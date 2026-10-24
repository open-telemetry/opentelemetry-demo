"""Synthetic recorded tool results ("snapshots") for offline tests. Shapes match the real tools."""

T1, T2, T3 = "4bf92f3577b34da6a3ce929d0e0e4736", "00f067aa0ba902b7a3ce929d0e0e4736", "a1b2c3d4e5f60718293a4b5c6d7e8f90"


def _h(svc, er=0.0, erb=0.0, p95=50.0, p95b=50.0, rate=2.0, rateb=2.0):
    return {"req_per_s": rate, "req_per_s_baseline": rateb, "error_rate": er, "error_rate_baseline": erb,
            "error_spans_per_s": er * rate, "p95_ms": p95, "p95_ms_baseline": p95b}


def snap(health_services, anomalies, origins=(), slow=(), logs=None, events=(), abnormal=None,
         failing_ops=(), extra_calls=()):
    calls = [
        {"name": "get_service_health", "args": {}, "result": {
            "window": "5m", "baseline_offset": "30m", "anomalies": list(anomalies),
            "services": health_services, "healthy_services": []}},
        {"name": "get_failing_operations", "args": {}, "result": list(failing_ops)},
        {"name": "get_error_origins", "args": {}, "result": {
            "lookback": "5m", "traces_sampled": 300, "error_spans_by_service": {},
            "error_origins": list(origins), "services_not_readable": []}},
        {"name": "get_slow_operations", "args": {}, "result": {"lookback": "5m", "slowest_by_self_time": list(slow)}},
        {"name": "get_error_log_summary", "args": {}, "result": {
            "source": "opensearch", "log_lines_scanned": 1000, "minutes": 5,
            "error_logs_by_service": logs or {}, "services_with_no_logs": []}},
        {"name": "get_runtime_events", "args": {}, "result": {
            "events": list(events), "baseline_available": True, "abnormal_containers": abnormal or {}}},
    ]
    return {"recorded_at": "test", "calls": calls + list(extra_calls)}


def payment_failure():
    return snap(
        {"payment": _h("payment", 0.45), "checkout": _h("checkout", 0.40), "frontend": _h("frontend", 0.12)},
        [{"service": "payment", "type": "error_rate_up", "detail": "error rate 45.0% (baseline 0.0%)", "severity": 0.9},
         {"service": "checkout", "type": "error_rate_up", "detail": "error rate 40.0% (baseline 0.0%)", "severity": 0.8},
         {"service": "frontend", "type": "error_rate_up", "detail": "error rate 12.0% (baseline 0.0%)", "severity": 0.24}],
        origins=[{"where": "payment :: oteldemo.PaymentService/Charge", "count": 28,
                  "top_messages": ["Payment request failed. Invalid token. app.loyalty.level=gold"],
                  "calls_to": [], "example_trace_ids": [T1, T2]},
                 {"where": "frontend :: GET /api/data", "count": 2, "top_messages": [], "calls_to": [],
                  "example_trace_ids": [T3]}],
        logs={"payment": {"error_lines": 40, "total_lines": 200, "top_messages": ["40x [ERROR] Payment request failed. Invalid token."]},
              "checkout": {"error_lines": 20, "total_lines": 300, "top_messages": ["20x [ERROR] failed to charge card: rpc error"]}},
        events=["frontend (re)started 3.0 min ago"],
        failing_ops=[{"service": "payment", "operation": "oteldemo.PaymentService/Charge", "errors_per_s": 0.4}],
        extra_calls=[
            {"name": "get_trace", "args": {"trace_id": T1}, "result": {"trace_id": T1, "spans": 9, "tree": [
                "frontend-proxy :: ingress 812.0ms ERROR", "  frontend :: POST /api/checkout 800.0ms ERROR",
                "    checkout :: oteldemo.CheckoutService/PlaceOrder 700.0ms ERROR",
                '      payment :: oteldemo.PaymentService/Charge 12.0ms ERROR "Payment request failed. Invalid token."']}},
            {"name": "search_logs", "args": {"service": "payment"}, "result": {
                "service": "payment", "source": "opensearch", "lines_scanned": 200, "matches": 40,
                "lines": [{"time": "2026-10-23T10:00:01Z", "severity": "ERROR",
                           "body": "Payment request failed. Invalid token. app.loyalty.level=gold"}]}},
            {"name": "get_container_health", "args": {"service": "payment"}, "result": {
                "service": "payment", "status": "running", "restart_count": 0, "oom_killed": False}},
        ])


