# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0
"""Recovery verification using post-remediation evidence."""

from datetime import datetime, timezone
import time
from typing import Callable

from .models import VerificationResult, utc_now_iso


class RecoveryVerifier:
    def __init__(self, query_fn: Callable[[str, str, str, str], dict] | None = None):
        self.query_fn = query_fn

    def verify(
        self,
        incident_id: str,
        plan_digest: str,
        action_time_iso: str,
        criteria: dict,
        target_service: str,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> VerificationResult:
        settling_seconds = float(criteria.get("settling_period_seconds", 0.0))
        if settling_seconds > 0:
            sleep_fn(settling_seconds)

        now_iso = utc_now_iso()
        metric_name = criteria.get("metric", "error_rate")
        threshold = float(criteria.get("threshold", 0.05))
        min_samples = int(criteria.get("min_samples", 1))

        if not self.query_fn:
            return VerificationResult(
                verdict=VerificationResult.INCONCLUSIVE,
                incident_id=incident_id,
                plan_digest=plan_digest,
                verified_at=now_iso,
                observed_samples=[],
                summary="No telemetry query provider configured for verification.",
            )

        try:
            res = self.query_fn(target_service, metric_name, action_time_iso, now_iso)
        except Exception as ex:
            return VerificationResult(
                verdict=VerificationResult.INCONCLUSIVE,
                incident_id=incident_id,
                plan_digest=plan_digest,
                verified_at=now_iso,
                observed_samples=[],
                summary=f"Failed to query verification telemetry: {ex}",
            )

        if res.get("status") != "ok":
            return VerificationResult(
                verdict=VerificationResult.INCONCLUSIVE,
                incident_id=incident_id,
                plan_digest=plan_digest,
                verified_at=now_iso,
                observed_samples=[],
                summary=f"Telemetry returned non-ok status: {res.get('status')} ({res.get('warnings', [])})",
            )

        observations = res.get("observations", [])
        if not observations:
            return VerificationResult(
                verdict=VerificationResult.INCONCLUSIVE,
                incident_id=incident_id,
                plan_digest=plan_digest,
                verified_at=now_iso,
                observed_samples=[],
                summary="No metric observations returned for verification window.",
            )

        samples = observations[0].get("samples", [])
        post_action_samples = []
        for s in samples:
            s_time = s.get("timestamp", "")
            if s_time >= action_time_iso:
                post_action_samples.append(s)

        if len(post_action_samples) < min_samples:
            return VerificationResult(
                verdict=VerificationResult.INCONCLUSIVE,
                incident_id=incident_id,
                plan_digest=plan_digest,
                verified_at=now_iso,
                observed_samples=post_action_samples,
                summary=f"Insufficient post-action samples: got {len(post_action_samples)}, required {min_samples}.",
            )

        # Check threshold
        values = [float(s.get("value", 0.0)) for s in post_action_samples]
        operator = criteria.get("comparison", "<=")
        
        all_passed = True
        for val in values:
            if operator == "<=" and not (val <= threshold):
                all_passed = False
            elif operator == "<" and not (val < threshold):
                all_passed = False
            elif operator == "==" and not (val == threshold):
                all_passed = False

        if all_passed:
            verdict = VerificationResult.RECOVERED
            summary = f"All {len(values)} post-action samples met threshold {operator} {threshold} (values: {values})."
        else:
            verdict = VerificationResult.NOT_RECOVERED
            summary = f"One or more post-action samples breached threshold {operator} {threshold} (values: {values})."

        return VerificationResult(
            verdict=verdict,
            incident_id=incident_id,
            plan_digest=plan_digest,
            verified_at=now_iso,
            observed_samples=post_action_samples,
            summary=summary,
        )
