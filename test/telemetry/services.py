# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""
Service-signal matrix: single source of truth for which services emit which telemetry.

To add a new service: add an entry to SIGNAL_MATRIX.
To mark a service as full-only (Kafka-dependent): add it to FULL_ONLY_SERVICES.
To mark a service as agentic-only (compose.agent.yaml): add it to AGENTIC_ONLY_SERVICES.
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
    "quote": {"traces": True, "metrics": True, "logs": True},
    "recommendation": {"traces": True, "metrics": True, "logs": True},
    "shipping": {"traces": True, "metrics": True, "logs": True},
    "accounting": {"traces": True, "metrics": True, "logs": True},
    "fraud-detection": {"traces": True, "metrics": True, "logs": True},
    "load-generator": {"traces": True, "metrics": True, "logs": True},
    # Agentic services (compose.agent.yaml only): traces via Traceloop SDK /
    # OTel SDK; no OTLP metrics or log exporters configured.
    "agent":   {"traces": True, "metrics": False, "logs": False},
    "mcp":     {"traces": True, "metrics": False, "logs": False},
    "chatbot": {"traces": True, "metrics": False, "logs": False},
}

# Services excluded from minimal scope:
# - accounting, fraud-detection, kafka: require Kafka (not in minimal compose)
# - frontend-web: requires LOCUST_BROWSER_TRAFFIC_ENABLED=true (disabled in minimal)
#   without browser traffic, so traces don't appear within the test timeout
FULL_ONLY_SERVICES = {"accounting", "fraud-detection", "frontend-web", "kafka"}

# Services that only run when compose.agent.yaml is included (make start-agentic).
# Excluded from minimal/full scopes; covered by the agentic scope.
AGENTIC_ONLY_SERVICES = {"agent", "mcp", "chatbot"}

MINIMAL_SERVICES = [s for s in SIGNAL_MATRIX if s not in FULL_ONLY_SERVICES and s not in AGENTIC_ONLY_SERVICES]
ALL_SERVICES = [s for s in SIGNAL_MATRIX if s not in AGENTIC_ONLY_SERVICES]
AGENTIC_SERVICES = [s for s in SIGNAL_MATRIX if s in AGENTIC_ONLY_SERVICES]


def services_for_scope(scope: str) -> list[str]:
    """Return service list based on test scope."""
    if scope == "full":
        return ALL_SERVICES
    if scope == "agentic":
        return AGENTIC_SERVICES
    return MINIMAL_SERVICES


def services_with_signal(signal: str, scope: str = "minimal") -> list[str]:
    """Return services that emit a given signal within the specified scope."""
    return [
        svc
        for svc in services_for_scope(scope)
        if SIGNAL_MATRIX[svc].get(signal, False)
    ]


# Directed inter-service edges expected to appear in trace data:
# `parent` emits a span that has a direct child span belonging to `child`.
# Edges referencing any FULL_ONLY_SERVICES service run only in the full scope.
SERVICE_EDGES = [
    # Frontend fan-out (gRPC)
    ("frontend", "ad"),
    ("frontend", "recommendation"),
    ("frontend", "product-catalog"),
    ("frontend", "cart"),
    ("frontend", "checkout"),
    # frontend->currency intentionally omitted: the only path that triggers it
    # is the browser-driven currency-change task in load-generator (full scope
    # only, browser traffic). checkout->currency below covers currency reach.
    # Checkout fan-out
    ("checkout", "cart"),
    ("checkout", "payment"),
    ("checkout", "shipping"),         # HTTP
    ("checkout", "email"),            # HTTP
    ("checkout", "product-catalog"),
    ("checkout", "currency"),
    # Other sync
    ("recommendation", "product-catalog"),
    ("shipping", "quote"),            # HTTP
    # Note: async Kafka edges (checkout->accounting, checkout->fraud-detection)
    # are intentionally excluded. The OTel auto-instrumentation here records
    # producer spans on `checkout` and consumer spans on accounting /
    # fraud-detection, but does not link them via parent-child references --
    # they live in separate traces. Asserting their existence requires a
    # different pattern than the parent->child walker used here.
]

# Directed edges expected in the agentic service graph:
# chatbot calls agent via HTTP (RequestsInstrumentor injects traceparent).
# Note: the agent->mcp edge requires MCP_ENABLED=True and a cassette recorded
# with MCP tools; it is not asserted here to keep the default test run stable.
AGENTIC_EDGES = [
    ("chatbot", "agent"),
]


def edges_for_scope(scope: str) -> list[tuple[str, str]]:
    """Return the inter-service edges applicable to the given scope."""
    if scope == "full":
        return SERVICE_EDGES
    if scope == "agentic":
        return AGENTIC_EDGES
    return [
        (p, c) for p, c in SERVICE_EDGES
        if p not in FULL_ONLY_SERVICES and c not in FULL_ONLY_SERVICES
    ]
