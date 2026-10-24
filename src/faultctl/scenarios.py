# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Predefined incident drill scenarios matching hackathon practice faults."""

SCENARIOS = {
    "payment-fail": {
        "description": "Payment service fails 100% of charges",
        "flags": {"paymentFailure": "100%"},
    },
    "payment-intermittent": {
        "description": "Payment service fails 50% of charges",
        "flags": {"paymentFailure": "50%"},
    },
    "payment-down": {
        "description": "Payment service is unreachable",
        "flags": {"paymentUnreachable": "on"},
    },
    "cart-fail": {
        "description": "Cart service fails 50% of requests",
        "flags": {"cartFailure": "50%"},
    },
    "catalog-fail": {
        "description": "Product catalog fails for product OLJCESPC7Z",
        "flags": {"productCatalogFailure": "on"},
    },
    "catalog-lock": {
        "description": "Product catalog database lock contention",
        "flags": {"productCatalogLockContention": "on"},
    },
    "ad-high-cpu": {
        "description": "Ad service CPU spikes to 100%",
        "flags": {"adHighCpu": "on"},
    },
    "ad-gc": {
        "description": "Ad service continuous manual GC (JVM stop-the-world)",
        "flags": {"adManualGc": "on"},
    },
    "email-leak": {
        "description": "Email service memory leak (1000x multiplier)",
        "flags": {"emailMemoryLeak": "1000x"},
    },
    "kafka-dead": {
        "description": "Fraud-detection Kafka consumer leaves group, lag climbs",
        "flags": {"kafkaConsumerDead": "on"},
    },
    "kafka-lag": {
        "description": "Fraud-detection Kafka consumer throttled (3s per record)",
        "flags": {"kafkaQueueProblems": "3sec"},
    },
    "shipping-slow": {
        "description": "International shipping responses delayed 10 seconds",
        "flags": {"intlShippingSlowdown": "10sec"},
    },
    "image-slow": {
        "description": "Product images load with 10-second delay",
        "flags": {"imageSlowLoad": "10sec"},
    },
    "traffic-flood": {
        "description": "Load generator floods homepage with 100 concurrent users",
        "flags": {"loadGeneratorFloodHomepage": "on"},
    },
    "ai-runaway": {
        "description": "AI agent loops tool calls until recursion limit",
        "flags": {"aiRunawayAgent": "on"},
    },
    "ai-slow": {
        "description": "AI agent LLM responses delayed 10 seconds",
        "flags": {"aiSlowResponse": "10sec"},
    },
    "readiness-fail": {
        "description": "Cart service readiness probe failure",
        "flags": {"failedReadinessProbe": "on"},
    },
    "cardinality-overflow": {
        "description": "Cart metric cardinality overflow (traceId in labels)",
        "flags": {"cartMetricCardinalityOverflow": "on"},
    },
}
