# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import sys
import tomllib
from pathlib import Path


def validate_report(contract, report):
    errors = []
    statistics = report.get("statistics") or {}
    entity_counts = statistics.get("total_entities_by_type") or {}

    if int(entity_counts.get("span", 0)) == 0:
        errors.append("Weaver did not observe any spans")

    violations = int(
        (statistics.get("advice_level_counts") or {}).get("violation", 0)
    )
    if violations:
        errors.append(f"Weaver reported {violations} violation(s)")

    expected = contract.get("expected") or {}
    observed_attributes = statistics.get("seen_registry_attributes") or {}
    observed_metrics = statistics.get("seen_registry_metrics") or {}

    missing_attributes = [
        name
        for name in expected.get("attributes", [])
        if int(observed_attributes.get(name, 0)) == 0
    ]
    if missing_attributes:
        errors.append(
            "Missing expected attributes: " + ", ".join(sorted(missing_attributes))
        )

    missing_metrics = [
        name
        for name in expected.get("metrics", [])
        if int(observed_metrics.get(name, 0)) == 0
    ]
    if missing_metrics:
        errors.append("Missing expected metrics: " + ", ".join(sorted(missing_metrics)))

    return errors


def main():
    parser = argparse.ArgumentParser(
        description="Check a Weaver live-check report against expected telemetry."
    )
    parser.add_argument("contract", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()

    with args.contract.open("rb") as contract_file:
        contract = tomllib.load(contract_file)
    with args.report.open(encoding="utf-8") as report_file:
        report = json.load(report_file)

    errors = validate_report(contract, report)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    statistics = report["statistics"]
    expected = contract["expected"]
    for signal, observed_key in (
        ("attributes", "seen_registry_attributes"),
        ("metrics", "seen_registry_metrics"),
    ):
        observed = statistics.get(observed_key) or {}
        for name in expected.get(signal, []):
            print(f"{signal[:-1]} {name}: {observed[name]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
