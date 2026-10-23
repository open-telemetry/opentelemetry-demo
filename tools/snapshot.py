"""Run container_health and query_metrics once and print a compact table.

Run with: python -m tools.snapshot [--window MINUTES] [--top N]
Read-only. An error or empty result is printed as such, never as healthy.
"""
import argparse

from tools.containers import container_health
from tools.metrics import query_metrics


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", type=int, default=5, help="metrics window in minutes")
    parser.add_argument("--top", type=int, default=10, help="max services to show")
    args = parser.parse_args()
    print_containers(container_health())
    print()
    print_metrics(query_metrics(window_minutes=args.window, top_n=args.top))


if __name__ == "__main__":
    main()
