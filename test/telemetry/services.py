# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""
Service-signal matrix: single source of truth for which services emit which telemetry.

To add a new service: add an entry to SIGNAL_MATRIX.
To mark a service as full-only (Kafka-dependent): add it to FULL_ONLY_SERVICES.
"""

SIGNAL_MATRIX = {
    "ad": {"traces": True, "metrics": True, "logs": True},
    "cart": {"traces": True, "metrics": True, "logs": True},
    "checkout": {"traces": True, "metrics": True, "logs": True},
    "currency": {"traces": True, "metrics": True, "logs": True},
    "email": {"traces": True, "metrics": True, "logs": True},
    "frontend": {"traces": True, "metrics": True, "logs": False},
    "frontend-proxy": {"traces": True, "metrics": True, "logs": True},
    "frontend-web": {"traces": True, "metrics": True, "logs": False},
    "image-provider": {"traces": True, "metrics": True, "logs": False},
    "kafka": {"traces": False, "metrics": True, "logs": True},
    "payment": {"traces": True, "metrics": True, "logs": True},
    "product-catalog": {"traces": True, "metrics": True, "logs": True},
    "product-reviews": {"traces": True, "metrics": True, "logs": True},
    "quote": {"traces": True, "metrics": True, "logs": True},
    "recommendation": {"traces": True, "metrics": True, "logs": True},
    "shipping": {"traces": True, "metrics": True, "logs": True},
    "accounting": {"traces": True, "metrics": True, "logs": True},
    "fraud-detection": {"traces": True, "metrics": True, "logs": True},
    "load-generator": {"traces": True, "metrics": True, "logs": True},
}

# Services excluded from minimal scope:
# - accounting, fraud-detection, kafka: require Kafka (not in minimal compose)
# - frontend-web: requires LOCUST_BROWSER_TRAFFIC_ENABLED=true (disabled in minimal)
# - product-reviews: load-generator rarely hits the product reviews API path
#   without browser traffic, so traces don't appear within the test timeout
FULL_ONLY_SERVICES = {"accounting", "fraud-detection", "frontend-web", "kafka", "product-reviews"}

MINIMAL_SERVICES = [s for s in SIGNAL_MATRIX if s not in FULL_ONLY_SERVICES]
ALL_SERVICES = list(SIGNAL_MATRIX.keys())


def services_for_scope(scope: str) -> list[str]:
    """Return service list based on test scope."""
    if scope == "full":
        return ALL_SERVICES
    return MINIMAL_SERVICES


def services_with_signal(signal: str, scope: str = "minimal") -> list[str]:
    """Return services that emit a given signal within the specified scope."""
    return [
        svc
        for svc in services_for_scope(scope)
        if SIGNAL_MATRIX[svc].get(signal, False)
    ]
