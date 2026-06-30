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

AGENT_HOST = os.environ.get("AGENT_ENDPOINT", "agent")
AGENT_PORT = os.environ.get("AGENT_PORT", "8010")
AGENT_URL = os.environ.get("AGENT_URL", f"http://{AGENT_HOST}:{AGENT_PORT}")

MCP_HOST = os.environ.get("MCP_ENDPOINT", "mcp")
MCP_PORT_VAL = os.environ.get("MCP_PORT", "8011")
MCP_URL = os.environ.get("MCP_URL", f"http://{MCP_HOST}:{MCP_PORT_VAL}")

CHATBOT_HOST = os.environ.get("CHATBOT_HOST", "chatbot")
CHATBOT_PORT_VAL = os.environ.get("CHATBOT_PORT", "7860")
CHATBOT_URL = os.environ.get("CHATBOT_URL", f"http://{CHATBOT_HOST}:{CHATBOT_PORT_VAL}")

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
WARMUP_PROBE_TIMEOUT = int(os.environ.get("WARMUP_PROBE_TIMEOUT", "120"))

# These services are expected to emit logs from the checkout path driven by the
# warmup probe. Gate on them explicitly so CI fails in setup with a useful
# message instead of spending one POLL_TIMEOUT per missing log test.
WARMUP_PROBE_LOG_SERVICES = tuple(
    svc
    for svc in ("email", "frontend-proxy", "quote")
    if svc in services_with_signal("logs", TEST_SCOPE)
)

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


