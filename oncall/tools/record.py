"""CLI for recording telemetry fixtures from live backends.

Usage:
    python -m oncall.tools.record --scenario baseline
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from oncall.tools.backends import BackendError, RecordingBackend

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

COMMON_SERVICES = [
    "frontend",
    "cart",
    "checkout",
    "payment",
    "product-catalog",
    "recommendation",
    "shipping",
    "email",
    "ad",
    "accounting",
    "fraud-detection",
    "quote",
]


def record_scenario(
    scenario: str = "baseline",
    services: Sequence[str] | None = None,
    backend: RecordingBackend | None = None,
) -> int:
    """Record a comprehensive sweep of telemetry queries for a given scenario."""
    if backend is None:
        backend = RecordingBackend(scenario=scenario)

    logger.info("Recording scenario '%s' to %s", scenario, backend.scenario_dir)

    recorded_count = 0
    errors_count = 0

    # 1. Prometheus checks
    logger.info("Recording Prometheus queries...")
    prom_queries = [
        "up",
        "sum by (service_name) (rate(traces_span_metrics_calls_total[5m]))",
        'sum by (service_name) (rate(traces_span_metrics_calls_total{status_code="STATUS_CODE_ERROR"}[5m]))',
        "histogram_quantile(0.95, sum by (le, service_name) (rate(traces_span_metrics_duration_ms_bucket[5m])))",
    ]
    for q in prom_queries:
        try:
            backend.prom_query(q)
            recorded_count += 1
            logger.info("Recorded prom_query: %s", q)
        except BackendError as exc:
            errors_count += 1
            logger.warning("Failed prom_query %s: %s", q, exc)

    # 2. Jaeger services
    logger.info("Recording Jaeger services and traces...")
    discovered_services: list[str] = []
    try:
        discovered_services = backend.jaeger_services()
        recorded_count += 1
        logger.info("Discovered %d Jaeger services", len(discovered_services))
    except BackendError as exc:
        errors_count += 1
        logger.warning("Failed jaeger_services: %s", exc)

    target_services = list(services or discovered_services or COMMON_SERVICES)

    for svc in target_services:
        try:
            backend.jaeger_traces(service=svc, lookback="15m", limit=20)
            recorded_count += 1
            logger.info("Recorded jaeger_traces for %s", svc)
        except BackendError as exc:
            errors_count += 1
            logger.warning("Failed jaeger_traces for %s: %s", svc, exc)

        try:
            backend.jaeger_traces(
                service=svc, lookback="15m", limit=20, tags={"error": "true"}
            )
            recorded_count += 1
        except BackendError as exc:
            errors_count += 1
            logger.warning("Failed error jaeger_traces for %s: %s", svc, exc)

    # 3. OpenSearch logs
    logger.info("Recording OpenSearch logs...")
    try:
        backend.logs_search(service=None, level="error", since_min=15, limit=50)
        recorded_count += 1
        logger.info("Recorded general error logs")
    except BackendError as exc:
        errors_count += 1
        logger.warning("Failed general logs_search: %s", exc)

    for svc in target_services:
        try:
            backend.logs_search(service=svc, level="error", since_min=15, limit=50)
            recorded_count += 1
        except BackendError as exc:
            errors_count += 1
            logger.warning("Failed logs_search for %s: %s", svc, exc)

    logger.info(
        "Finished recording '%s'. Total recorded calls: %d, errors: %d",
        scenario,
        recorded_count,
        errors_count,
    )
    return recorded_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Record telemetry fixtures.")
    parser.add_argument(
        "--scenario",
        default="baseline",
        help="Name of scenario / folder to store fixtures in.",
    )
    args = parser.parse_args()
    count = record_scenario(scenario=args.scenario)
    if count == 0:
        logger.error("No queries were recorded successfully.")
        sys.exit(1)


if __name__ == "__main__":
    main()
