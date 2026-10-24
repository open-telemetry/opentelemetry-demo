# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
Incident Prevention Engine (Stretch Goal 5 & Slide 2 Requirement).
Synthesizes actionable engineering recommendations to prevent recurring outages:
1. Code & Architectural Resilience
2. Configuration & Infrastructure Tuning
3. Observability & Alerting Refinements
"""

from typing import Dict, Any, List
from oncall.models import RootCauseDiagnosis


class PreventionEngine:
    @staticmethod
    def generate_recommendations(diagnosis: RootCauseDiagnosis) -> Dict[str, Any]:
        """Generates concrete preventive recommendations to stop recurrence."""
        culprit = diagnosis.root_cause_service

        if culprit == "cart":
            return {
                "service": "cart",
                "code_improvements": [
                    "Implement asynchronous connection pooling in StackExchange.Redis / Valkey client.",
                    "Wrap datastore calls in a Polly circuit breaker with exponential backoff and jitter."
                ],
                "configuration_tuning": [
                    "Increase Valkey connection timeout from 2000ms to 5000ms for batch cart writes.",
                    "Configure memory eviction policy on valkey-cart to volatile-lru."
                ],
                "alerting_rules": [
                    "Add Prometheus burn-rate alert on 'valkey_client_timeout_total' > 5 over 2m.",
                    "Track 99th percentile Redis command execution latency."
                ]
            }

        elif culprit == "payment":
            return {
                "service": "payment",
                "code_improvements": [
                    "Introduce an idempotent fallback queue for declined or timeout transactions.",
                    "Add gRPC client-side retry policy with hedged requests for payment processing."
                ],
                "configuration_tuning": [
                    "Implement request timeout deadlines on gRPC PaymentService client (max 1500ms).",
                    "Configure autoscaling threshold on payment service pods based on active gRPC channels."
                ],
                "alerting_rules": [
                    "Alert on downstream payment gateway HTTP 503 / UNAVAILABLE rate exceeding 1%.",
                    "Monitor checkout-to-payment RPC latency divergence."
                ]
            }

        elif culprit == "ad":
            return {
                "service": "ad",
                "code_improvements": [
                    "Optimize AdService thread pool allocation to prevent worker exhaustion.",
                    "Refactor ad category cache to avoid runaway heap allocation."
                ],
                "configuration_tuning": [
                    "Tune JVM garbage collector: switch to G1GC with -XX:MaxGCPauseMillis=200.",
                    "Increase container heap allocation memory limits to prevent GC thrashing."
                ],
                "alerting_rules": [
                    "Alert on JVM GC pause duration exceeding 500ms.",
                    "Add JVM thread contention metrics to OpenTelemetry dashboard."
                ]
            }

        else:
            return {
                "service": culprit,
                "code_improvements": [
                    f"Audit {culprit} error handling and ensure graceful degradation on dependency failure."
                ],
                "configuration_tuning": [
                    f"Review CPU and memory requests/limits in Kubernetes manifests for {culprit}."
                ],
                "alerting_rules": [
                    f"Create multi-window SLO burn-rate alert for service '{culprit}'."
                ]
            }
