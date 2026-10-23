# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Flag domain model: reading, mutating, and inspecting flagd configuration."""

import copy
import json
from pathlib import Path

# Mapping from flag key to the service(s) it affects.
FLAG_SERVICE_MAP = {
    "adFailure": "ad",
    "adHighCpu": "ad",
    "adManualGc": "ad",
    "aiRunawayAgent": "agent",
    "aiSlowResponse": "agent",
    "cartFailure": "cart",
    "cartMetricCardinalityOverflow": "cart",
    "emailMemoryLeak": "email",
    "emitRawPii": "checkout / payment",
    "failedReadinessProbe": "cart",
    "imageSlowLoad": "image-provider",
    "intlShippingSlowdown": "shipping",
    "kafkaConsumerDead": "fraud-detection",
    "kafkaQueueProblems": "fraud-detection",
    "loadGeneratorFloodHomepage": "load-generator",
    "paymentFailure": "payment",
    "paymentUnreachable": "checkout / payment",
    "productCatalogFailure": "product-catalog",
    "productCatalogLockContention": "product-catalog",
    "recommendationCacheFailure": "recommendation",
}

DEFAULT_FLAG_FILE = Path(__file__).resolve().parent.parent / "flagd" / "demo.flagd.json"


def load_config(path=None):
    """Load and parse the flagd JSON configuration file."""
    p = Path(path) if path else DEFAULT_FLAG_FILE
    return json.loads(p.read_text(encoding="utf-8"))


def save_config(config, path=None):
    """Atomically write the flagd JSON configuration file."""
    p = Path(path) if path else DEFAULT_FLAG_FILE
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)


def get_variants(flag_data):
    """Return the sorted list of variant names for a flag."""
    return sorted(flag_data.get("variants", {}).keys())


RESTING_VARIANT = "off"


def get_resting_variant(_flag_data=None):
    """Return the resting variant name.

    Every failure flag in the demo rests at ``"off"``.  The flagd-ui
    Storage GenServer overwrites ``defaultVariant`` with the *currently
    selected* variant, so we cannot read the resting state from the
    config after a mutation — it is always the constant ``"off"``.
    """
    return RESTING_VARIANT


def has_targeting(flag_data):
    """Return True if the flag uses a targeting rule (e.g. productCatalogFailure)."""
    targeting = flag_data.get("targeting", {}).get("if")
    return isinstance(targeting, list) and len(targeting) >= 3


def get_active_variant(flag_data):
    """Return the currently active variant name.

    For targeted flags this is ``targeting.if[1]``; for standard flags it
    is ``defaultVariant`` (which the flagd-ui Storage overwrites to the
    selected variant).
    """
    if has_targeting(flag_data):
        return flag_data["targeting"]["if"][1]
    return flag_data["defaultVariant"]


def is_active(flag_data):
    """Return True if the flag is set to something other than its resting variant."""
    active = get_active_variant(flag_data)
    return active != RESTING_VARIANT


def set_flag(config, flag_name, variant):
    """Set *flag_name* to *variant* in *config* (mutates in place).

    Mirrors the update logic in ``FlagdUi.Storage.update_flag/3``:
    targeted flags update ``targeting.if[1]``; standard flags update
    ``defaultVariant``.

    Raises ``KeyError`` for an unknown flag and ``ValueError`` for an
    unknown variant.
    """
    flags = config.get("flags", {})
    if flag_name not in flags:
        raise KeyError(f"Unknown flag: {flag_name}")

    flag_data = flags[flag_name]
    variants = get_variants(flag_data)
    if variant not in variants:
        raise ValueError(
            f"Invalid variant '{variant}' for {flag_name}. "
            f"Valid variants: {', '.join(variants)}"
        )

    if has_targeting(flag_data):
        flag_data["targeting"]["if"][1] = variant
    else:
        flag_data["defaultVariant"] = variant


def clear_flag(config, flag_name):
    """Reset *flag_name* back to its resting (off) variant."""
    flags = config.get("flags", {})
    if flag_name not in flags:
        raise KeyError(f"Unknown flag: {flag_name}")
    resting = get_resting_variant(flags[flag_name])
    set_flag(config, flag_name, resting)


def reset_all(config):
    """Reset every flag in *config* back to its resting variant."""
    for name in list(config.get("flags", {}).keys()):
        clear_flag(config, name)


def trigger_all(config):
    """Activate every flag to its first non-resting variant."""
    for name, data in config.get("flags", {}).items():
        resting = get_resting_variant(data)
        activatable = [v for v in get_variants(data) if v != resting]
        if activatable:
            set_flag(config, name, activatable[0])


def flag_summary(config):
    """Return a list of dicts summarising every flag's current state."""
    rows = []
    for name in sorted(config.get("flags", {}).keys()):
        data = config["flags"][name]
        rows.append({
            "name": name,
            "service": FLAG_SERVICE_MAP.get(name, "unknown"),
            "description": data.get("description", ""),
            "active_variant": get_active_variant(data),
            "resting_variant": get_resting_variant(data),
            "is_active": is_active(data),
            "variants": get_variants(data),
            "has_targeting": has_targeting(data),
        })
    return rows
