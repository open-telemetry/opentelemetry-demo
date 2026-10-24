"""Deterministic planner: one allowlisted action with its rollback, or None to escalate."""
from __future__ import annotations

import pytest

from src.agent.transcript import Transcript
from src.models.action import ALLOWED_ACTION_TYPES, ActionType
from src.remediation.planner import plan_action, plan_with_reason


def transcript(category="traffic_spike", service="frontend", confidence="high", escalate=False, **root):
    t = Transcript(incident_id="INC-P", alert="alert")
    t.diagnosis = {"root_cause": {"service": service, "category": category, "summary": "s", **root}}
    t.gate = {"final_confidence": confidence, "escalate": escalate}
    return t


def test_traffic_spike_throttles_load_generator_with_restore_rollback():
    action = plan_action(transcript())
    assert action.action_type == ActionType.THROTTLE_LOAD_GENERATOR
    assert action.target_service == "load-generator"
    assert action.parameters["reason"] and action.parameters["diagnosed_service"] == "frontend"
    assert action.rollback.action_type == ActionType.RESTORE_LOAD_GENERATOR
    assert action.rollback.action_id == f"{action.action_id}-RB"
    assert {action.action_type, action.rollback.action_type} <= ALLOWED_ACTION_TYPES


@pytest.mark.parametrize("kwargs, why", [
    ({"escalate": True}, "escalated"),
    ({"confidence": "low"}, "confidence is low"),
    ({"service": "flagd"}, "excluded"),
    ({"service": "flagd-ui"}, "excluded"),
    ({"service": "jaeger"}, "excluded"),
    ({"service": "made-up"}, "not a known demo service"),
    ({"category": "errors_on_operation"}, "no safe action"),
    ({"category": "unknown"}, "no safe action"),
    ({"category": "memory_growth", "service": "email"}, "needs Kubernetes"),
])
def test_no_action_cases(kwargs, why):
    decision = plan_with_reason(transcript(**kwargs))
    assert decision.action is None
    assert why in decision.reason


def test_scale_only_on_kubernetes_and_paired_with_scale_back():
    action = plan_action(transcript(category="cpu_saturation", service="ad"), platform="kubernetes")
    assert action.action_type == ActionType.SCALE_SERVICE
    assert action.parameters["replicas_delta"] == 1
    assert action.rollback.parameters["replicas_delta"] == -1


def test_restart_is_irreversible_without_rollback():
    action = plan_action(transcript(category="container_down_or_restarting", service="cart"))
    assert action.action_type == ActionType.RESTART_SERVICE
    assert action.rollback is None and action.irreversible is True
    assert plan_action(transcript()).irreversible is False


def test_flag_toggle_needs_the_flag_named_in_evidence():
    decision = plan_with_reason(transcript(category="errors_on_operation", service="cart", feature_flag="someFlag"))
    assert decision.action is None and "not named in any collected evidence" in decision.reason
    no_flag = plan_action(transcript(category="errors_on_operation", service="cart"))
    assert no_flag is None
