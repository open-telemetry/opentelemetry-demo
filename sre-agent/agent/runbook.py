"""Step 4 - PROPOSE a safe fix: exactly one allowlisted action, with a short reason and its rollback."""
import yaml

from agent import config, topology

RB = yaml.safe_load((config.ROOT / "config" / "runbook.yaml").read_text(encoding="utf-8"))


def _rollback(action: dict):
    a, p = action["action"], action["params"]
    if a == "toggle_flag":
        return None  # turning a failure flag OFF is the fix itself; re-enabling it would re-break the system
    if a == "throttle_load":
        return {"action": "throttle_load", "params": {"users": RB["throttle"]["users_normal"]}}
    if a == "scale_service":
        return {"action": "scale_service", "params": {"service": p["service"], "replicas": 1}}
    return None  # a restart cannot be undone -> escalate if it did not help


def propose(diagnosis: dict) -> dict:
    """Returns {"action", "params", "reason", "rollback"} or {"action": "escalate", "reason"}."""
    rc = diagnosis["root_cause"]
    svc, ft = rc["service"], rc["fault_type"]
    if diagnosis.get("status") != "diagnosed":
        return {"action": "escalate", "reason": diagnosis.get("escalation_reason") or "not confident"}
    choice = RB["by_fault_type"].get(ft, "escalate")
    flags = RB.get("service_flags", {}).get(svc, {})
    flag = flags.get(ft) or flags.get("default")

    if choice == "flag_or_restart":
        if RB.get("enable_flag_remediation") and flag:
            choice = "toggle_flag"
        else:
            choice = "restart_service"
    if choice == "scale_service" and RB.get("platform") != "kubernetes":
        return {"action": "escalate", "reason": f"{svc} looks resource-starved; scaling is only available on "
                                                f"Kubernetes, so a human must raise its CPU/memory limits."}
    if choice == "restart_service" and svc in RB.get("never_restart", []):
        return {"action": "escalate", "reason": f"{svc} is observability/infra tooling - not restarted automatically."}
    if choice == "restart_service" and svc not in topology.APP_CONTAINERS:
        return {"action": "escalate", "reason": f"'{svc}' is not a known container; cannot pick a safe action."}

    if choice == "restart_service":
        act = {"action": "restart_service", "params": {"service": svc},
               "reason": f"{svc} is the root cause ({ft}); a restart restores a clean process/connection state."}
    elif choice == "toggle_flag":
        act = {"action": "toggle_flag", "params": {"flag": flag, "variant": RB.get("off_variant", "off")},
               "reason": f"{svc} shows an application-level {ft}; turning off its fault-injection flag "
                         f"'{flag}' removes the cause (a restart would not)."}
    elif choice == "throttle_load":
        act = {"action": "throttle_load", "params": {"users": RB["throttle"]["users_during_incident"]},
               "reason": "Traffic far above baseline overloads the shop; throttle the load generator."}
    elif choice == "scale_service":
        act = {"action": "scale_service", "params": {"service": svc, "replicas": 2},
               "reason": f"{svc} is saturated; add a replica."}
    else:
        return {"action": "escalate", "reason": f"No safe runbook action for fault type '{ft}'."}
    if act["action"] not in RB["allowlist"]:
        return {"action": "escalate", "reason": f"{act['action']} is not on the allowlist."}
    act["rollback"] = _rollback(act)
    act["target_service"] = svc
    return act
