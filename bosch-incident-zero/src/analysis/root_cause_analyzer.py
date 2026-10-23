"""Deterministic, explainable Root Cause Analyzer for Bosch Incident Zero.

Evaluates multi-signal EvidenceBundles using rule-based diagnostic logic:
- Rule 1: A service with error traces and matching error logs is a stronger candidate than one with downstream symptoms only.
- Rule 2: A dependency showing errors before or during caller failures is an upstream cause.
- Rule 3: Latency increases without corresponding errors indicate performance issues rather than crashes.
- Rule 4: A service with missing/unavailable telemetry is not automatically healthy.
- Rule 5: Unavailable telemetry sources penalize diagnostic certainty.
- Rule 6: Conflicting signals between metrics, traces, and logs are surfaced explicitly.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from ..models.evidence import EvidenceBundle, MetricDataPoint
from ..models.incident import IncidentSeverity
from ..models.diagnosis import (
    DiagnosisResult,
    DiagnosisStatus,
    FailureMode,
    RootCauseCandidate,
)

# Known microservice names in OpenTelemetry Astronomy Shop
KNOWN_SERVICES: Set[str] = {
    "ad",
    "cart",
    "checkout",
    "currency",
    "email",
    "frontend",
    "frontend-proxy",
    "image-provider",
    "kafka",
    "payment",
    "product-catalog",
    "quote",
    "recommendation",
    "shipping",
    "accounting",
    "fraud-detection",
    "valkey-cart",
    "valkey",
    "postgresql",
    "astronomy-db",
}

DEPENDENCY_FAILURE_KEYWORDS = [
    "connection refused",
    "failed to connect",
    "unavailable",
    "deadline exceeded",
    "timeout",
    "timed out",
    "broken pipe",
    "unreachable",
    "name resolution failure",
    "503",
    "status code 14",  # gRPC UNAVAILABLE
    "network error",
]


class RootCauseAnalyzer:
    """Deterministic analyzer isolating root causes from multi-signal evidence."""

    def __init__(self, thresholds: Optional[Dict[str, float]] = None) -> None:
        self.thresholds = thresholds or {
            "error_rate_threshold": 0.05,
            "latency_threshold_ms": 2000.0,
            "latency_ratio_threshold": 2.0,
        }

    def diagnose(self, bundle: EvidenceBundle) -> DiagnosisResult:
        """Analyze an EvidenceBundle and return ranked, explainable root-cause candidates."""
        now_iso = datetime.now(timezone.utc).isoformat()
        service = bundle.service_name

        # 1. Parse and classify signals
        traces_info = self._analyze_traces(bundle)
        metrics_info = self._analyze_metrics(bundle)
        logs_info = self._analyze_logs(bundle)
        telemetry_info = self._analyze_telemetry_health(bundle)

        missing_evidence: List[str] = list(telemetry_info["missing_evidence"])
        contradictory_evidence: List[str] = []

        # 2. Check for conflicting evidence (Rule 6)
        conflicts = self._detect_conflicting_signals(traces_info, metrics_info, logs_info, telemetry_info)
        contradictory_evidence.extend(conflicts)

        # 3. Detect candidate root causes
        raw_candidates: List[RootCauseCandidate] = []

        # Check for dependency outages (Rule 2)
        dep_candidates, dep_victim = self._detect_dependency_outages(
            service=service,
            bundle=bundle,
            logs_info=logs_info,
            traces_info=traces_info,
            metrics_info=metrics_info,
            telemetry_info=telemetry_info,
        )
        raw_candidates.extend(dep_candidates)

        # Check for internal service errors (Rule 1)
        internal_candidate = self._detect_internal_service_fault(
            service=service,
            traces_info=traces_info,
            metrics_info=metrics_info,
            logs_info=logs_info,
            telemetry_info=telemetry_info,
            has_dependency_root_cause=bool(dep_candidates),
        )
        if internal_candidate:
            raw_candidates.append(internal_candidate)

        # If a dependency failure was detected, append the investigated service as a cascading victim
        if dep_victim and not any(c.service == service for c in raw_candidates):
            raw_candidates.append(dep_victim)

        # Check for latency degradation without errors (Rule 3)
        latency_candidate = self._detect_latency_degradation(
            service=service,
            metrics_info=metrics_info,
            traces_info=traces_info,
            logs_info=logs_info,
            telemetry_info=telemetry_info,
        )
        if latency_candidate:
            raw_candidates.append(latency_candidate)

        # 4. Rank candidates and compute overall diagnosis status
        candidates = self._rank_candidates(raw_candidates, contradictory_evidence, telemetry_info)

        # Determine overall status and confidence
        status, overall_conf, next_step = self._determine_overall_status(
            service=service,
            candidates=candidates,
            telemetry_info=telemetry_info,
            contradictory_evidence=contradictory_evidence,
            traces_info=traces_info,
            metrics_info=metrics_info,
            logs_info=logs_info,
        )

        primary_root = candidates[0] if candidates else None

        supporting_evidence: Dict[str, Any] = {
            "trace_ids": bundle.trace_ids,
            "metrics_summary": {m.metric_name: m.observed_value for m in bundle.metrics},
            "log_excerpts": bundle.log_excerpts,
            "signal_counts": {
                "error_traces": traces_info["count"],
                "error_logs": logs_info["count"],
                "metrics_analyzed": len(bundle.metrics),
            },
        }

        scoring_breakdown: Dict[str, Any] = {
            "telemetry_availability_penalty": telemetry_info["penalty"],
            "conflicting_evidence_penalty": -0.25 if contradictory_evidence else 0.0,
            "available_sources": telemetry_info["available_sources"],
            "unavailable_sources": telemetry_info["unavailable_sources"],
        }

        return DiagnosisResult(
            investigated_service=service,
            diagnosis_timestamp=now_iso,
            status=status,
            overall_confidence=overall_conf,
            primary_root_cause=primary_root,
            candidates=candidates,
            supporting_evidence=supporting_evidence,
            contradictory_evidence=contradictory_evidence,
            missing_evidence=missing_evidence,
            scoring_breakdown=scoring_breakdown,
            recommended_next_step=next_step,
        )

    # --------------------------------------------------------------------------
    # Signal Parsers
    # --------------------------------------------------------------------------

    def _analyze_traces(self, bundle: EvidenceBundle) -> Dict[str, Any]:
        count = len(bundle.trace_ids)
        return {
            "has_errors": count > 0,
            "count": count,
            "trace_ids": bundle.trace_ids,
        }

    def _analyze_metrics(self, bundle: EvidenceBundle) -> Dict[str, Any]:
        error_rate: Optional[float] = None
        latency_val: Optional[float] = None
        latency_baseline: Optional[float] = None

        for m in bundle.metrics:
            name_lower = m.metric_name.lower()
            if "error" in name_lower or "fail" in name_lower:
                error_rate = m.observed_value
            elif "latency" in name_lower or "duration" in name_lower:
                latency_val = m.observed_value
                latency_baseline = m.baseline_value

        is_error_elevated = (
            error_rate is not None and error_rate > self.thresholds["error_rate_threshold"]
        )
        is_latency_elevated = False
        if latency_val is not None:
            if latency_val >= self.thresholds["latency_threshold_ms"]:
                is_latency_elevated = True
            elif latency_baseline and latency_baseline > 0:
                if (latency_val / latency_baseline) >= self.thresholds["latency_ratio_threshold"]:
                    is_latency_elevated = True

        return {
            "has_metrics": len(bundle.metrics) > 0,
            "error_rate": error_rate,
            "is_error_elevated": is_error_elevated,
            "latency": latency_val,
            "latency_baseline": latency_baseline,
            "is_latency_elevated": is_latency_elevated,
        }

    def _analyze_logs(self, bundle: EvidenceBundle) -> Dict[str, Any]:
        count = len(bundle.log_excerpts)
        return {
            "has_errors": count > 0,
            "count": count,
            "excerpts": bundle.log_excerpts,
        }

    def _analyze_telemetry_health(self, bundle: EvidenceBundle) -> Dict[str, Any]:
        source_status = bundle.metadata.get("source_status", {})
        source_errors = bundle.metadata.get("source_errors", {})

        available = [s for s, st in source_status.items() if st == "available"]
        unavailable = [s for s, st in source_status.items() if st == "unavailable"]
        missing_evidence: List[str] = []

        for src in unavailable:
            err = source_errors.get(src, "unreachable")
            missing_evidence.append(f"Telemetry store '{src}' was unavailable ({err})")

        total_checked = len(source_status)
        if total_checked == 0:
            penalty = 0.0
        elif len(unavailable) == total_checked:
            penalty = -1.0
        elif len(unavailable) == 2:
            penalty = -0.45
        elif len(unavailable) == 1:
            penalty = -0.20
        else:
            penalty = 0.0

        return {
            "source_status": source_status,
            "available_sources": available,
            "unavailable_sources": unavailable,
            "missing_evidence": missing_evidence,
            "penalty": penalty,
            "is_total_outage": total_checked > 0 and len(available) == 0,
        }

    # --------------------------------------------------------------------------
    # Conflict Detection (Rule 6)
    # --------------------------------------------------------------------------

    def _detect_conflicting_signals(
        self,
        traces: Dict[str, Any],
        metrics: Dict[str, Any],
        logs: Dict[str, Any],
        telemetry: Dict[str, Any],
    ) -> List[str]:
        conflicts: List[str] = []
        status = telemetry["source_status"]

        # Conflict 1: Elevated metric error rate, but 0 traces & 0 logs when stores are available
        if metrics["is_error_elevated"]:
            jaeger_available = status.get("jaeger") == "available"
            opensearch_available = status.get("opensearch") == "available"
            if jaeger_available and opensearch_available and not traces["has_errors"] and not logs["has_errors"]:
                conflicts.append(
                    f"Prometheus reports elevated error rate ({metrics['error_rate']}), "
                    "but Jaeger and OpenSearch report 0 error traces or logs despite being available."
                )

        # Conflict 2: Error traces or logs exist, but metrics explicitly report 0.0 error rate
        if (traces["has_errors"] or logs["has_errors"]) and metrics.get("error_rate") == 0.0:
            if status.get("prometheus") == "available":
                conflicts.append(
                    "Error traces/logs detected in system, but Prometheus explicitly reports an error rate of 0.0."
                )

        return conflicts

    # --------------------------------------------------------------------------
    # Root Cause Candidate Detection Rules
    # --------------------------------------------------------------------------

    def _detect_dependency_outages(
        self,
        service: str,
        bundle: EvidenceBundle,
        logs_info: Dict[str, Any],
        traces_info: Dict[str, Any],
        metrics_info: Dict[str, Any],
        telemetry_info: Dict[str, Any],
    ) -> Tuple[List[RootCauseCandidate], Optional[RootCauseCandidate]]:
        """Identify if an upstream/downstream dependency failed (Rule 2)."""
        candidates: List[RootCauseCandidate] = []
        victim_candidate: Optional[RootCauseCandidate] = None

        downstream = set(bundle.dependency_graph.get("downstream", []))
        # Prioritize explicit downstream dependencies first, then sort by name length descending
        search_pool = (downstream | KNOWN_SERVICES) - {service}
        sorted_candidates = sorted(
            list(search_pool),
            key=lambda x: (x in downstream, len(x)),
            reverse=True,
        )

        detected_deps: Dict[str, List[str]] = {}

        for log in logs_info.get("excerpts", []):
            log_lower = log.lower()
            matched_dep_for_log = None
            for dep in sorted_candidates:
                # Check if dependency name is cited as a whole token or delimiter
                if re.search(rf"\b{re.escape(dep)}\b", log_lower):
                    # Check if error keyword is also present
                    if any(kw in log_lower for kw in DEPENDENCY_FAILURE_KEYWORDS):
                        detected_deps.setdefault(dep, []).append(log)
                        matched_dep_for_log = dep
                        # Avoid sub-string matches on the same log (e.g. matching 'valkey' when 'valkey-cart' matched)
                        break

        for dep, matching_logs in detected_deps.items():
            signals = [f"logs: {len(matching_logs)} entries cite communication failure with '{dep}'"]
            if traces_info["has_errors"]:
                signals.append(f"traces: {traces_info['count']} error traces correlated with dependency failure")
            if metrics_info["is_error_elevated"]:
                signals.append(f"metrics: elevated error rate ratio = {metrics_info['error_rate']}")

            # Calculate base confidence
            # Traces (+0.30) + Logs (+0.35) + Metrics (+0.25)
            score = 0.35  # Strong log evidence
            if traces_info["has_errors"]:
                score += 0.30
            if metrics_info["is_error_elevated"]:
                score += 0.25

            # Apply telemetry availability penalty
            score += telemetry_info["penalty"]
            final_conf = max(0.0, min(1.0, round(score, 3)))

            reasoning = (
                f"Target service '{service}' logs explicitly report communication failures with dependency '{dep}'. "
                f"Under Rule 2, '{dep}' is identified as the originating root cause rather than {service}."
            )

            candidates.append(
                RootCauseCandidate(
                    service=dep,
                    failure_mode=FailureMode.DEPENDENCY_OUTAGE,
                    confidence=final_conf,
                    rank=1,
                    reasoning=reasoning,
                    supporting_signals=signals,
                    is_dependency=True,
                    severity=IncidentSeverity.CRITICAL,
                )
            )

        if candidates:
            # Service itself is a cascading victim (Rule 1 & 2)
            victim_signals = [f"symptoms: cascading errors triggered by dependency outage in {candidates[0].service}"]
            if metrics_info["is_error_elevated"]:
                victim_signals.append(f"metrics: error rate {metrics_info['error_rate']}")
            victim_conf = max(0.1, min(0.45, round(candidates[0].confidence * 0.5, 3)))

            victim_candidate = RootCauseCandidate(
                service=service,
                failure_mode=FailureMode.CASCADING_SYMPTOMATIC_FAILURE,
                confidence=victim_conf,
                rank=2,
                reasoning=(
                    f"'{service}' exhibits failure symptoms but is a dependent caller of failing service "
                    f"'{candidates[0].service}'. Under Rule 1 & 2, it is classified as a cascading symptom."
                ),
                supporting_signals=victim_signals,
                is_dependency=False,
                severity=IncidentSeverity.HIGH,
            )

        return candidates, victim_candidate

    def _detect_internal_service_fault(
        self,
        service: str,
        traces_info: Dict[str, Any],
        metrics_info: Dict[str, Any],
        logs_info: Dict[str, Any],
        telemetry_info: Dict[str, Any],
        has_dependency_root_cause: bool,
    ) -> Optional[RootCauseCandidate]:
        """Detect internal service faults (Rule 1)."""
        # If a dependency failure was already confirmed, internal fault is unlikely unless logs indicate panic
        has_traces = traces_info["has_errors"]
        has_logs = logs_info["has_errors"]
        has_metrics = metrics_info["is_error_elevated"]

        if not (has_traces or has_logs or has_metrics):
            return None

        # If a dependency failure was explicitly identified, only create internal candidate if distinct
        if has_dependency_root_cause:
            return None

        signals: List[str] = []
        score = 0.0

        if has_traces:
            score += 0.30
            signals.append(f"traces: {traces_info['count']} error traces detected in Jaeger")
        if has_logs:
            score += 0.30
            signals.append(f"logs: {logs_info['count']} error log excerpts recorded in OpenSearch")
        if has_metrics:
            score += 0.25
            signals.append(f"metrics: elevated error rate {metrics_info['error_rate']}")

        # Internal signature checks (OOM, High CPU, Panic)
        log_text = " ".join(logs_info.get("excerpts", [])).lower()
        failure_mode = FailureMode.INTERNAL_SERVICE_ERROR
        if "outofmemory" in log_text or "memory leak" in log_text:
            failure_mode = FailureMode.MEMORY_LEAK
            score += 0.10
            signals.append("logs: memory exhaustion / OOM signature identified")
        elif "high cpu" in log_text or "cpu starvation" in log_text:
            failure_mode = FailureMode.RESOURCE_STARVATION_CPU
            score += 0.10
            signals.append("logs: CPU starvation signature identified")

        score += telemetry_info["penalty"]
        final_conf = max(0.0, min(1.0, round(score, 3)))

        reasoning = (
            f"Service '{service}' exhibits corroborated error traces, logs, and metric deviations without "
            "external dependency faults (Rule 1). The root cause originates internally within this service."
        )

        return RootCauseCandidate(
            service=service,
            failure_mode=failure_mode,
            confidence=final_conf,
            rank=1,
            reasoning=reasoning,
            supporting_signals=signals,
            is_dependency=False,
            severity=IncidentSeverity.HIGH if final_conf >= 0.5 else IncidentSeverity.MEDIUM,
        )

    def _detect_latency_degradation(
        self,
        service: str,
        metrics_info: Dict[str, Any],
        traces_info: Dict[str, Any],
        logs_info: Dict[str, Any],
        telemetry_info: Dict[str, Any],
    ) -> Optional[RootCauseCandidate]:
        """Detect latency degradation / performance issue without crash errors (Rule 3)."""
        if not metrics_info["is_latency_elevated"]:
            return None

        # Rule 3 applies especially when errors are low or absent
        has_errors = traces_info["has_errors"] or logs_info["has_errors"] or metrics_info["is_error_elevated"]

        lat = metrics_info["latency"]
        base = metrics_info["latency_baseline"]
        signals = [f"metrics: p95 latency = {lat}ms (baseline: {base}ms)"]

        if not has_errors:
            score = 0.70 + telemetry_info["penalty"]
            final_conf = max(0.0, min(1.0, round(score, 3)))
            reasoning = (
                f"Service '{service}' displays elevated p95 latency ({lat}ms) without error traces or error logs. "
                "Under Rule 3, this is classified as a performance degradation / latency bottleneck rather than a failure."
            )
            return RootCauseCandidate(
                service=service,
                failure_mode=FailureMode.LATENCY_DEGRADATION,
                confidence=final_conf,
                rank=1,
                reasoning=reasoning,
                supporting_signals=signals,
                is_dependency=False,
                severity=IncidentSeverity.MEDIUM,
            )

        return None

    # --------------------------------------------------------------------------
    # Ranking & Overall Status Determination
    # --------------------------------------------------------------------------

    def _rank_candidates(
        self,
        candidates: List[RootCauseCandidate],
        conflicts: List[str],
        telemetry: Dict[str, Any],
    ) -> List[RootCauseCandidate]:
        """Rank candidates by evidence strength and adjust confidence for conflicts."""
        conflict_penalty = 0.25 if conflicts else 0.0

        for cand in candidates:
            adjusted = max(0.0, round(cand.confidence - conflict_penalty, 3))
            cand.confidence = adjusted

        # Sort: Highest confidence first; break ties with dependency (direct cause > symptom)
        sorted_cands = sorted(
            candidates,
            key=lambda c: (c.confidence, 1 if c.is_dependency else 0, len(c.supporting_signals)),
            reverse=True,
        )

        for i, cand in enumerate(sorted_cands, start=1):
            cand.rank = i

        return sorted_cands

    def _determine_overall_status(
        self,
        service: str,
        candidates: List[RootCauseCandidate],
        telemetry_info: Dict[str, Any],
        contradictory_evidence: List[str],
        traces_info: Dict[str, Any],
        metrics_info: Dict[str, Any],
        logs_info: Dict[str, Any],
    ) -> Tuple[DiagnosisStatus, float, str]:
        """Determine overall diagnosis status, confidence score, and recommended next step."""
        # Case 1: Total telemetry outage
        if telemetry_info["is_total_outage"]:
            return (
                DiagnosisStatus.INSUFFICIENT_EVIDENCE,
                0.0,
                f"Restore network connectivity to telemetry backends ({', '.join(telemetry_info['unavailable_sources'])})."
            )

        # Case 2: Candidates identified
        if candidates:
            primary = candidates[0]
            conf = primary.confidence

            # Never claim a root cause is confirmed when evidence is insufficient
            if primary.failure_mode == FailureMode.LATENCY_DEGRADATION:
                status = DiagnosisStatus.DEGRADED_PERFORMANCE
                next_step = f"Profile '{service}' CPU/memory allocation and inspect downstream call latency."
            elif conf >= 0.70 and not contradictory_evidence and not telemetry_info["unavailable_sources"]:
                status = DiagnosisStatus.CONFIRMED
                if primary.is_dependency:
                    next_step = (
                        f"Request approval to remediate root-cause dependency '{primary.service}' "
                        f"(e.g., check container health, restart, or revert fault flags)."
                    )
                else:
                    next_step = f"Request approval to restart or roll back '{service}'."
            elif conf >= 0.40:
                status = DiagnosisStatus.SUSPECTED
                if contradictory_evidence:
                    next_step = "Resolve conflicting telemetry signals by checking raw service metrics and running an active trace probe."
                elif telemetry_info["unavailable_sources"]:
                    next_step = (
                        f"Verify telemetry sources {telemetry_info['unavailable_sources']} to confirm suspected diagnosis "
                        f"for '{primary.service}'."
                    )
                else:
                    next_step = f"Gather additional trace samples for '{primary.service}' before initiating remediation."
            else:
                status = DiagnosisStatus.INSUFFICIENT_EVIDENCE
                next_step = "Evidence is too weak to isolate a root cause. Run a synthetic warmup probe to generate active traces."

            return status, conf, next_step

        # Case 3: No candidates found
        has_any_errors = traces_info["has_errors"] or metrics_info["is_error_elevated"] or logs_info["has_errors"]
        if not has_any_errors:
            if telemetry_info["unavailable_sources"]:
                # Rule 4: A service with no telemetry is not automatically healthy
                return (
                    DiagnosisStatus.INSUFFICIENT_EVIDENCE,
                    0.0,
                    f"No errors recorded, but telemetry stores ({', '.join(telemetry_info['unavailable_sources'])}) are unavailable. Verify backend reachability."
                )
            else:
                return (
                    DiagnosisStatus.NO_ANOMALY_DETECTED,
                    0.0,
                    f"Service '{service}' is healthy. No anomalous metrics, error traces, or error logs detected."
                )

        return (
            DiagnosisStatus.INSUFFICIENT_EVIDENCE,
            0.0,
            "Ambiguous telemetry signals detected without identifiable failure signatures. Inspect manual logs."
        )
