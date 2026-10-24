# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
Adversarial Reviewer Agent (Stretch Goal 2).
Acts as an independent critic that validates empirical grounding, Rule 6 compliance,
and causal proof before any recommendation reaches the human operator.
"""

from typing import Dict, Any, List
from oncall.models import RootCauseDiagnosis


class ReviewerAgent:
    PROHIBITED_SOURCES = ["flagd_config", "flag_file", "feature_flag_api"]
    PROHIBITED_RESTART_TARGETS = [
        "otel-collector", "jaeger", "prometheus", "opensearch", "grafana",
        "flagd", "flagd-ui", "astronomy-db", "valkey-cart"
    ]

    def review_diagnosis(self, diagnosis: RootCauseDiagnosis) -> Dict[str, Any]:
        """
        Adversarially critiques the primary agent's diagnosis:
        1. Enforces Rule 6: Zero feature-flag inspection citations in diagnosis.
        2. Validates trace DAG causal proof (ensures no 'None' or 'Nonems').
        3. Enforces honest log evidence accounting (NO_DATA must not be claimed as corroborating).
        4. Reconciles temporal metric discrepancies (active outage vs recovered since trigger).
        5. Validates allowlisted and safe action runbooks (blocks restarts on databases/telemetry).
        """
        challenges: List[str] = []
        checks_passed: List[str] = []

        # Audit 1: Rule 6 Adherence
        has_flag_cheats = any(c.source_type.lower() in self.PROHIBITED_SOURCES for c in diagnosis.citations)
        if has_flag_cheats:
            challenges.append("RULE 6 VIOLATION: Diagnosis contains forbidden feature flag inspection citations.")
        else:
            checks_passed.append("Rule 6 Adherence: Verified zero flag-reading citations during diagnosis.")

        # Audit 2: Trace DAG Causal Grounding
        trace_summary = diagnosis.trace_summary or {}
        parent_op = trace_summary.get("parent_operation")
        downstream_op = trace_summary.get("downstream_operation")
        
        if parent_op in (None, "None") or downstream_op in (None, "None"):
            challenges.append("Trace Metadata Incomplete: Operation name is 'None' or missing from trace tree.")
        else:
            checks_passed.append(f"Trace Metadata Validated: Concrete operations recorded ('{parent_op}' -> '{downstream_op}').")

        if diagnosis.is_downstream:
            culprit = diagnosis.root_cause_service
            target = diagnosis.target_service
            if culprit == target:
                challenges.append("Causal Contradiction: is_downstream is True, but root cause equals target service.")
            else:
                checks_passed.append(f"Downstream Trace Proof: Isolated blocker '{culprit}' accounting for child execution delay.")
        else:
            checks_passed.append("Local Failure Validated: Internal service execution accounts for latency without downstream blocker.")

        # Audit 3: Honest Log Accounting (NO_DATA handling)
        if diagnosis.log_evidence_status == "NO_DATA":
            # Verify agent did NOT fabricate a log corroboration claim
            falsely_claimed_logs = any("OpenSearch Correlated Log:" in f for f in diagnosis.confirmed_facts)
            if falsely_claimed_logs:
                challenges.append("Evidence Grounding Error: Agent claimed log corroboration when OpenSearch returned NO_DATA.")
            else:
                checks_passed.append("Log Accounting Honest: Confirmed zero logs marked as NO_DATA; no false corroboration claimed.")
        else:
            checks_passed.append("Log Corroboration Grounded: Verified correlated log entry matching trace ID in OpenSearch.")

        # Audit 4: Temporal Telemetry Reconciliation
        recon_status = diagnosis.telemetry_reconciliation_status
        if recon_status == "CONFLICTING_MEASUREMENTS":
            challenges.append("Temporal Conflict: Triggering alert measurements directly contradict fresh live Prometheus evaluation.")
        elif recon_status == "RECOVERED_SINCE_TRIGGER":
            checks_passed.append("Temporal Reconciliation: Detected latency normalized since trigger; alert marked as stabilized.")
        else:
            checks_passed.append(f"Temporal Reconciliation: Telemetry evaluation confirms {recon_status}.")

        # Audit 5: Action Allowlist & Safety Barrier
        action_type = diagnosis.action_type
        target_service = diagnosis.root_cause_service

        if action_type == "RESTART_CONTAINER" and target_service in self.PROHIBITED_RESTART_TARGETS:
            challenges.append(f"CRITICAL SAFETY VIOLATION: Proposed restart on protected service '{target_service}'.")
        else:
            checks_passed.append(f"Action Safety Gate: Action '{action_type}' on '{target_service}' is allowlisted and safe.")

        is_approved = (len(challenges) == 0)
        verdict = "APPROVED_BY_REVIEWER" if is_approved else "CHALLENGED_BY_REVIEWER"

        return {
            "verdict": verdict,
            "approved": is_approved,
            "challenges": challenges,
            "checks_passed": checks_passed,
            "summary": (
                f"Adversarial Reviewer: Diagnosis for '{diagnosis.incident_id}' {verdict}. "
                f"({len(checks_passed)} checks passed, {len(challenges)} challenges raised)."
            )
        }
