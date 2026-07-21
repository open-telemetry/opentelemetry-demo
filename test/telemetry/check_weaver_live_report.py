# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import sys

EXPECTED_METRICS = {
    "demo.cart.add_item.latency",
    "demo.payment.transactions",
}


def positive_counts(values):
    return {name: count for name, count in values.items() if count > 0}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_weaver_live_report.py <live_check.json>")

    with open(sys.argv[1], encoding="utf-8") as report_file:
        report = json.load(report_file)
    stats = report.get("statistics", {}) or {}
    registry_attributes = positive_counts(stats.get("seen_registry_attributes", {}) or {})
    registry_metrics = positive_counts(stats.get("seen_registry_metrics", {}) or {})
    services = set()
    has_spans = False

    for sample in report.get("samples", []):
        resource = sample.get("resource")
        if resource:
            for attr in resource.get("attributes", []):
                if attr.get("name") == "service.name" and attr.get("value"):
                    services.add(str(attr["value"]))
        has_spans = has_spans or sample.get("span") is not None

    print("Weaver live-check summary")
    print(f"  total entities: {stats.get('total_entities', 0)}")
    print(f"  advice levels: {stats.get('advice_level_counts', {})}")
    print(f"  services: {sorted(services)}")
    print(f"  observed registry attributes: {registry_attributes}")
    print(f"  observed registry metrics: {registry_metrics}")

    if stats.get("total_entities", 0) <= 0:
        raise SystemExit("Weaver live-check report did not contain any entities")
    if not has_spans:
        raise SystemExit("Weaver live-check report did not contain any spans")
    if not registry_attributes:
        raise SystemExit("Weaver live-check did not observe any registry attributes")
    missing_metrics = EXPECTED_METRICS - registry_metrics.keys()
    if missing_metrics:
        raise SystemExit(
            f"Weaver live-check did not observe expected registry metrics: {sorted(missing_metrics)}"
        )

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("### Observed Demo telemetry\n\n")
            summary.write(f"- Services with matched telemetry: {', '.join(sorted(services))}\n")
            summary.write(f"- Matched registry attributes: {len(registry_attributes)}\n")
            summary.write(
                f"- Matched registry metrics: {', '.join(sorted(registry_metrics))}\n\n"
            )


if __name__ == "__main__":
    main()