def _opensearch_service_log_count(service):
    """Number of log records OpenSearch has indexed for one service."""
    ppl = f"source=otel-logs-* | where resource.service.name = '{service}' | stats count()"
    resp = requests.post(
        f"{OPENSEARCH_URL}/_plugins/_ppl",
        json={"query": ppl},
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    rows = resp.json().get("datarows", [])
    if not rows:
        return 0
    return int(rows[0][0])


def _opensearch_service_log_counts(services):
    return {svc: _opensearch_service_log_count(svc) for svc in services}


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


def _raise_for_status(resp, description):
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        body = resp.text.strip().replace("\n", " ")[:300]
        raise requests.HTTPError(
            f"{description} returned HTTP {resp.status_code}: {body}",
            response=resp,
        ) from e


def _drive_checkout(session, product_id):
    """Add one product to a fresh cart and check out via the frontend proxy.
    """
    user_id = str(uuid.uuid4())
    cart_resp = session.post(
        f"{FRONTEND_PROXY_URL}/api/cart",
        json={"item": {"productId": product_id, "quantity": 1}, "userId": user_id},
        timeout=10,
    )
    _raise_for_status(cart_resp, "cart warmup request")

    person = dict(PROBE_PERSON, userId=user_id)
    checkout_resp = session.post(
        f"{FRONTEND_PROXY_URL}/api/checkout",
        json=person,
        timeout=15,
    )
    _raise_for_status(checkout_resp, "checkout warmup request")


def _run_warmup_probe():
    """Drive a handful of real checkouts so the full service graph - including
    low-frequency services like email and quote that only emit on the checkout
    path - produces telemetry deterministically before the readiness poll."""
    if WARMUP_PROBE_CHECKOUTS <= 0:
        print("Warmup probe requested 0 checkouts, skipping checkout traffic.")
        return

    print(
        f"Driving {WARMUP_PROBE_CHECKOUTS} warmup checkout(s) via "
        f"{FRONTEND_PROXY_URL} for up to {WARMUP_PROBE_TIMEOUT}s..."
    )
    deadline = time.time() + WARMUP_PROBE_TIMEOUT
    ok = 0
    attempts = 0
    last_error = None
    with requests.Session() as session:
        while ok < WARMUP_PROBE_CHECKOUTS and time.time() < deadline:
            product_id = PROBE_PRODUCTS[attempts % len(PROBE_PRODUCTS)]
            attempts += 1
            try:
                _drive_checkout(session, product_id)
                ok += 1
                print(f"  warmup checkout {ok}/{WARMUP_PROBE_CHECKOUTS} succeeded")
            except requests.RequestException as e:
                last_error = e
                print(f"  warmup checkout attempt {attempts} failed: {e}")
                time.sleep(POLL_INTERVAL)

    if ok < WARMUP_PROBE_CHECKOUTS:
        msg = (
            f"Warmup probe completed only {ok}/{WARMUP_PROBE_CHECKOUTS} "
            f"checkout(s) within {WARMUP_PROBE_TIMEOUT}s"
        )
        if last_error:
            msg += f"; last error: {last_error}"
        pytest.fail(msg)

    print(f"  warmup probe completed: {ok}/{WARMUP_PROBE_CHECKOUTS} checkout(s) succeeded")


def _run_agentic_warmup_probe():
    """Drive one request to each agentic service so all three appear in Jaeger
    before test assertions begin.

    * agent   - POST /prompt (required): FastAPIInstrumentor and the Traceloop
                @workflow decorator emit spans even when the LLM call fails, so
                any HTTP response (including 5xx) is treated as success.
    * mcp     - POST /mcp tools/call list_products (best-effort): triggers an
                outbound httpx call that HTTPXClientInstrumentor captures as a span.
    * chatbot - POST /gradio_api/call/respond (best-effort): triggers the
                chatbot->agent HTTP call so both services emit linked spans.
    """
    deadline = time.time() + WARMUP_PROBE_TIMEOUT
    print(
        f"\nDriving agentic warmup probes (agent, chatbot) for up to "
        f"{WARMUP_PROBE_TIMEOUT}s..."
    )

    # --- agent: required ---
    # POST /prompt causes FastAPI + Traceloop @workflow spans to be emitted.
    # Any HTTP response (including 5xx) is sufficient: FastAPIInstrumentor and
    # the @workflow decorator both record spans regardless of whether the LLM
    # call inside succeeds. We only retry on connection errors (service not up).
    agent_ok = False
    last_error = None
    with requests.Session() as session:
        while not agent_ok and time.time() < deadline:
            try:
                resp = session.post(
                    f"{AGENT_URL}/prompt",
                    json={"message": "List available products in the store.", "history": []},
                    timeout=30,
                )
                agent_ok = True
                print(f"  agent warmup probe: HTTP {resp.status_code}")
            except requests.RequestException as e:
                last_error = e
                time.sleep(POLL_INTERVAL)

    if not agent_ok:
        msg = f"Agent at {AGENT_URL} did not respond within {WARMUP_PROBE_TIMEOUT}s"
        if last_error:
            msg += f"; last error: {last_error}"
        pytest.fail(msg)

    # --- mcp: best-effort direct probe ---
    # FastMCP uses MCP Streamable HTTP transport which requires:
    #   Accept: application/json, text/event-stream  (else 406)
    #   Mcp-Session-Id: <id>  on all requests after initialize
    # The server returns Mcp-Session-Id in the initialize response headers;
    # without it on tools/call the server rejects the request before invoking
    # any tool, so no HTTPX span is emitted.
    # list_products triggers an outbound httpx call to product-catalog,
    # the only code path HTTPXClientInstrumentor reliably captures as a span.
    try:
        mcp_headers = {"Accept": "application/json, text/event-stream"}
        init_resp = requests.post(
            f"{MCP_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "telemetry-warmup", "version": "1.0"},
                },
                "id": 1,
            },
            headers=mcp_headers,
            timeout=10,
        )
        session_id = init_resp.headers.get("Mcp-Session-Id")
        call_headers = {**mcp_headers}
        if session_id:
            call_headers["Mcp-Session-Id"] = session_id
        mcp_resp = requests.post(
            f"{MCP_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "list_products", "arguments": {}},
                "id": 2,
            },
            headers=call_headers,
            timeout=15,
        )
        print(f"  mcp warmup probe: HTTP {mcp_resp.status_code}")
    except Exception as e:
        print(f"  mcp warmup probe skipped: {e}")

    # --- chatbot: best-effort Gradio API call ---
    # Gradio 6.x moved all API routes to /gradio_api/.  POST to
    # /gradio_api/call/respond queues and executes the respond() handler,
    # which calls requests.post(agent_url).  RequestsInstrumentor injects
    # traceparent so the chatbot->agent edge appears in Jaeger.
    try:
        chatbot_resp = requests.post(
            f"{CHATBOT_URL}/gradio_api/call/respond",
            json={"data": ["List available products in the store.", []]},
            timeout=60,
        )
        print(f"  chatbot warmup probe: HTTP {chatbot_resp.status_code}")
    except Exception as e:
        print(f"  chatbot warmup probe skipped: {e}")


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
    if WARMUP_PROBE_ENABLED and TEST_SCOPE != "agentic":
        _run_warmup_probe()
    print(f"\nWaiting for backends to be ready (up to {WARMUP_SECONDS}s)...")
    required_probe_log_services = (
        WARMUP_PROBE_LOG_SERVICES
        if WARMUP_PROBE_ENABLED and WARMUP_PROBE_CHECKOUTS > 0
        else ()
    )
    if required_probe_log_services:
        print(
            "Waiting for checkout-path logs in OpenSearch: "
            + ", ".join(required_probe_log_services)
        )
    deadline = time.time() + WARMUP_SECONDS
    backends_ready = False
    last_state = None
    last_error = None
    while time.time() < deadline:
        try:
            jaeger = _jaeger_service_count()
            prom = _prometheus_service_count()
            logs = _opensearch_log_count()
            probe_logs = _opensearch_service_log_counts(required_probe_log_services)
            last_state = (jaeger, prom, logs, probe_logs)
            if (
                jaeger > WARMUP_MIN_SERVICES
                and prom > WARMUP_MIN_SERVICES
                and logs >= WARMUP_MIN_LOGS
                and all(count > 0 for count in probe_logs.values())
            ):
                backends_ready = True
                break
        except (requests.RequestException, ValueError) as e:
            last_error = e
        time.sleep(POLL_INTERVAL)
    if not backends_ready:
        if required_probe_log_services:
            probe_logs = last_state[3] if last_state else {}
            missing_logs = [
                svc
                for svc in required_probe_log_services
                if probe_logs.get(svc, 0) <= 0
            ]
            if missing_logs:
                msg = (
                    "Warmup checkouts completed, but checkout-path logs did not "
                    f"reach OpenSearch within {WARMUP_SECONDS}s. Missing logs: "
                    f"{', '.join(missing_logs)}. Last counts: {probe_logs}"
                )
                if last_error:
                    msg += f"; last backend error: {last_error}"
                pytest.fail(msg)
        remaining = max(0, int(deadline - time.time()))
        print(f"Backends not fully ready after {WARMUP_SECONDS - remaining}s, proceeding with poll-based checks...")
    else:
        elapsed = WARMUP_SECONDS - int(deadline - time.time())
        print(f"Backends ready after {elapsed}s, starting tests...")

    if TEST_SCOPE == "agentic":
        _run_agentic_warmup_probe()


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
