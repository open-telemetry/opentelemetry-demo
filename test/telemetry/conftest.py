# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import os
import time

import pytest
import requests

from services import edges_for_scope, services_with_signal


JAEGER_HOST = os.environ.get("JAEGER_HOST", "jaeger")
JAEGER_UI_PORT = os.environ.get("JAEGER_UI_PORT", "16686")
JAEGER_URL = os.environ.get("JAEGER_URL", f"http://{JAEGER_HOST}:{JAEGER_UI_PORT}")

PROMETHEUS_HOST = os.environ.get("PROMETHEUS_HOST", "prometheus")
PROMETHEUS_PORT = os.environ.get("PROMETHEUS_PORT", "9090")
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", f"http://{PROMETHEUS_HOST}:{PROMETHEUS_PORT}")

OPENSEARCH_HOST = os.environ.get("OPENSEARCH_HOST", "opensearch")
OPENSEARCH_PORT = os.environ.get("OPENSEARCH_PORT", "9200")
OPENSEARCH_URL = os.environ.get("OPENSEARCH_URL", f"http://{OPENSEARCH_HOST}:{OPENSEARCH_PORT}")

COLLECTOR_HOST = os.environ.get("OTEL_COLLECTOR_HOST", "otel-collector")
COLLECTOR_PORT = int(os.environ.get("OTEL_COLLECTOR_PORT_GRPC", "4317"))

TEST_SCOPE = os.environ.get("TEST_SCOPE", "minimal")
WARMUP_SECONDS = int(os.environ.get("WARMUP_SECONDS", "240"))

POLL_INTERVAL = 5
POLL_TIMEOUT = int(os.environ.get("POLL_TIMEOUT", "180"))


def _jaeger_service_count():
    """Number of services Jaeger has seen at least one span from."""
    resp = requests.get(f"{JAEGER_URL}/jaeger/ui/api/services", timeout=5)
    if resp.status_code != 200:
        return 0
    # Jaeger returns {"data": null, ...} until the first span arrives, so coerce
    # None -> [] before len().
    return len(resp.json().get("data") or [])


def _prometheus_service_count():
    """Number of distinct service.name labels Prometheus has received via OTLP push."""
    resp = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": "count(group(target_info) by (service_name))"},
        timeout=5,
    )
    if resp.status_code != 200:
        return 0
    result = resp.json().get("data", {}).get("result") or []
    if not result:
        return 0
    return int(float(result[0]["value"][1]))


def _opensearch_log_count():
    """Number of log records OpenSearch has indexed in the otel-logs index."""
    resp = requests.get(f"{OPENSEARCH_URL}/otel-logs*/_count", timeout=5)
    if resp.status_code != 200:
        return 0
    return int(resp.json().get("count", 0))


# Minimum distinct services / records each backend must report before we treat
# warmup as complete. A small floor (rather than the full service count) keeps
# this robust across the full and minimal scopes while still proving each
# signal pipeline is actually flowing end to end.
WARMUP_MIN_SERVICES = 3
WARMUP_MIN_LOGS = 1


@pytest.fixture(scope="session", autouse=True)
def wait_for_warmup():
    """Wait for Jaeger, Prometheus, and OpenSearch to all ingest telemetry
    before starting the individual signal checks.

    Traces (Jaeger), metrics (Prometheus), and logs (OpenSearch) reach their
    backends on independent paths through the collector, each with its own
    batching / sending-queue interval, so they do not become queryable at the
    same moment. Observed on a cold start: Jaeger had 12 services at ~11s while
    Prometheus still had only 3 (it caught up to 20 by ~39s). If warmup gates on
    traces alone, the metrics tests start against a near-empty Prometheus and
    time out at the per-test deadline (one timeout per service, which is how a
    run ballooned to ~45min). Gating on all three keeps the per-test polls fast
    because the data is already there when they run.
    """
    print(f"\nWaiting for backends to be ready (up to {WARMUP_SECONDS}s)...")
    deadline = time.time() + WARMUP_SECONDS
    backends_ready = False
    while time.time() < deadline:
        try:
            jaeger = _jaeger_service_count()
            prom = _prometheus_service_count()
            logs = _opensearch_log_count()
            if (
                jaeger > WARMUP_MIN_SERVICES
                and prom > WARMUP_MIN_SERVICES
                and logs >= WARMUP_MIN_LOGS
            ):
                backends_ready = True
                break
        except (requests.RequestException, ValueError):
            pass
        time.sleep(POLL_INTERVAL)
    if not backends_ready:
        remaining = max(0, int(deadline - time.time()))
        print(f"Backends not fully ready after {WARMUP_SECONDS - remaining}s, proceeding with poll-based checks...")
    else:
        elapsed = WARMUP_SECONDS - int(deadline - time.time())
        print(f"Backends ready after {elapsed}s, starting tests...")


@pytest.fixture(scope="session")
def jaeger_url():
    return JAEGER_URL


@pytest.fixture(scope="session")
def prometheus_url():
    return PROMETHEUS_URL


@pytest.fixture(scope="session")
def opensearch_url():
    return OPENSEARCH_URL


@pytest.fixture(scope="session")
def collector_host():
    return COLLECTOR_HOST


@pytest.fixture(scope="session")
def collector_port():
    return COLLECTOR_PORT


@pytest.fixture(scope="session")
def test_scope():
    return TEST_SCOPE


def poll_until(fn, description: str, timeout: int = POLL_TIMEOUT, interval: int = POLL_INTERVAL):
    """
    Poll a callable until it returns a truthy value or timeout is reached.
    Returns the result on success, raises AssertionError on timeout.
    """
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            result = fn()
            if result:
                return result
        except (requests.RequestException, KeyError, IndexError) as e:
            last_error = e
        time.sleep(interval)
    msg = f"Timed out after {timeout}s waiting for: {description}"
    if last_error:
        msg += f" (last error: {last_error})"
    raise AssertionError(msg)


def pytest_generate_tests(metafunc):
    """Dynamically parametrize tests based on TEST_SCOPE and signal matrix."""
    scope = os.environ.get("TEST_SCOPE", "minimal")

    if "trace_service" in metafunc.fixturenames:
        services = services_with_signal("traces", scope)
        metafunc.parametrize("trace_service", services)

    if "metric_service" in metafunc.fixturenames:
        services = services_with_signal("metrics", scope)
        metafunc.parametrize("metric_service", services)

    if "log_service" in metafunc.fixturenames:
        services = services_with_signal("logs", scope)
        metafunc.parametrize("log_service", services)

    if "service_edge" in metafunc.fixturenames:
        edges = edges_for_scope(scope)
        metafunc.parametrize(
            "service_edge",
            edges,
            ids=[f"{p}->{c}" for p, c in edges],
        )
