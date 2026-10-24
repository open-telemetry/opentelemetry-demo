# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0
"""CLI interface for Hands: human approvals, kill switch, dispatch, and verification."""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tomllib

from .adapter import ActionApiAdapter
from .approval import ApprovalGate
from .executor import HandsExecutor
from .kill_switch import KillSwitch
from .models import ActionPlan, utc_now_iso
from .store import HandsStore
from .verifier import RecoveryVerifier


def load_config(config_path: str) -> dict:
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with p.open("rb") as f:
        return tomllib.load(f)


def build_components(cfg: dict):
    data_dir = cfg.get("data_dir", "/tmp/hands-data")
    store = HandsStore(data_dir)
    kill_switch = KillSwitch(store)
    approval_gate = ApprovalGate(store, kill_switch)

    adapter_cfg = cfg.get("adapter", {})
    adapter_cfg["services"] = cfg.get("safety", {}).get("services", [])
    adapter = ActionApiAdapter(adapter_cfg)

    # Telemetry query function using f02 if available
    f02_cfg_path = cfg.get("f02_config")
    query_fn = None
    if f02_cfg_path and Path(f02_cfg_path).exists():
        try:
            from incident_tools.f02 import ObservabilityTools
            obs_tools = ObservabilityTools(f02_cfg_path)

            def f02_query(service, metric, start, end):
                return obs_tools.call(
                    "query_metrics",
                    {"service": service, "metric": metric, "start": start, "end": end},
                )

            query_fn = f02_query
        except Exception:
            query_fn = None

    verifier = RecoveryVerifier(query_fn=query_fn)
    executor = HandsExecutor(store, approval_gate, kill_switch, adapter, verifier)
    return store, kill_switch, approval_gate, adapter, verifier, executor


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to operator TOML configuration")
    sub = parser.add_subparsers(dest="command", required=True)

    # status
    sub.add_parser("status", help="Show kill switch status, recent plans, approvals, and audits")

    # plan
    plan_parser = sub.add_parser("plan", help="Validate and register a proposed remediation plan")
    plan_parser.add_argument("--file", required=True, help="JSON file containing the plan")

    # approve
    approve_parser = sub.add_parser("approve", help="Explicitly approve a remediation plan")
    approve_parser.add_argument("--digest", required=True, help="Plan digest (SHA-256)")
    approve_parser.add_argument("--operator", required=True, help="Operator name or identifier")
    approve_parser.add_argument("--reason", default="", help="Approval justification")
    approve_parser.add_argument("--ttl-minutes", type=int, default=15, help="Validity duration in minutes")

    # reject
    reject_parser = sub.add_parser("reject", help="Explicitly reject a remediation plan")
    reject_parser.add_argument("--digest", required=True, help="Plan digest (SHA-256)")
    reject_parser.add_argument("--operator", required=True, help="Operator name or identifier")
    reject_parser.add_argument("--reason", required=True, help="Rejection rationale")

    # dispatch
    dispatch_parser = sub.add_parser("dispatch", help="Execute an approved plan through safety gates")
    dispatch_parser.add_argument("--digest", required=True, help="Plan digest (SHA-256)")
    dispatch_parser.add_argument("--dry-run", action="store_true", help="Perform validation without executing mutations")

    # kill
    kill_parser = sub.add_parser("kill", help="Engage the durable emergency stop latch")
    kill_parser.add_argument("--operator", required=True, help="Operator name")
    kill_parser.add_argument("--reason", required=True, help="Reason for engaging kill switch")

    # reset-kill
    reset_parser = sub.add_parser("reset-kill", help="Reset the durable emergency stop latch")
    reset_parser.add_argument("--operator", required=True, help="Operator name")
    reset_parser.add_argument("--reason", required=True, help="Reason for clearing kill switch")

    args = parser.parse_args()

    try:
        cfg = load_config(args.config)
        store, kill_switch, approval_gate, adapter, verifier, executor = build_components(cfg)

        if args.command == "status":
            ks = kill_switch.status()
            plans = store.list_plans(limit=5)
            audits = store.list_audits(limit=5)
            out = {
                "kill_switch": ks,
                "recent_plans": [p.get("plan_digest") for p in plans],
                "recent_audits": audits,
            }
            print(json.dumps(out, indent=2))
            return 0

        elif args.command == "kill":
            res = kill_switch.engage(operator=args.operator, reason=args.reason)
            print(json.dumps({"kill_switch": res}, indent=2))
            return 0

        elif args.command == "reset-kill":
            res = kill_switch.reset(operator=args.operator, reason=args.reason)
            print(json.dumps({"kill_switch": res}, indent=2))
            return 0

        elif args.command == "plan":
            plan_file = Path(args.file)
            if not plan_file.exists():
                print(f"Error: plan file not found: {args.file}", file=sys.stderr)
                return 1
            with plan_file.open("r", encoding="utf-8") as f:
                plan_raw = json.load(f)

            allowed = set(cfg.get("safety", {}).get("services", []))
            plan = ActionPlan(plan_raw, allowed_services=allowed)
            store.save_plan(plan.to_dict())
            print(json.dumps({
                "message": "Plan registered successfully",
                "plan_digest": plan.digest,
                "action_type": plan.action_type,
                "target": plan.target,
                "incident_id": plan.incident_id,
            }, indent=2))
            return 0

        elif args.command == "approve":
            plan_data = store.get_plan(args.digest)
            if not plan_data:
                print(f"Error: Unknown plan digest: {args.digest}", file=sys.stderr)
                return 1

            expires_at = (datetime.now(timezone.utc) + timedelta(minutes=args.ttl_minutes)).isoformat().replace("+00:00", "Z")
            decision = approval_gate.record_decision(
                incident_id=plan_data["incident_id"],
                plan_digest=args.digest,
                decision="approved",
                operator=args.operator,
                reason=args.reason,
                expires_at=expires_at,
            )
            print(json.dumps({"approval": decision}, indent=2))
            return 0

        elif args.command == "reject":
            plan_data = store.get_plan(args.digest)
            if not plan_data:
                print(f"Error: Unknown plan digest: {args.digest}", file=sys.stderr)
                return 1

            decision = approval_gate.record_decision(
                incident_id=plan_data["incident_id"],
                plan_digest=args.digest,
                decision="rejected",
                operator=args.operator,
                reason=args.reason,
            )
            print(json.dumps({"approval": decision}, indent=2))
            return 0

        elif args.command == "dispatch":
            plan_data = store.get_plan(args.digest)
            if not plan_data:
                print(f"Error: Unknown plan digest: {args.digest}", file=sys.stderr)
                return 1

            allowed = set(cfg.get("safety", {}).get("services", []))
            plan = ActionPlan(plan_data, allowed_services=allowed)

            res = executor.dispatch(plan, dry_run=args.dry_run)
            print(json.dumps(res, indent=2))
            return 0 if res.get("success") else 1

        return 0
    except Exception as ex:
        print(f"Hands execution halted: {ex}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
