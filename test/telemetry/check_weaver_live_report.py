# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import json
import sys
from collections import Counter


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_weaver_live_report.py <live_check.json>")

    report = json.load(open(sys.argv[1], encoding="utf-8"))
    stats = report.get("statistics", {}) or {}
    services = Counter()
    spans = Counter()

    for sample in report.get("samples", []):
        resource = sample.get("resource")
        if resource:
            for attr in resource.get("attributes", []):
                if attr.get("name") == "service.name" and attr.get("value"):
                    services[str(attr["value"])] += 1
        span = sample.get("span")
        if span:
            spans[str(span.get("name"))] += 1

    print("Weaver live-check summary")
    print(f"  total entities: {stats.get('total_entities', 0)}")
    print(f"  advice levels: {stats.get('advice_level_counts', {})}")
    print(f"  services: {dict(services)}")
    print(f"  top spans: {spans.most_common(10)}")

    if stats.get("total_entities", 0) <= 0:
        raise SystemExit("Weaver live-check report did not contain any entities")
    if len(services) < 2:
        raise SystemExit("Weaver live-check report covered fewer than two services")
    if not spans:
        raise SystemExit("Weaver live-check report did not contain any spans")


if __name__ == "__main__":
    main()
