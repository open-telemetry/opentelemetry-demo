# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
Single Source of Truth Live Incident Manager & Real-Time Monitoring Daemon.
Continuously monitors live microservices via Prometheus Golden Signals, Jaeger DAGs,
and OpenSearch logs. Manages incident detection, ReAct investigation, adversarial review,
human approval barrier, allowlisted remediation execution, and post-action verification.
"""

import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from oncall.models import IncidentAlert, IncidentRecord, RootCauseDiagnosis
from oncall.agent import AIOnCallAgent
from oncall.safety.reviewer_agent import ReviewerAgent
from oncall.safety.recovery_verifier import RecoveryVerifier
from oncall.actions.action_manager import ActionManager
from oncall.reporter import IncidentReporter
from oncall.tools.prometheus import PrometheusTool, DEFAULT_THRESHOLDS_MS
from oncall.tools.jaeger import JaegerTool
from oncall.tools.opensearch import OpenSearchTool

MONITORED_SERVICES = [
    "frontend", "checkout", "cart", "payment",
    "shipping", "ad", "recommendation", "product-catalog", "email"
]

POLL_INTERVAL_SECONDS = int(os.environ.get("ONCALL_POLL_INTERVAL", "5"))


class LiveIncidentManager:
    _instance: Optional["LiveIncidentManager"] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "LiveIncidentManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self, poll_interval: int = POLL_INTERVAL_SECONDS):
        self.poll_interval = poll_interval
        self.prom_tool = PrometheusTool()
        self.jaeger_tool = JaegerTool()
        self.opensearch_tool = OpenSearchTool()
        self.agent = AIOnCallAgent(prom_tool=self.prom_tool, jaeger_tool=self.jaeger_tool, opensearch_tool=self.opensearch_tool)
        self.reviewer = ReviewerAgent()
        self.action_mgr = ActionManager()
        self.verifier = RecoveryVerifier()

        self.service_health: Dict[str, Dict[str, Any]] = {}
        self.active_incidents: Dict[str, IncidentRecord] = {}
        self.consecutive_healthy: Dict[str, int] = {}
        
        self.telemetry_status = "UNKNOWN"
        self.telemetry_details: Dict[str, Any] = {}
        self.last_collection_time: Optional[str] = None
        self.daemon_running = False
        self._thread: Optional[threading.Thread] = None
        self._state_lock = threading.Lock()

    def start_daemon(self):
        """Starts the background continuous live monitoring thread."""
        with self._state_lock:
            if self.daemon_running:
                return
            self.daemon_running = True
            self._thread = threading.Thread(target=self._daemon_loop, daemon=True, name="LiveIncidentMonitorThread")
            self._thread.start()

    def stop_daemon(self):
        """Stops the continuous monitoring thread."""
        with self._state_lock:
            self.daemon_running = False

    def _daemon_loop(self):
        """Continuous background polling loop."""
        while self.daemon_running:
            try:
                self.poll_once()
            except Exception as e:
                print(f"[LiveIncidentManager] Error during poll cycle: {e}")
            time.sleep(self.poll_interval)

    def poll_once(self):
        """Performs one full evaluation cycle against live telemetry."""
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.isoformat()

        # 1. Check live connectivity across backbones
        prom_conn = self.prom_tool.check_connection()
        jaeger_conn = self.jaeger_tool.check_connection()
        opensearch_conn = self.opensearch_tool.check_connection()

        if prom_conn.get("connected") and jaeger_conn.get("connected"):
            if opensearch_conn.get("connected"):
                telemetry_status = "CONNECTED"
            else:
                telemetry_status = "DEGRADED"  # OpenSearch unavailable or indexing
        elif prom_conn.get("connected"):
            telemetry_status = "DEGRADED"
        else:
            telemetry_status = "DISCONNECTED"

        with self._state_lock:
            self.telemetry_status = telemetry_status
            self.telemetry_details = {
                "prometheus": prom_conn,
                "jaeger": jaeger_conn,
                "opensearch": opensearch_conn,
            }
            self.last_collection_time = now_str

        # 2. Query Golden Signals for each monitored service
        for service in MONITORED_SERVICES:
            threshold_ms = DEFAULT_THRESHOLDS_MS.get(service, DEFAULT_THRESHOLDS_MS["default"])
            obs = self.prom_tool.inspect_service_metrics(service, allow_fixtures=False)

            with self._state_lock:
                if not obs.success:
                    # Missing telemetry is never treated as zero or healthy!
                    self.service_health[service] = {
                        "service_name": service,
                        "latency_ms": None,
                        "error_rate": None,
                        "throughput_rps": None,
                        "status": "UNKNOWN" if telemetry_status == "DISCONNECTED" else "STALE",
                        "last_updated": now_str,
                        "threshold_ms": threshold_ms,
                        "is_live": False
                    }
                    continue

                p95_ms = obs.data.get("p95_latency_ms")
                err_rps = obs.data.get("error_rate_rps", 0.0)
                thru_rps = obs.data.get("throughput_rps", 0.0)

                # Classify health state based on explicit threshold
                if p95_ms is None:
                    health_status = "UNKNOWN"
                elif p95_ms > 2.0 * threshold_ms or err_rps > 5.0:
                    health_status = "CRITICAL"
                elif p95_ms > threshold_ms or err_rps > 0.5:
                    health_status = "WARNING"
                else:
                    health_status = "HEALTHY"

                self.service_health[service] = {
                    "service_name": service,
                    "latency_ms": p95_ms,
                    "error_rate": err_rps,
                    "throughput_rps": thru_rps,
                    "status": health_status,
                    "last_updated": now_str,
                    "threshold_ms": threshold_ms,
                    "is_live": True
                }

            # 3. Incident Lifecycle: Detection & Investigation
            if health_status in ("CRITICAL", "WARNING"):
                self._handle_active_anomaly(service, p95_ms, err_rps, threshold_ms, health_status, now_str)
            else:
                self._handle_healthy_service(service, p95_ms, err_rps, threshold_ms, now_str)

    def _handle_active_anomaly(self, service: str, p95_ms: float, err_rps: float, threshold_ms: float, health_status: str, now_str: str):
        with self._state_lock:
            self.consecutive_healthy[service] = 0

            # Find existing active incident for this service
            existing_inc = None
            for inc in self.active_incidents.values():
                if inc.alerted_service == service and inc.current_status in (
                    "INVESTIGATING", "AWAITING_APPROVAL", "APPROVED", "EXECUTING", "VERIFYING_RECOVERY"
                ):
                    existing_inc = inc
                    break

            if existing_inc:
                # Deduplication: update latest live measurements, do not duplicate incident!
                existing_inc.latest_live_measurement = {
                    "p95_latency_ms": p95_ms,
                    "error_rate_rps": err_rps,
                    "timestamp_utc": now_str
                }
                existing_inc.telemetry_evaluation_timestamp = now_str
                return

        # No active incident: launch fresh autonomous investigation
        incident_id = f"INC-{service.upper()}-{int(time.time())}"
        alert = IncidentAlert(
            alert_id=incident_id,
            service_name=service,
            title=f"{service.capitalize()}DegradedPerformance",
            severity="critical" if health_status == "CRITICAL" else "warning",
            started_at=datetime.now(timezone.utc),
            summary=f"Golden Signals Violation: P95 Latency = {p95_ms:.1f}ms (threshold: {threshold_ms:.0f}ms), Error Rate = {err_rps:.2f} req/s.",
            snapshot_p95_ms=p95_ms,
            snapshot_error_rate_rps=err_rps,
            snapshot_timestamp_utc=now_str
        )

        try:
            diag = self.agent.investigate(alert, allow_fixtures=False)
            rev = self.reviewer.review_diagnosis(diag)

            # Determine proposed remediation & status
            if diag.action_type == "NO_ACTION" or diag.telemetry_reconciliation_status in ("NOMINAL_BASELINE", "RECOVERED_SINCE_TRIGGER"):
                curr_status = "NO_ACTION_REQUIRED"
                root_status = "LIKELY"
                approval_stat = "NOT_REQUIRED"
                prop_remed = None
            else:
                curr_status = "AWAITING_APPROVAL"
                root_status = "CONFIRMED" if (diag.confidence_score >= 0.85 and rev.get("approved")) else "LIKELY"
                approval_stat = "AWAITING_APPROVAL"
                prop_remed = {
                    "action_type": diag.action_type,
                    "target_service": diag.root_cause_service,
                    "reason": diag.explanation,
                    "expected_impact": f"Restore P95 latency on '{diag.root_cause_service}' to <{threshold_ms:.0f}ms.",
                    "risk": "Low (stateless container recycling)" if diag.action_type == "RESTART_CONTAINER" else "Medium",
                    "rollback_available": True,
                    "parameters": {"action": diag.action_type, "target": diag.root_cause_service}
                }

            record = IncidentRecord(
                incident_id=incident_id,
                alerted_service=service,
                title=alert.title,
                severity=alert.severity,
                detection_timestamp=now_str,
                current_status=curr_status,
                root_cause_status=root_status,
                triggering_metric="P95 Latency",
                threshold_ms=threshold_ms,
                triggering_measurement={
                    "p95_latency_ms": p95_ms,
                    "error_rate_rps": err_rps,
                    "timestamp_utc": now_str
                },
                latest_live_measurement={
                    "p95_latency_ms": p95_ms,
                    "error_rate_rps": err_rps,
                    "timestamp_utc": now_str
                },
                telemetry_evaluation_timestamp=now_str,
                telemetry_reconciliation_status=diag.telemetry_reconciliation_status,
                root_cause_service=diag.root_cause_service,
                is_downstream=diag.is_downstream,
                failure_mode=diag.failure_mode,
                confidence_score=diag.confidence_score,
                trace_ids=[diag.trace_summary.get("trace_id")] if diag.trace_summary.get("trace_id") else [],
                span_ids=[diag.trace_summary.get("span_id")] if diag.trace_summary.get("span_id") else [],
                trace_summary=diag.trace_summary,
                log_evidence_status=diag.log_evidence_status,
                deployment_evidence_type=diag.deployment_evidence_type,
                confirmed_facts=diag.confirmed_facts,
                likely_causes=diag.likely_causes,
                unresolved_hypotheses=diag.unresolved_hypotheses,
                citations=diag.citations,
                reviewer_verdict=rev,
                proposed_remediation=prop_remed,
                approval_status=approval_stat,
                execution_status="NOT_STARTED",
                recovery_verification_status="NOT_STARTED",
                post_mortem_report=None  # Strictly None until remediation is executed!
            )

            with self._state_lock:
                self.active_incidents[incident_id] = record
        except Exception as e:
            print(f"[LiveIncidentManager] Failed to investigate incident for {service}: {e}")

    def _handle_healthy_service(self, service: str, p95_ms: Optional[float], err_rps: float, threshold_ms: float, now_str: str):
        with self._state_lock:
            self.consecutive_healthy[service] = self.consecutive_healthy.get(service, 0) + 1
            healthy_count = self.consecutive_healthy[service]

            for inc in list(self.active_incidents.values()):
                if inc.alerted_service == service and inc.current_status in ("INVESTIGATING", "AWAITING_APPROVAL"):
                    if healthy_count >= 3:
                        # Auto-reconcile incident since trigger
                        inc.current_status = "RECOVERED"
                        inc.telemetry_reconciliation_status = "RECOVERED_SINCE_TRIGGER"
                        inc.approval_status = "SUPERSEDED"
                        inc.latest_live_measurement = {
                            "p95_latency_ms": p95_ms,
                            "error_rate_rps": err_rps,
                            "timestamp_utc": now_str
                        }
                        inc.telemetry_evaluation_timestamp = now_str
                        inc.confirmed_facts.append(
                            f"Live Telemetry Reconciled: '{service}' normalized across {healthy_count} consecutive polling cycles prior to action execution."
                        )

    def get_dashboard_state(self) -> Dict[str, Any]:
        """Produces the complete snapshot for the live operations console."""
        with self._state_lock:
            # Sort incidents: active awaiting approval first, then active investigating, then recovered
            incidents_list = [inc.model_dump() for inc in self.active_incidents.values()]
            incidents_list.sort(
                key=lambda x: (
                    0 if x["current_status"] == "AWAITING_APPROVAL" else (
                        1 if x["current_status"] in ("INVESTIGATING", "EXECUTING", "VERIFYING_RECOVERY") else (
                            2 if x["current_status"] == "NO_ACTION_REQUIRED" else 3
                        )
                    ),
                    x["detection_timestamp"]
                ),
                reverse=False
            )

            return {
                "telemetry_status": self.telemetry_status,
                "telemetry_details": self.telemetry_details,
                "monitoring_daemon": {
                    "running": self.daemon_running,
                    "poll_interval_seconds": self.poll_interval,
                    "monitored_services_count": len(MONITORED_SERVICES),
                    "last_collection_time": self.last_collection_time,
                },
                "service_health": list(self.service_health.values()),
                "active_incidents": incidents_list,
                "system_time_utc": datetime.now(timezone.utc).isoformat()
            }

    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single incident record by ID."""
        with self._state_lock:
            inc = self.active_incidents.get(incident_id)
            return inc.model_dump() if inc else None

    def approve_remediation(self, incident_id: str, approver: str = "operator_web_console") -> Dict[str, Any]:
        """
        Validates safety, authorizes cryptographic token, executes allowlisted runbook,
        verifies recovery, and generates post-mortem report ONLY upon execution.
        """
        with self._state_lock:
            incident = self.active_incidents.get(incident_id)
            if not incident:
                return {"success": False, "error": f"Incident '{incident_id}' not found."}

            if incident.current_status != "AWAITING_APPROVAL":
                return {
                    "success": False,
                    "error": f"Incident '{incident_id}' is in state '{incident.current_status}' (not AWAITING_APPROVAL)."
                }

            # 1. Pre-Execution Telemetry Re-check: has the service already recovered?
            service = incident.alerted_service
            threshold_ms = incident.threshold_ms
            recheck_obs = self.prom_tool.inspect_service_metrics(service, allow_fixtures=False)
            if recheck_obs.success:
                curr_p95 = recheck_obs.data.get("p95_latency_ms")
                if curr_p95 is not None and curr_p95 < threshold_ms:
                    # Invalidate obsolete action
                    incident.current_status = "RECOVERED"
                    incident.telemetry_reconciliation_status = "RECOVERED_SINCE_TRIGGER"
                    incident.approval_status = "SUPERSEDED"
                    return {
                        "success": False,
                        "action_status": "SUPERSEDED",
                        "error": f"Action invalidated: Service '{service}' has already recovered (P95: {curr_p95:.1f}ms < {threshold_ms:.0f}ms). Destructive mutation prevented."
                    }

            # 2. Extract approved action parameters
            remed = incident.proposed_remediation or {}
            action_type = remed.get("action_type", "RESTART_CONTAINER")
            target_service = remed.get("target_service", incident.root_cause_service)

            # Generate Cryptographic Token
            auth_token = f"AUTH-UI-{uuid.uuid4().hex[:6].upper()}"
            incident.approval_status = "APPROVED"
            incident.approval_token = auth_token
            incident.approved_by = approver
            incident.approval_timestamp = datetime.now(timezone.utc).isoformat()
            incident.current_status = "EXECUTING"
            incident.execution_status = "EXECUTING"

        # 3. Action API Execution
        exec_res = self.action_mgr.execute_action(
            action_type=action_type,
            target_service=target_service,
            parameters=remed.get("parameters", {}),
            auth_token=auth_token,
            dry_run=False
        )

        with self._state_lock:
            incident.execution_result = exec_res
            incident.execution_timestamp = datetime.now(timezone.utc).isoformat()
            if not exec_res.get("success"):
                incident.execution_status = "EXECUTION_FAILED"
                incident.current_status = "EXECUTION_FAILED"
                return {
                    "success": False,
                    "action_status": "EXECUTION_FAILED",
                    "error": exec_res.get("error", "Action execution failed"),
                    "token": auth_token
                }

            incident.execution_status = "EXECUTED"
            incident.current_status = "VERIFYING_RECOVERY"
            incident.recovery_verification_status = "VERIFYING"

        # 4. Post-Action Recovery Verification (Polling fresh Prometheus telemetry on target service)
        verify_service = target_service or incident.alerted_service
        verif_res = self.verifier.verify_recovery(service_name=verify_service, timeout_seconds=5)

        with self._state_lock:
            incident.recovery_details = verif_res
            if verif_res.get("recovered"):
                incident.current_status = "RECOVERED"
                incident.recovery_verification_status = "RECOVERED"
            else:
                incident.current_status = "RECOVERY_UNCONFIRMED"
                incident.recovery_verification_status = "FAILED"
                # Automated Rollback on Recovery Failure
                rollback_res = self.action_mgr.rollback_last_action()
                incident.recovery_details["rollback"] = rollback_res

            # 5. GENERATE POST-MORTEM REPORT (ONLY AFTER FIX EXECUTION)
            alert = IncidentAlert(
                alert_id=incident.incident_id,
                service_name=incident.alerted_service,
                title=incident.title,
                severity=incident.severity,
                started_at=datetime.fromisoformat(incident.detection_timestamp),
                summary=f"Incident on '{incident.alerted_service}'. P95 breached SLA threshold."
            )
            diag = RootCauseDiagnosis(
                incident_id=incident.incident_id,
                target_service=incident.alerted_service,
                root_cause_service=incident.root_cause_service,
                is_downstream=incident.is_downstream,
                failure_mode=incident.failure_mode,
                confidence_score=incident.confidence_score,
                incident_snapshot=incident.triggering_measurement,
                current_telemetry=incident.latest_live_measurement,
                telemetry_reconciliation_status=incident.telemetry_reconciliation_status,
                trace_summary=incident.trace_summary,
                log_evidence_status=incident.log_evidence_status,
                deployment_evidence_type=incident.deployment_evidence_type,
                confirmed_facts=incident.confirmed_facts,
                likely_causes=incident.likely_causes,
                unresolved_hypotheses=incident.unresolved_hypotheses,
                citations=incident.citations,
                explanation=remed.get("reason", "Root cause diagnosed through empirical telemetry."),
                recommended_action=f"Execute {action_type} on '{target_service}'.",
                action_type=action_type,
                action_status="EXECUTED",
                verification_status="RECOVERED" if verif_res.get("recovered") else "NOT_RECOVERED"
            )

            report_md = IncidentReporter.generate_markdown_report(
                alert=alert,
                diagnosis=diag,
                approval={
                    "approved": True,
                    "token": auth_token,
                    "approver": approver,
                    "timestamp": incident.approval_timestamp
                },
                execution=exec_res,
                verification=verif_res,
                reviewer_audit=incident.reviewer_verdict
            )
            incident.post_mortem_report = report_md
            incident.report_generated_at = datetime.now(timezone.utc).isoformat()

            return {
                "success": True,
                "incident_id": incident_id,
                "action_status": incident.execution_status,
                "token": auth_token,
                "target": target_service,
                "action": action_type,
                "outcome": exec_res.get("message") or exec_res.get("error"),
                "verification_status": incident.recovery_verification_status,
                "recovery_duration_seconds": verif_res.get("verification_duration_seconds", 12.0),
                "post_mortem_report": report_md
            }

    def reject_remediation(self, incident_id: str, approver: str = "operator_web_console", notes: str = "Rejected by operator") -> Dict[str, Any]:
        """Rejects remediation and escalates to human on-call without executing or generating post-mortem."""
        with self._state_lock:
            incident = self.active_incidents.get(incident_id)
            if not incident:
                return {"success": False, "error": f"Incident '{incident_id}' not found."}

            incident.approval_status = "REJECTED"
            incident.current_status = "ESCALATED"
            incident.approved_by = approver
            incident.approval_timestamp = datetime.now(timezone.utc).isoformat()
            incident.confirmed_facts.append(f"Remediation rejected by human operator ({notes}). Escalated.")
            return {
                "success": True,
                "incident_id": incident_id,
                "status": "ESCALATED",
                "notes": notes
            }
