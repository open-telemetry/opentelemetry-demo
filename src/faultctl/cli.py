# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""faultctl command-line interface."""

import argparse
import json
import sys
import threading
import time

from . import __version__
from .client import FaultClient
from .flags import (
    FLAG_SERVICE_MAP,
    clear_flag,
    flag_summary,
    get_active_variant,
    get_resting_variant,
    get_variants,
    is_active,
    reset_all,
    set_flag,
    trigger_all,
)
from .scenarios import SCENARIOS

# ── ANSI helpers ──────────────────────────────────────────────────────────

_SUPPORTS_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _c(code, text):
    if _SUPPORTS_COLOR:
        return f"\033[{code}m{text}\033[0m"
    return text


def _green(t):
    return _c("32", t)


def _red(t):
    return _c("31", t)


def _yellow(t):
    return _c("33", t)


def _cyan(t):
    return _c("36", t)


def _bold(t):
    return _c("1", t)


def _dim(t):
    return _c("2", t)


# ── Table formatting ─────────────────────────────────────────────────────


def _print_table(headers, rows, col_styles=None):
    """Print a simple aligned table to stdout."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    sep = "  "
    header_line = sep.join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(_bold(header_line))
    print(sep.join("-" * w for w in widths))

    for row in rows:
        parts = []
        for i, cell in enumerate(row):
            text = str(cell).ljust(widths[i])
            if col_styles and i in col_styles:
                text = col_styles[i](text, row)
            parts.append(text)
        print(sep.join(parts))


# ── Subcommand handlers ──────────────────────────────────────────────────


def _make_client(args):
    mode = getattr(args, "mode", None)
    api_url = getattr(args, "api_url", None) or "http://localhost:8080/feature/api"
    file_path = getattr(args, "file", None)
    return FaultClient(mode=mode, api_url=api_url, file_path=file_path)


def cmd_list(args):
    """List all flags with current state."""
    client = _make_client(args)
    config = client.read()
    rows_data = flag_summary(config)

    if args.service:
        svc = args.service.lower()
        rows_data = [r for r in rows_data if svc in r["service"].lower()]

    if args.active:
        rows_data = [r for r in rows_data if r["is_active"]]

    if args.json:
        print(json.dumps(rows_data, indent=2))
        return

    if not rows_data:
        print(_dim("No flags match the filter."))
        return

    def status_style(text, row):
        return _red(text) if row[2] != "off" else _green(text)

    headers = ["FLAG", "SERVICE", "ACTIVE", "VARIANTS", "DESCRIPTION"]
    table_rows = []
    for r in rows_data:
        table_rows.append([
            r["name"],
            r["service"],
            r["active_variant"] if r["is_active"] else "off",
            ", ".join(r["variants"]),
            r["description"][:60],
        ])

    print(f"\n  {_bold('Failure Flags')}  ({_cyan(client.transport_name)} mode)\n")
    _print_table(headers, table_rows, col_styles={2: status_style})
    print()

    active_count = sum(1 for r in rows_data if r["is_active"])
    if active_count:
        print(f"  {_red('*')} {active_count} fault(s) active")
    else:
        print(f"  {_green('*')} All faults inactive")
    print()


def cmd_status(args):
    """High-level status summary."""
    client = _make_client(args)
    config = client.read()
    rows_data = flag_summary(config)

    active = [r for r in rows_data if r["is_active"]]

    print(f"\n  {_bold('faultctl status')}  ({_cyan(client.transport_name)} mode)\n")
    print(f"  Total flags: {len(rows_data)}")
    print(f"  Active:      {_red(str(len(active))) if active else _green('0')}")
    print()

    if active:
        headers = ["FLAG", "SERVICE", "VARIANT"]
        table_rows = [[r["name"], r["service"], r["active_variant"]] for r in active]
        _print_table(headers, table_rows)
        print()


def cmd_set(args):
    """Set a flag to a specific variant."""
    client = _make_client(args)
    config = client.read()

    flag_name = args.flag
    variant = args.variant

    if variant is None:
        flag_data = config.get("flags", {}).get(flag_name)
        if flag_data is None:
            print(_red(f"Error: Unknown flag '{flag_name}'"), file=sys.stderr)
            sys.exit(1)
        resting = get_resting_variant(flag_data)
        non_resting = [v for v in get_variants(flag_data) if v != resting]
        variant = non_resting[0] if non_resting else resting

    try:
        set_flag(config, flag_name, variant)
    except (KeyError, ValueError) as exc:
        print(_red(f"Error: {exc}"), file=sys.stderr)
        sys.exit(1)

    client.write(config)
    service = FLAG_SERVICE_MAP.get(flag_name, "unknown")
    print(f"  {_red('*')} {_bold(flag_name)} -> {_yellow(variant)}  ({service})")

    duration = getattr(args, "duration", None)
    if duration:
        print(f"  Auto-revert in {duration}s ...")
        _schedule_revert(client, flag_name, duration)


def _schedule_revert(client, flag_name, seconds):
    """Wait *seconds*, then revert *flag_name* to its resting variant."""
    def _revert():
        time.sleep(seconds)
        config = client.read()
        try:
            clear_flag(config, flag_name)
            client.write(config)
            print(f"\n  {_green('*')} {_bold(flag_name)} auto-reverted to off")
        except KeyError:
            pass

    t = threading.Thread(target=_revert, daemon=True)
    t.start()
    t.join()


def cmd_clear(args):
    """Clear (revert) a flag back to off."""
    client = _make_client(args)
    config = client.read()

    try:
        clear_flag(config, args.flag)
    except KeyError as exc:
        print(_red(f"Error: {exc}"), file=sys.stderr)
        sys.exit(1)

    client.write(config)
    print(f"  {_green('*')} {_bold(args.flag)} -> off")


def cmd_trigger_all(args):
    """Trigger all faults simultaneously."""
    client = _make_client(args)
    config = client.read()

    if args.dry_run:
        print(f"\n  {_bold('Dry run')} - would activate:\n")
        for name, data in sorted(config.get("flags", {}).items()):
            resting = get_resting_variant(data)
            activatable = [v for v in get_variants(data) if v != resting]
            if activatable:
                print(f"    {name} -> {activatable[0]}")
        print()
        return

    trigger_all(config)
    client.write(config)

    rows = flag_summary(config)
    active = [r for r in rows if r["is_active"]]
    print(f"\n  {_red('*')} Triggered {_bold(str(len(active)))} faults\n")
    for r in active:
        print(f"    {r['name']} -> {_yellow(r['active_variant'])}  ({r['service']})")
    print()

    duration = getattr(args, "duration", None)
    if duration:
        print(f"  Auto-reset in {duration}s ...")
        time.sleep(duration)
        config = client.read()
        reset_all(config)
        client.write(config)
        print(f"  {_green('*')} All faults reverted to off")


def cmd_reset(args):
    """Reset all flags to their resting (off) variants."""
    client = _make_client(args)
    config = client.read()
    reset_all(config)
    client.write(config)
    print(f"  {_green('*')} All {len(config.get('flags', {}))} flags reset to off")


def cmd_scenario_list(args):
    """List available preset scenarios."""
    print(f"\n  {_bold('Preset Scenarios')}\n")
    headers = ["NAME", "FLAGS", "DESCRIPTION"]
    table_rows = []
    for name in sorted(SCENARIOS.keys()):
        sc = SCENARIOS[name]
        flag_str = ", ".join(f"{k}={v}" for k, v in sc["flags"].items())
        table_rows.append([name, flag_str, sc["description"]])
    _print_table(headers, table_rows)
    print()


def cmd_scenario_apply(args):
    """Apply a preset scenario."""
    name = args.name
    if name not in SCENARIOS:
        print(_red(f"Error: Unknown scenario '{name}'"), file=sys.stderr)
        print(f"  Available: {', '.join(sorted(SCENARIOS.keys()))}")
        sys.exit(1)

    sc = SCENARIOS[name]
    client = _make_client(args)
    config = client.read()

    for flag_name, variant in sc["flags"].items():
        set_flag(config, flag_name, variant)

    client.write(config)

    print(f"\n  {_red('*')} Scenario: {_bold(name)}")
    print(f"  {sc['description']}\n")
    for flag_name, variant in sc["flags"].items():
        service = FLAG_SERVICE_MAP.get(flag_name, "unknown")
        print(f"    {flag_name} -> {_yellow(variant)}  ({service})")
    print()

    duration = getattr(args, "duration", None)
    if duration:
        print(f"  Auto-revert in {duration}s ...")
        time.sleep(duration)
        config = client.read()
        for flag_name in sc["flags"]:
            clear_flag(config, flag_name)
        client.write(config)
        print(f"  {_green('*')} Scenario reverted")


# ── Argument parser ──────────────────────────────────────────────────────


def build_parser():
    parser = argparse.ArgumentParser(
        prog="faultctl",
        description="Trigger and manage OpenTelemetry Demo failure flags.",
    )
    parser.add_argument(
        "--version", action="version", version=f"faultctl {__version__}",
    )

    # Global transport options
    transport = parser.add_mutually_exclusive_group()
    transport.add_argument(
        "--api", dest="mode", action="store_const", const="api",
        help="Force HTTP API mode (flagd-ui must be running)",
    )
    transport.add_argument(
        "--local", dest="mode", action="store_const", const="local",
        help="Force direct file mode (no flagd-ui needed)",
    )
    parser.add_argument(
        "--api-url", dest="api_url",
        default="http://localhost:8080/feature/api",
        help="Base URL for the flagd-ui REST API (default: %(default)s)",
    )
    parser.add_argument(
        "--file", dest="file", default=None,
        help="Path to demo.flagd.json (default: auto-detected)",
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # list
    p_list = sub.add_parser("list", aliases=["ls"], help="List all flags")
    p_list.add_argument("--service", "-s", help="Filter by service name")
    p_list.add_argument("--active", "-a", action="store_true",
                        help="Show only active faults")
    p_list.add_argument("--json", action="store_true",
                        help="Output as JSON")
    p_list.set_defaults(func=cmd_list)

    # status
    p_status = sub.add_parser("status", help="Summary of active faults")
    p_status.set_defaults(func=cmd_status)

    # set
    p_set = sub.add_parser("set", aliases=["inject"],
                           help="Set a flag to a variant")
    p_set.add_argument("flag", help="Flag name (e.g. paymentFailure)")
    p_set.add_argument("variant", nargs="?", default=None,
                       help="Variant to activate (default: first non-off)")
    p_set.add_argument("--duration", "-d", type=int, default=None,
                       help="Auto-revert after N seconds")
    p_set.set_defaults(func=cmd_set)

    # clear
    p_clear = sub.add_parser("clear", aliases=["revert"],
                             help="Revert a flag to off")
    p_clear.add_argument("flag", help="Flag name")
    p_clear.set_defaults(func=cmd_clear)

    # trigger-all
    p_all = sub.add_parser("trigger-all", aliases=["inject-all"],
                           help="Trigger all faults at once")
    p_all.add_argument("--duration", "-d", type=int, default=None,
                       help="Auto-reset after N seconds")
    p_all.add_argument("--dry-run", action="store_true",
                       help="Show what would be triggered without applying")
    p_all.set_defaults(func=cmd_trigger_all)

    # reset
    p_reset = sub.add_parser("reset", help="Reset all flags to off")
    p_reset.set_defaults(func=cmd_reset)

    # scenario
    p_sc = sub.add_parser("scenario", help="Preset incident drills")
    sc_sub = p_sc.add_subparsers(dest="scenario_command", metavar="ACTION")

    p_sc_list = sc_sub.add_parser("list", help="List preset scenarios")
    p_sc_list.set_defaults(func=cmd_scenario_list)

    p_sc_apply = sc_sub.add_parser("apply", help="Apply a preset scenario")
    p_sc_apply.add_argument("name", help="Scenario name")
    p_sc_apply.add_argument("--duration", "-d", type=int, default=None,
                            help="Auto-revert after N seconds")
    p_sc_apply.set_defaults(func=cmd_scenario_apply)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)

    args.func(args)