def payment_stopped():
    return snap(
        {"checkout": _h("checkout", 0.6), "frontend": _h("frontend", 0.2), "payment": _h("payment", 0, 0, 0, 20, 0, 1.5)},
        [{"service": "checkout", "type": "error_rate_up", "detail": "error rate 60.0% (baseline 0.0%)", "severity": 1.0},
         {"service": "payment", "type": "traffic_drop", "detail": "0.00 req/s (baseline 1.50)", "severity": 0.7}],
        origins=[{"where": "checkout :: oteldemo.PaymentService/Charge", "count": 25,
                  "top_messages": ["rpc error: code = Unavailable desc = connection error: dial tcp: lookup payment: no such host"],
                  "calls_to": ["oteldemo.PaymentService"], "example_trace_ids": [T1]}],
        logs={"checkout": {"error_lines": 30, "total_lines": 100,
                           "top_messages": ["30x failed to charge card: could not charge the card: rpc error: code = Unavailable"]}},
        events=["payment is exited (exit code 137, stopped 2.1 min ago)"],
        abnormal={"payment": {"status": "exited", "restart_count": 0, "oom_killed": False, "health": None,
                              "started_min_ago": 30, "exit_code": 137}})


def valkey_down():
    return snap(
        {"cart": _h("cart", 0.5), "frontend": _h("frontend", 0.3)},
        [{"service": "cart", "type": "error_rate_up", "detail": "error rate 50.0% (baseline 0.0%)", "severity": 1.0},
         {"service": "frontend", "type": "error_rate_up", "detail": "error rate 30.0% (baseline 0.0%)", "severity": 0.6}],
        origins=[{"where": "cart :: HGET", "count": 20, "top_messages": ["It was not possible to connect to the redis server(s). UnableToConnect"],
                  "calls_to": ["valkey-cart:6379"], "example_trace_ids": [T2]}],
        logs={"cart": {"error_lines": 25, "total_lines": 60, "top_messages": ["25x [ERROR] wasn't able to connect to redis valkey-cart:6379 connection refused"]}},
        events=["valkey-cart is exited (exit code 0, stopped 1.5 min ago)"],
        abnormal={"valkey-cart": {"status": "exited", "restart_count": 0, "oom_killed": False, "health": None,
                                  "started_min_ago": 40, "exit_code": 0}})


def ad_high_cpu():
    return snap(
        {"ad": _h("ad", 0, 0, 900, 40), "frontend": _h("frontend", 0, 0, 1200, 300)},
        [{"service": "ad", "type": "latency_up", "detail": "p95 900ms (baseline 40ms)", "severity": 1.0},
         {"service": "frontend", "type": "latency_up", "detail": "p95 1200ms (baseline 300ms)", "severity": 0.4}],
        slow=[{"where": "ad :: oteldemo.AdService/GetAds", "n": 12, "max_self_ms": 880.0, "trace_ids": [T3], "calls_to": ""}],
        events=["ad CPU 185% (baseline 4%)"])


def traffic_flood():
    return snap(
        {"frontend": _h("frontend", 0.01, 0, 400, 100, 40, 5), "frontend-proxy": _h("frontend-proxy", 0, 0, 500, 120, 45, 6)},
        [{"service": "frontend", "type": "traffic_spike", "detail": "40.0 req/s (baseline 5.0)", "severity": 0.6},
         {"service": "frontend-proxy", "type": "traffic_spike", "detail": "45.0 req/s (baseline 6.0)", "severity": 0.6},
         {"service": "frontend", "type": "latency_up", "detail": "p95 400ms (baseline 100ms)", "severity": 0.3}])


def healthy():
    return snap({}, [], origins=[{"where": "load-generator :: POST", "count": 2, "top_messages": [], "calls_to": [],
                                  "example_trace_ids": [T1]}],
                logs={"frontend-proxy": {"error_lines": 3, "total_lines": 376, "top_messages": ["3x upgrade_failed"]}},
                events=["load-generator CPU 151% (no baseline)", "accounting (re)started 4.0 min ago"])
