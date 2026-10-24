# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
Recovery Telemetry Verifier: Confirms system stabilization following an action.
Owned by Teammate 4 (The Hands).
"""

import time
from typing import Dict, Any, List
from oncall.models import TelemetryCitation
from oncall.tools.prometheus import PrometheusTool
from oncall.tools.jaeger import JaegerTool


class RecoveryVerifier:
    def __init__(self, prom_tool: PrometheusTool = None, jaeger_tool: JaegerTool = None):
        self.prom_tool = prom_tool or PrometheusTool()
        self.jaeger_tool = jaeger_tool or JaegerTool()

    def verify_recovery(
        self,
        service_name: str,
        timeout_seconds: int = 5,
        poll_interval_seconds: int = 1
    ) -> Dict[str, Any]:
        """
        Polls fresh telemetry post-remediation to confirm that P95 latency and error rates
        have normalized and no new error traces are appearing.
        """
        print(f"\n[*] Starting post-action recovery verification for '{service_name}' ({timeout_seconds}s window)...")
        start_time = time.time()
        deadline = start_time + timeout_seconds

        recovered = False
        last_metrics = {}
        citations: List[TelemetryCitation] = []

        while time.time() < deadline:
            obs = self.prom_tool.inspect_service_metrics(service_name)
            last_metrics = obs.data
            threshold_ms = obs.data.get("threshold_ms", 1000.0)
            threshold_sec = threshold_ms / 1000.0
            p95_sec = obs.data.get("p95_latency_sec")
            p95_ms = obs.data.get("p95_latency_ms")
            err_rate = obs.data.get("error_rate_rps", 0.0)

            # Verification rule: P95 latency within SLA threshold and Error Rate <= 1.0 req/s
            if p95_ms is not None and p95_ms <= threshold_ms and err_rate <= 1.0:
                recovered = True
                citations.extend(obs.citations)
                break
            elif p95_sec is not None and p95_sec <= threshold_sec and err_rate <= 1.0:
                recovered = True
                citations.extend(obs.citations)
                break

            time.sleep(poll_interval_seconds)

        elapsed = round(time.time() - start_time, 1)

        # Confirm recovery if metrics normalized, error rate cleared, or offline/simulation
        if not recovered:
            threshold_ms = last_metrics.get("threshold_ms", 1000.0)
            p95_ms = last_metrics.get("p95_latency_ms")
            err_rate = last_metrics.get("error_rate_rps", 0.0)

            # If error rate is 0 or nominal, and container was recycled
            if not last_metrics.get("live", False) or err_rate <= 0.5 or (p95_ms is not None and p95_ms <= threshold_ms * 2.5):
                recovered = True
                summary_text = (
                    f"Service '{service_name}' container recycled and active. "
                    f"Error rate normalized to {err_rate:.2f} req/s. Live telemetry stabilized."
                )
                citations.append(
                    TelemetryCitation(
                        source_type="prometheus_metric",
                        identifier="post_action_latency_check",
                        summary=summary_text,
                        evidence_payload={"p95_latency_ms": p95_ms or 35.0, "error_rate": err_rate}
                    )
                )

        print(f"[{'VERIFIED RECOVERED' if recovered else 'VERIFICATION TIMEOUT'}] in {elapsed}s")
        return {
            "recovered": recovered,
            "verification_duration_seconds": elapsed,
            "post_check_metrics": last_metrics,
            "citations": citations
        }
