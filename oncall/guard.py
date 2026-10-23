from __future__ import annotations

from typing import Any


def scrub(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            key: scrub(value)
            for key, value in obj.items()
            if not key.lower().startswith("feature_flag")
            and not (key.lower() == "name" and isinstance(value, str) and value.lower().startswith("feature_flag"))
        }
    if isinstance(obj, list):
        return [
            scrub(item)
            for item in obj
            if not (isinstance(item, str) and "feature_flag" in item.lower())
            and not (isinstance(item, dict) and _mentions_feature_flag(item))
        ]
    return obj


def _mentions_feature_flag(value: dict[str, Any]) -> bool:
    return any(
        "feature_flag" in str(key).lower() or "feature_flag" in str(item).lower()
        for key, item in value.items()
    )


def is_banned_service(name: str) -> bool:
    return name.lower() in {"flagd", "flagd-ui"}


def is_banned_text(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in ("flagd", "feature_flag", "ofrep", "/feature", "/flagservice", ":8013", ":8016"))
