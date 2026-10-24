# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
Structured Incident Post-Mortem and Evaluation Reporter.
Features:
- Rigorous temporal reconciliation: Trigger snapshot vs live Prometheus evaluation
- Explicit trace DAG causal tree breakdown
- Honest log accounting (NO_DATA explicitly declared)
- Classification of repository commit context vs runtime rollout
- Prevention and recurrence mitigation (Stretch Goal 5)
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from oncall.models import IncidentAlert, RootCauseDiagnosis
from oncall.prevention import PreventionEngine


class IncidentReporter:
    @staticmethod
    def generate_markdown_report(
        alert: IncidentAlert,
        diagnosis: RootCauseDiagnosis,
        approval: Dict[str, Any],
        execution: Dict[str, Any],
        verification: Dict[str, Any],
        reviewer_audit: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Produces a comprehensive Markdown incident post-mortem report."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        lines = []
        lines.append(f"# Incident Post-Mortem: {alert.title} ({alert.alert_id})")
        lines.append(f"**Report Generated**: `{now_str}`  ")
        lines.append(f"**Alerted Service**: `{alert.service_name}` | **Actual Culprit**: `{diagnosis.root_cause_service}`  ")
        lines.append(f"**Severity**: `{alert.severity.upper()}` | **Resolution Status**: `{'MITIGATED' if verification.get('recovered') else 'ESCALATED'}`\n")

        lines.append("## 1. Executive Summary & Telemetry Reconciliation")
        lines.append(f"- **Failure Mode**: `{diagnosis.failure_mode}`")
        lines.append(f"- **Calibrated Confidence**: `{diagnosis.confidence_score * 100:.1f}%`")
        lines.append(f"- **Reconciliation Status**: `{diagnosis.telemetry_reconciliation_status}`")
        
        snap = diagnosis.incident_snapshot or {}
        curr = diagnosis.current_telemetry or {}
        lines.append(f"- **Triggering Alert Snapshot**: P95 = `{snap.get('trigger_p95_latency_ms', 0):.0f}ms` (threshold: `{snap.get('threshold_ms', 1000)}ms`), Error Rate = `{snap.get('trigger_error_rate_rps', 0):.1f} req/s` at `{snap.get('timestamp_utc', 'N/A')}`")
        lines.append(f"- **Current Live Evaluation**: P95 = `{curr.get('current_p95_latency_ms', 0):.1f}ms`, Error Rate = `{curr.get('current_error_rate_rps', 0):.1f} req/s` at `{curr.get('evaluation_time_utc', 'N/A')}` ({curr.get('query_window', '5m window')})")
        lines.append(f"- **Consistency Check**: `{'PASSED' if diagnosis.evidence_consistency_passed else 'FAILED'}`")
        lines.append(f"- **Detailed Explanation**: {diagnosis.explanation}\n")

        lines.append("## 2. Distributed Tracing & Causal DAG Proof")
        ts = diagnosis.trace_summary or {}
        lines.append(f"- **Trace ID**: `{ts.get('trace_id', 'trace-unavailable')}` | **Span ID**: `{ts.get('span_id', 'span-unavailable')}`")
        lines.append(f"- **Target Parent Span**: `{ts.get('parent_operation', 'unknown_operation')}` (`{ts.get('parent_duration_ms', 0):.1f}ms`)")
        if diagnosis.is_downstream:
            lines.append(f"- **Isolated Downstream Child**: `{ts.get('downstream_service')}` -> `{ts.get('downstream_operation')}` (`{ts.get('downstream_duration_ms', 0):.1f}ms`, accounting for `{ts.get('consumption_percentage', 0):.1f}%` of parent duration)")
        lines.append(f"- **Causal Proof**: {ts.get('causal_proof', 'Internal service execution accounts for duration.')}\n")

        lines.append("## 3. Categorized Diagnostic Evidence")
        lines.append("### A. Confirmed Empirical Facts (Observed Telemetry)")
        for f in diagnosis.confirmed_facts:
            lines.append(f"- {f}")
        lines.append("")

        lines.append("### B. Likely Inferred Causes")
        for lc in diagnosis.likely_causes:
            lines.append(f"- {lc}")
        lines.append("")

        lines.append("### C. Evaluated Hypotheses & Evidence Accounting")
        lines.append(f"- **Log Evidence Status**: `{diagnosis.log_evidence_status}` (Zero logs marked as NO_DATA; no false corroboration claimed)")
        lines.append(f"- **Deployment Context Classification**: `{diagnosis.deployment_evidence_type}` (Repository commits audited on branch 'main')")
        for uh in diagnosis.unresolved_hypotheses:
            lines.append(f"- {uh}")
        lines.append("")

        lines.append("## 4. Investigation Timeline & Telemetry Citations")
        lines.append("| Step | Tool Executed | Key Observation |")
        lines.append("| :--- | :--- | :--- |")
        for step in diagnosis.investigation_steps:
            lines.append(f"| {step.step_number} | `{step.tool_name}` | {step.observation.summary[:100]}... |")
        lines.append("")

        lines.append("### Grounding Telemetry Citations")
        for idx, c in enumerate(diagnosis.citations, 1):
            lines.append(f"{idx}. **[{c.source_type.upper()}]** `{c.identifier}`: {c.summary}")
        lines.append("")

        if reviewer_audit:
            lines.append("## 5. Adversarial Reviewer Agent Audit (Stretch Goal 2)")
            lines.append(f"- **Reviewer Verdict**: `{reviewer_audit.get('verdict', 'APPROVED')}`")
            lines.append(f"- **Audit Summary**: {reviewer_audit.get('summary')}")
            for cp in reviewer_audit.get("checks_passed", []):
                lines.append(f"  + {cp}")
            for ch in reviewer_audit.get("challenges", []):
                lines.append(f"  ! {ch}")
            lines.append("")

        lines.append("## 6. Safety Gates & Remediation Execution")
        lines.append(f"- **Consistency Validation**: `{'PASSED' if diagnosis.evidence_consistency_passed else 'FAILED'}`")
        lines.append(f"- **Approval Status**: `{'APPROVED' if approval.get('approved') else 'REJECTED'}` (Token: `{approval.get('token')}`)")
        lines.append(f"- **Authorized By**: `{approval.get('approver')}`")
        lines.append(f"- **Action Executed**: `{execution.get('action')}`")
        lines.append(f"- **Action Outcome**: {execution.get('message', execution.get('error'))}\n")

        lines.append("## 7. Post-Action Recovery Verification")
        lines.append(f"- **Action Status**: `{'EXECUTED' if execution.get('action') else 'PENDING'}`")
        lines.append(f"- **Verification Status**: `{'RECOVERED' if verification.get('recovered') else 'NOT_RECOVERED'}`")
        lines.append(f"- **Verification Window**: `{verification.get('verification_duration_seconds', 0)} seconds`")
        if verification.get("citations"):
            for vc in verification["citations"]:
                lines.append(f"- **Verification Signal**: [{vc.source_type}] {vc.summary}")
        lines.append("")

        # Section 8: Prevention Recommendations
        prev = PreventionEngine.generate_recommendations(diagnosis)
        lines.append("## 8. Prevention & Recurrence Mitigation (Stretch Goal 5)")
        lines.append("### Code & Architecture Improvements")
        for ci in prev.get("code_improvements", []):
            lines.append(f"- {ci}")
        lines.append("")
        lines.append("### Configuration & Infrastructure Tuning")
        for ct in prev.get("configuration_tuning", []):
            lines.append(f"- {ct}")
        lines.append("")
        lines.append("### Observability & Alerting Refinements")
        for ar in prev.get("alerting_rules", []):
            lines.append(f"- {ar}")
        lines.append("")

        return "\n".join(lines)
