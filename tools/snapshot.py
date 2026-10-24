"""Run container_health, query_metrics, query_traces, query_logs and deploy_history once and print them.

Run with: python -m tools.snapshot [--window MINUTES] [--top N]
Read-only. An error or empty result is printed as such, never as healthy.
"""
import argparse

from tools.ledger import Ledger
from tools.containers import container_health
from tools.deploys import deploy_history
from tools.logs import query_logs
from tools.metrics import query_metrics
from tools.traces import query_traces


def fmt(value, spec: str = "") -> str:
    return "-" if value is None else format(value, spec)


def print_header(result) -> None:
    print(f"[{result.tool}] state={result.state}")
    if result.error:
        print(f"  ERROR: {result.error}")
    for note in result.notes:
        print(f"  note: {note}")


def print_containers(result) -> None:
    print_header(result)
    if result.state != "data":
        return
    s = result.extra["summary"]
    print(f"  {s['running']}/{s['total']} running; not running: {s['not_running'] or 'none'}; "
          f"unhealthy: {s['unhealthy'] or 'none'}; restarted: {s['restarted'] or 'none'}; OOM: {s['oom_killed'] or 'none'}")
    print(f"  {'container':<18}{'status':<11}{'health':<11}{'restarts':>8}{'exit':>6}{'cpu%':>7}{'mem%':>7}")
    for r in result.items:
        print(f"  {r['name']:<18}{r['status']:<11}{r['health']:<11}{r['restart_count']:>8}{fmt(r['exit_code']):>6}"
              f"{fmt(r.get('cpu_percent'), '.1f'):>7}{fmt(r.get('memory_percent'), '.1f'):>7}")


def print_metrics(result) -> None:
    print_header(result)
    if result.state != "data":
        return
    print(f"  window {result.window['start']} .. {result.window['end']}  ({len(result.items)} of {result.total_items} services)")
    print(f"  {'service':<18}{'req/s':>8}{'err %':>8}{'p95 ms':>9}  top erroring spans")
    for r in result.items:
        spans = "; ".join(f"{s['span_name']} [{s['span_kind']}]" for s in r.get("top_error_spans", []))
        print(f"  {r['service']:<18}{r['request_rate_per_s']:>8.2f}{fmt(r['error_rate_pct'], '.2f'):>8}{fmt(r['p95_ms'], '.0f'):>9}  {spans}")
    for name, rows in result.extra.items():
        if name == "top_error_spans":
            print("  worst erroring spans (all services, all span kinds):")
            for r in rows[:5]:
                print(f"    {r['service']:<16}{r['span_kind']:<9}{r['error_rate_per_s']:>8.3f}/s  {r['span_name']}")
            continue
        print(f"  {name}: " + ", ".join(" ".join(str(v) for v in row.values()) for row in rows[:5]))


def print_traces(result) -> None:
    print_header(result)
    if result.state != "data":
        return
    print(f"  {len(result.items)} of {result.total_items} traces")
    for t in result.items:
        d = t["deepest_error"]
        print(f"  {t['trace_id']}  {t['root_service']}:{t['root_operation']}  {t['duration_ms']:.0f}ms  "
              f"{t['span_count']} spans  {t['error_span_count']} erroring")
        if d:
            print(f"      deepest error: {d['service']} / {d['span']} [{d['kind']}] {', '.join(d['why'])}"
                  + (f" - {d['message']}" if d.get("message") else ""))
    for g in result.extra.get("error_groups", []):
        print(f"  group x{g['traces']}: {g['deepest_service']} / {g['deepest_span']}  e.g. {g['example_trace_id']}")


def print_logs(result) -> None:
    print_header(result)
    if result.state != "data":
        return
    print(f"  {len(result.items)} of {result.total_items} message groups")
    for g in result.items:
        print(f"  x{g['count']:<4}{g['service']:<16}{g['level']:<9}{g['last_seen']}  {g['message'][:110]}")


def print_deploys(result) -> None:
    print_header(result)
    if result.state != "data":
        return
    s = result.extra["summary"]
    print(f"  restarted recently: {s['restarted_recently'] or 'none'}; median age {s['median_age_seconds']}s")
    for r in result.items[:6]:
        print(f"  {r['name']:<18}{r['status']:<11}started {r['started_at']}  age {r['age_seconds']}s  restarts {r['restart_count']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", type=int, default=5, help="metrics window in minutes")
    parser.add_argument("--top", type=int, default=10, help="max services to show")
    parser.add_argument("--save-ledger", metavar="PATH", help="also save every result, as the agent's ledger would hold it, to this JSON file")
    args = parser.parse_args()
    ledger = Ledger()
    runs = [
        ("container_health", {}, container_health(), print_containers),
        ("query_metrics", {"window_minutes": args.window, "top_n": args.top}, query_metrics(window_minutes=args.window, top_n=args.top), print_metrics),
        ("query_traces", {"window_minutes": args.window}, query_traces(window_minutes=args.window), print_traces),
        ("query_logs", {"window_minutes": args.window}, query_logs(window_minutes=args.window), print_logs),
        ("deploy_history", {}, deploy_history(), print_deploys),
    ]
    for index, (tool, arguments, result, show) in enumerate(runs):
        ledger.add(tool, arguments, result)
        if index:
            print()
        show(result)
    if args.save_ledger:
        print(f"\nledger saved to {ledger.save(args.save_ledger)}")


if __name__ == "__main__":
    main()
