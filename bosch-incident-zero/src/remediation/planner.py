"""Deterministic map from a gated diagnosis to at most one allowlisted action and its rollback."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..agent.tools import EXCLUDED_SERVICES, TOOLING_CONTAINERS, TOPOLOGY
from ..agent.transcript import Transcript
from ..models.action import ACTION_CATALOG, IRREVERSIBLE_ACTIONS, ActionType, RemediationAction, is_allowlisted

LOAD_GENERATOR = "load-generator"
NON_TARGETS = EXCLUDED_SERVICES | (TOOLING_CONTAINERS - {LOAD_GENERATOR})
ACTIONABLE_CONFIDENCE = ("high", "medium")
ROLLBACK_REASONS = {
    ActionType.RESTORE_LOAD_GENERATOR: "Restore the load-generator rate that was in effect before the throttle.",
    ActionType.THROTTLE_LOAD_GENERATOR: "Throttle the load-generator again to the rate before the restore.",
    ActionType.SCALE_SERVICE: "Scale '{target}' back to the replica count it had before the action.",
}


@dataclass
class PlanDecision:
    action: Optional[RemediationAction]
    reason: str


def _build(transcript: Transcript, action_type: ActionType, target: str, reason: str,
           params: Optional[Dict[str, Any]] = None,
           rollback_params: Optional[Dict[str, Any]] = None) -> RemediationAction:
    root = (transcript.diagnosis or {}).get("root_cause") or {}
    action_id = f"ACT-{transcript.incident_id}"
    rollback = None
    rb_type = ACTION_CATALOG.get(action_type)
    if rb_type is not None:
        rb_reason = ROLLBACK_REASONS.get(rb_type, "Undo {action_id}.").format(target=target, action_id=action_id)
        rollback = RemediationAction(
            action_id=f"{action_id}-RB", action_type=rb_type, target_service=target, description=rb_reason,
            parameters={"reason": rb_reason, "rollback_of": action_id, **(rollback_params or {})})
    return RemediationAction(
        action_id=action_id, action_type=action_type, target_service=target, description=reason,
        parameters={"reason": reason, "diagnosed_service": root.get("service"),
                    "category": root.get("category"), **(params or {})},
        rollback=rollback, irreversible=action_type in IRREVERSIBLE_ACTIONS)


def plan_with_reason(transcript: Transcript, platform: str = "docker") -> PlanDecision:
    gate = transcript.gate or {}
    root = (transcript.diagnosis or {}).get("root_cause") or {}
    service = str(root.get("service") or "").strip()
    category = root.get("category") or "unknown"
    confidence = gate.get("final_confidence", "low")

    if not gate or gate.get("escalate", True):
        return PlanDecision(None, "the confidence gate escalated this incident to a human")
    if confidence not in ACTIONABLE_CONFIDENCE:
        return PlanDecision(None, f"confidence is {confidence}")
    if service in NON_TARGETS:
        return PlanDecision(None, f"'{service}' is excluded from remediation")
    if service not in TOPOLOGY:
        return PlanDecision(None, f"target '{service or 'unknown'}' is not a known demo service")

    flag = str(root.get("feature_flag") or "").strip()
    if flag:
        if flag not in transcript.evidence_index().all_text():
            return PlanDecision(None, f"feature flag '{flag}' is not named in any collected evidence")
        reason = f"{category} on '{service}' is tied to feature flag '{flag}' named in the evidence."
        return PlanDecision(_build(transcript, ActionType.SET_FEATURE_FLAG, service, reason,
                                   {"flag": flag, "state": "disabled"}), reason)

    if category == "traffic_spike":
        reason = (f"traffic_spike diagnosed on '{service}' ({confidence} confidence): reduce the synthetic "
                  f"load from {LOAD_GENERATOR}.")
        action = _build(transcript, ActionType.THROTTLE_LOAD_GENERATOR, LOAD_GENERATOR, reason)
    elif category in ("memory_growth", "cpu_saturation"):
        if platform != "kubernetes":
            return PlanDecision(None, f"{category} maps to SCALE_SERVICE, which needs Kubernetes "
                                      f"(DEPLOY_PLATFORM={platform})")
        reason = f"{category} diagnosed on '{service}' ({confidence} confidence): add one replica."
        action = _build(transcript, ActionType.SCALE_SERVICE, service, reason,
                        {"replicas_delta": 1}, {"replicas_delta": -1})
    elif category in ("container_down_or_restarting", "dependency_unreachable"):
        reason = f"{category} diagnosed on '{service}' ({confidence} confidence): restart '{service}'."
        action = _build(transcript, ActionType.RESTART_SERVICE, service, reason)
    else:
        return PlanDecision(None, f"no safe action is mapped for category '{category}'")

    if not is_allowlisted(action.action_type):
        return PlanDecision(None, f"{action.action_type.value} is not on the action allowlist")
    return PlanDecision(action, reason)


def plan_action(transcript: Transcript, platform: str = "docker") -> Optional[RemediationAction]:
    return plan_with_reason(transcript, platform).action
