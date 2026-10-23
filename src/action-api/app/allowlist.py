from typing import Any

RESTART_ALLOWLIST: set[str] = {
    "ad",
    "cart",
    "checkout",
    "currency",
    "email",
    "frontend",
    "image-provider",
    "payment",
    "product-catalog",
    "quote",
    "recommendation",
    "shipping",
    "accounting",
    "fraud-detection",
    "kafka",
    "valkey-cart",
    "astronomy-db",
}

RESTART_BLOCKLIST: set[str] = {
    "otel-collector",
    "prometheus",
    "jaeger",
    "opensearch",
    "flagd",
    "flagd-ui",
    "action-api",
    "oncall-agent",
}

RUNBOOK_FLAGS: set[str] = {
    "adFailure",
    "adHighCpu",
    "adManualGc",
    "aiRunawayAgent",
    "aiSlowResponse",
    "cartFailure",
    "cartMetricCardinalityOverflow",
    "emailMemoryLeak",
    "emitRawPii",
    "failedReadinessProbe",
    "imageSlowLoad",
    "intlShippingSlowdown",
    "kafkaConsumerDead",
    "kafkaQueueProblems",
    "loadGeneratorFloodHomepage",
    "paymentFailure",
    "paymentUnreachable",
    "productCatalogFailure",
    "productCatalogLockContention",
    "recommendationCacheFailure",
}

FLAG_SERVICE_MAP: dict[str, str] = {
    "adFailure": "ad",
    "adHighCpu": "ad",
    "adManualGc": "ad",
    "aiRunawayAgent": "agent",
    "aiSlowResponse": "agent",
    "cartFailure": "cart",
    "cartMetricCardinalityOverflow": "cart",
    "emailMemoryLeak": "email",
    "emitRawPii": "checkout",
    "failedReadinessProbe": "cart",
    "imageSlowLoad": "frontend",
    "intlShippingSlowdown": "shipping",
    "kafkaConsumerDead": "fraud-detection",
    "kafkaQueueProblems": "fraud-detection",
    "loadGeneratorFloodHomepage": "frontend",
    "paymentFailure": "payment",
    "paymentUnreachable": "payment",
    "productCatalogFailure": "product-catalog",
    "productCatalogLockContention": "product-catalog",
    "recommendationCacheFailure": "recommendation",
}


def is_service_restart_allowed(service: str) -> tuple[bool, str]:
    if not service or not isinstance(service, str):
        return False, "Service name must be a non-empty string"
    if service in RESTART_BLOCKLIST:
        return False, f"Service '{service}' is protected and cannot be restarted"
    if service not in RESTART_ALLOWLIST:
        return False, f"Service '{service}' is not in the restart allowlist"
    return True, ""


def is_flag_allowed(flag: str, variant: str) -> tuple[bool, str]:
    if not flag or not isinstance(flag, str):
        return False, "Flag name must be a non-empty string"
    if flag not in RUNBOOK_FLAGS:
        return False, f"Flag '{flag}' is not in runbook flag list"
    if variant != "off":
        return False, "Only off/default variant is allowed via Action API"
    return True, ""


def is_throttle_allowed(users: Any, spawn_rate: Any) -> tuple[bool, str]:
    try:
        u = int(users)
        sr = float(spawn_rate)
    except (TypeError, ValueError):
        return False, "users and spawn_rate must be numeric"
    if u < 1:
        return False, "users must be >= 1"
    if sr < 0.1:
        return False, "spawn_rate must be >= 0.1"
    return True, ""


def get_action_service(action: str, params: dict[str, Any]) -> str:
    if action == "restart_service":
        return str(params.get("service", "unknown"))
    if action == "set_feature_flag":
        flag = str(params.get("flag", ""))
        return FLAG_SERVICE_MAP.get(flag, flag or "flagd")
    if action == "throttle_load_generator":
        return "load-generator"
    if action == "scale_service":
        return str(params.get("service", "unknown"))
    if action == "rollback":
        return "rollback"
    return "unknown"
