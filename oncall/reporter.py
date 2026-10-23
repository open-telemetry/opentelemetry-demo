# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
Structured Incident Post-Mortem and Evaluation Reporter.
Includes categorized evidence: Confirmed Facts, Likely Causes, and Ruled Out Hypotheses.
"""

from datetime import datetime, timezone
from typing import Dict, Any
from oncall.models import IncidentAlert, RootCauseDiagnosis


class IncidentReporter:
    @staticmethod
    def generate_markdown_report(
        alert: IncidentAlert,
        diagnosis: RootCauseDiagnosis,
        approval: Dict[str, Any],
        execution: Dict[str, Any],
        verification: Dict[str, Any],
    ) -> str:
        """Produces a comprehensive Markdown incident post-mortem report."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        lines = []
        lines.append(f"# Incident Post-Mortem: {alert.title} ({alert.alert_id})")
        lines.append(f"**Report Generated**: `{now_str}`  ")
        lines.append(f"**Alerted Service**: `{alert.service_name}` | **Actual Culprit**: `{diagnosis.root_cause_service}`  ")
        lines.append(f"**Severity**: `{alert.severity.upper()}` | **Resolution Status**: `{'MITIGATED' if verification.get('recovered') else 'ESCALATED'}`\n")

        lines.append("## 1. Executive Summary")
        lines.append(f"- **Failure Mode**: `{diagnosis.failure_mode}`")
        lines.append(f"- **Confidence Score**: `{diagnosis.confidence_score * 100:.1f}%`")
        lines.append(f"- **Consistency Check**: `{'PASSED' if diagnosis.evidence_consistency_passed else 'FAILED'}`")
        lines.append(f"- **Detailed Explanation**: {diagnosis.explanation}\n")

        lines.append("## 2. Categorized Diagnostic Evidence")
        lines.append("### A. Confirmed Empirical Facts (Observed Telemetry)")
        for f in diagnosis.confirmed_facts:
            lines.append(f"- {f}")
        lines.append("")

        lines.append("### B. Likely Inferred Causes")
        for lc in diagnosis.likely_causes:
            lines.append(f"- {lc}")
        lines.append("")

        lines.append("### C. Ruled Out or Pending Hypotheses")
        for uh in diagnosis.unresolved_hypotheses:
            lines.append(f"- {uh}")
        lines.append("")

        lines.append("## 3. Investigation Timeline & Telemetry Citations")
        lines.append("| Step | Tool Executed | Key Observation |")
        lines.append("| :--- | :--- | :--- |")
        for step in diagnosis.investigation_steps:
            lines.append(f"| {step.step_number} | `{step.tool_name}` | {step.observation.summary[:100]}... |")
        lines.append("")

        lines.append("### Grounding Telemetry Citations")
        for idx, c in enumerate(diagnosis.citations, 1):
            lines.append(f"{idx}. **[{c.source_type.upper()}]** `{c.identifier}`: {c.summary}")
        lines.append("")

        lines.append("## 4. Safety Gates & Remediation Execution")
        lines.append(f"- **Consistency Validation**: `{'PASSED' if diagnosis.evidence_consistency_passed else 'FAILED'}`")
        lines.append(f"- **Approval Status**: `{'APPROVED' if approval.get('approved') else 'REJECTED'}` (Token: `{approval.get('token')}`)")
        lines.append(f"- **Authorized By**: `{approval.get('approver')}`")
        lines.append(f"- **Action Executed**: `{execution.get('action')}`")
        lines.append(f"- **Action Outcome**: {execution.get('message', execution.get('error'))}\n")

        lines.append("## 5. Post-Action Recovery Verification")
        lines.append(f"- **Recovery Proven**: `{'YES - STABILIZED' if verification.get('recovered') else 'NO'}`")
        lines.append(f"- **Verification Window**: `{verification.get('verification_duration_seconds', 0)} seconds`")
        if verification.get("citations"):
            for vc in verification["citations"]:
                lines.append(f"- **Verification Signal**: [{vc.source_type}] {vc.summary}")
        lines.append("")

        return "\n".join(lines)
