# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import os
import time
import uuid

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

# Entrypoint the warmup probe drives traffic through. Envoy fans the request out
# to the whole service graph, exactly like the load generator does.
#
# Build the URL from host + port rather than FRONTEND_PROXY_ADDR: in .env that
# value is `frontend-proxy:${ENVOY_PORT}`, and `--env-file` (unlike compose) does
# not expand `${...}`, so the composed form arrives literally unexpanded.
ENVOY_PORT = os.environ.get("ENVOY_PORT", "8080")
FRONTEND_PROXY_HOST = os.environ.get("FRONTEND_PROXY_HOST", "frontend-proxy")
FRONTEND_PROXY_URL = os.environ.get(
    "FRONTEND_PROXY_URL", f"http://{FRONTEND_PROXY_HOST}:{ENVOY_PORT}"
)

TEST_SCOPE = os.environ.get("TEST_SCOPE", "minimal")
WARMUP_SECONDS = int(os.environ.get("WARMUP_SECONDS", "240"))

# The warmup probe drives a few real checkouts through the frontend before the
# readiness poll, so low-frequency services (email, quote) that only emit on the
# checkout path reliably produce telemetry instead of depending on the load
# generator happening to run a checkout (~6% task weight) within the test window.
WARMUP_PROBE_ENABLED = os.environ.get("WARMUP_PROBE_ENABLED", "true").lower() == "true"
WARMUP_PROBE_CHECKOUTS = int(os.environ.get("WARMUP_PROBE_CHECKOUTS", "5"))

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

# Static product IDs from the demo catalog, mirroring src/load-generator/locustfile.py.
# These are stable demo data; any one is fine for a checkout.
PROBE_PRODUCTS = [
    "0PUK6V6EV0",
    "1YMWWN1N4O",
    "2ZYFJ3GM2N",
    "66VCHSJNUP",
    "6E92ZMYYFZ",
    "9SIQT8TOJO",
    "L9ECAV7KIM",
    "LS4PSXUNUM",
    "OLJCESPC7Z",
    "HQTGWGPNH4",
]

# Checkout payload, mirroring an entry from src/load-generator/people.json. The
# frontend /api/checkout endpoint expects this shape (address, currency, card).
PROBE_PERSON = {
    "email": "telemetry-test@example.com",
    "address": {
        "streetAddress": "1600 Amphitheatre Parkway",
        "zipCode": "94043",
        "city": "Mountain View",
        "state": "CA",
        "country": "United States",
    },
    "userCurrency": "USD",
    "creditCard": {
        "creditCardNumber": "4432-8015-6152-0454",
        "creditCardExpirationMonth": 1,
        "creditCardExpirationYear": 2039,
        "creditCardCvv": 672,
    },
}


def _drive_checkout(session, product_id):
    """Add one product to a fresh cart and check out via the frontend proxy.

    Best-effort: the demo may still be starting, so any request error is swallowed
    and reported rather than raised - the warmup readiness loop is what actually
    gates the tests.
    """
    user_id = str(uuid.uuid4())
    try:
        session.post(
            f"{FRONTEND_PROXY_URL}/api/cart",
            json={"item": {"productId": product_id, "quantity": 1}, "userId": user_id},
            timeout=10,
        )
        person = dict(PROBE_PERSON, userId=user_id)
        session.post(f"{FRONTEND_PROXY_URL}/api/checkout", json=person, timeout=15)
        return True
    except requests.RequestException as e:
        print(f"  warmup probe checkout failed (ignored): {e}")
        return False


def _run_warmup_probe():
    """Drive a handful of real checkouts so the full service graph - including
    low-frequency services like email and quote that only emit on the checkout
    path - produces telemetry deterministically before the readiness poll."""
    print(f"Driving {WARMUP_PROBE_CHECKOUTS} warmup checkout(s) via {FRONTEND_PROXY_URL}...")
    ok = 0
    with requests.Session() as session:
        for i in range(WARMUP_PROBE_CHECKOUTS):
            product_id = PROBE_PRODUCTS[i % len(PROBE_PRODUCTS)]
            if _drive_checkout(session, product_id):
                ok += 1
    print(f"  warmup probe completed: {ok}/{WARMUP_PROBE_CHECKOUTS} checkout(s) succeeded")


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

    Before polling, drive a few real checkouts through the frontend so the
    low-frequency services (email, quote) that only emit on the checkout path
    reliably produce telemetry rather than relying on the load generator's ~6%
    checkout task weight landing inside the test window.
    """
    if WARMUP_PROBE_ENABLED:
        _run_warmup_probe()
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
