# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import os
import time

import pytest
import requests

from services import services_with_signal


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
WARMUP_SECONDS = int(os.environ.get("WARMUP_SECONDS", "120"))

POLL_INTERVAL = 5
POLL_TIMEOUT = 120


@pytest.fixture(scope="session", autouse=True)
def wait_for_warmup():
    """Wait for backends to be reachable, then allow time for telemetry to flow."""
    print(f"\nWaiting for backends to be ready (up to {WARMUP_SECONDS}s)...")
    deadline = time.time() + WARMUP_SECONDS
    backends_ready = False
    while time.time() < deadline:
        try:
            resp = requests.get(f"{JAEGER_URL}/jaeger/ui/api/services", timeout=5)
            if resp.status_code == 200 and len(resp.json().get("data", [])) > 3:
                backends_ready = True
                break
        except requests.RequestException:
            pass
        time.sleep(5)
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
