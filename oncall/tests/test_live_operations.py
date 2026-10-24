# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
Automated Test Suite for Refactored Live-Only AI On-Call Operations Console.
Verifies all 5 core acceptance criteria domains:
1. Live Telemetry Ingress & State Management
2. Root-Cause Diagnosis & Causal DAG Isolation
3. Strict Safety Barrier, Token Authorization & Invalidation
4. Post-Mortem Report Generation Constraints (Execution Prerequisite)
5. UI Contracts & Single Source of Truth
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from oncall.models import IncidentAlert, IncidentRecord, RootCauseDiagnosis, TelemetryObservation, TelemetryCitation
from oncall.agent import AIOnCallAgent
from oncall.safety.reviewer_agent import ReviewerAgent
from oncall.safety.approval_gate import HumanApprovalGate
from oncall.actions.action_manager import ActionManager
from oncall.reporter import IncidentReporter
from oncall.tools.prometheus import PrometheusTool
from oncall.tools.jaeger import JaegerTool
from oncall.tools.opensearch import OpenSearchTool
from oncall.live_manager import LiveIncidentManager
from oncall.ui import HTML_TEMPLATE


# ==============================================================================
# Domain 1: Live Telemetry Ingress & State Management
# ==============================================================================

def test_missing_telemetry_never_treated_as_zero_or_healthy():
    """Verify that when Prometheus fails, service is NOT marked healthy or zero."""
    tool = PrometheusTool()
    with patch.object(tool, "query", return_value={"status": "error", "error": "timeout"}):
        obs = tool.inspect_service_metrics("cart", allow_fixtures=False)
        assert obs.success is False
        assert obs.data["status"] == "UNKNOWN"
        assert obs.data["p95_latency_ms"] is None
        assert obs.data["error_rate_rps"] is None


def test_snapshots_and_current_measurements_remain_separate():
    """Ensure triggering snapshot is strictly separated from current live telemetry."""
    alert = IncidentAlert(
        alert_id="INC-FRONTEND-TEST-1",
        service_name="frontend",
        title="FrontendLatencySpike",
        summary="Frontend latency spike detected",
        snapshot_p95_ms=5420.0,
        snapshot_error_rate_rps=12.0,
        snapshot_timestamp_utc="2026-10-24T04:46:34Z"
    )
    agent = AIOnCallAgent()
    
    # Mock current live query observing recovered latency (110ms)
    mock_obs = TelemetryObservation(
        tool_name="prometheus_inspect_service",
        success=True,
        summary="Current live metrics nominal",
        data={
            "p95_latency_sec": 0.110,
            "p95_latency_ms": 110.0,
            "error_rate_rps": 0.0,
            "throughput_rps": 45.0,
            "evaluation_time_utc": "2026-10-24T05:00:00Z",
            "query_window": "5m sliding rate",
            "live": True
        }
    )
    with patch.object(agent.prom_tool, "inspect_service_metrics", return_value=mock_obs):
        diag = agent.investigate(alert, allow_fixtures=True)
        assert diag.incident_snapshot["trigger_p95_latency_ms"] == 5420.0
        assert diag.current_telemetry["current_p95_latency_ms"] == 110.0
        assert diag.telemetry_reconciliation_status == "RECOVERED_SINCE_TRIGGER"
        assert diag.incident_snapshot["trigger_p95_latency_ms"] != diag.current_telemetry["current_p95_latency_ms"]


# ==============================================================================
# Domain 2: Root-Cause Diagnosis & Causal DAG Isolation
# ==============================================================================

def test_downstream_dependency_isolation_checkout_to_payment():
    """Verify that a bottleneck in payment is not attributed to caller checkout."""
    agent = AIOnCallAgent()
    alert = IncidentAlert(
        alert_id="INC-CHECKOUT-TEST-2",
        service_name="checkout",
        title="CheckoutOrderErrors",
        summary="Checkout order placement errors",
        snapshot_p95_ms=2510.0
    )
    diag = agent.investigate(alert, allow_fixtures=True)
    assert diag.target_service == "checkout"
    assert diag.root_cause_service == "payment"
    assert diag.is_downstream is True
    assert "DOWNSTREAM" in diag.failure_mode
    assert diag.trace_summary["downstream_service"] == "payment"


def test_missing_logs_reported_honestly_as_no_data():
    """Verify that when 0 logs match a trace, NO_DATA is recorded without false corroboration."""
    tool = OpenSearchTool()
    with patch.object(tool, "base_url", "http://invalid-opensearch-host:9999"):
        obs = tool.query_logs(service_name="checkout", trace_id="nonexistent-trace-id", allow_fixtures=False)
        assert obs.data["logs"] == []
        assert "0 matching logs found" in obs.summary


def test_unverified_repo_history_not_claimed_as_deployment():
    """Ensure git commit history is tagged strictly as REPOSITORY_COMMIT_CONTEXT_ONLY."""
    agent = AIOnCallAgent()
    alert = IncidentAlert(alert_id="INC-CART-3", service_name="cart", title="CartTimeout", summary="Cart timeout")
    diag = agent.investigate(alert, allow_fixtures=True)
    assert diag.deployment_evidence_type == "REPOSITORY_COMMIT_CONTEXT_ONLY"


# ==============================================================================
# Domain 3: Strict Safety Barrier, Token Authorization & Invalidation
# ==============================================================================

def test_action_manager_rejects_without_auth_token():
    """Verify that ActionManager refuses to execute any action without an AUTH- token."""
    manager = ActionManager()
    res = manager.execute_action("RESTART_CONTAINER", "frontend", auth_token=None)
    assert res["success"] is False
    assert "SECURITY VIOLATION" in res["error"]


def test_action_manager_blocks_blacklisted_infrastructure():
    """Ensure critical databases and collectors cannot be restarted."""
    manager = ActionManager()
    res = manager.execute_action("RESTART_CONTAINER", "valkey-cart", auth_token="AUTH-VALID-1234")
    assert res["success"] is False
    assert "SAFETY VIOLATION" in res["error"]


def test_no_action_required_requires_no_approval_panel():
    """Verify that when service is nominal, approval gate returns NO_ACTION_REQUIRED."""
    gate = HumanApprovalGate()
    diag = RootCauseDiagnosis(
        incident_id="INC-SHIPPING-1",
        target_service="shipping",
        root_cause_service="shipping",
        failure_mode="NORMAL_BASELINE_HEALTH",
        confidence_score=0.95,
        action_type="NO_ACTION",
        action_status="NOT_REQUIRED",
        recommended_action="No action required.",
        explanation="Service is nominal."
    )
    decision = gate.request_approval(diag, {"action": "NO_ACTION"})
    assert decision.approved is False
    assert decision.token == "NO_ACTION_REQUIRED"


def test_obsolete_action_invalidated_if_incident_auto_recovers():
    """Verify that if live telemetry normalizes before approval, action is blocked."""
    manager = LiveIncidentManager.get_instance()
    
    # Create an active incident awaiting approval
    inc = IncidentRecord(
        incident_id="INC-AUTO-REC-1",
        alerted_service="cart",
        title="CartTimeout",
        threshold_ms=500.0,
        current_status="AWAITING_APPROVAL",
        root_cause_service="cart",
        proposed_remediation={"action_type": "RESTART_CONTAINER", "target_service": "cart", "reason": "Timeout"}
    )
    with manager._state_lock:
        manager.active_incidents["INC-AUTO-REC-1"] = inc

    # Mock live re-check: cart is now healthy (25ms < 500ms)
    mock_obs = TelemetryObservation(
        tool_name="prometheus_inspect_service",
        success=True,
        summary="Healthy",
        data={"p95_latency_ms": 25.0, "status": "HEALTHY"}
    )
    with patch.object(manager.prom_tool, "inspect_service_metrics", return_value=mock_obs):
        res = manager.approve_remediation("INC-AUTO-REC-1")
        assert res["success"] is False
        assert res["action_status"] == "SUPERSEDED"
        assert "has already recovered" in res["error"]


# ==============================================================================
# Domain 4: Post-Mortem Report Generation Constraints
# ==============================================================================

def test_no_report_on_diagnosis_alone():
    """Verify that creating an incident record has NO post-mortem report initially."""
    inc = IncidentRecord(
        incident_id="INC-REPORT-1",
        alerted_service="payment",
        title="PaymentSpike",
        current_status="AWAITING_APPROVAL"
    )
    assert inc.post_mortem_report is None


def test_no_report_for_no_action_required():
    """Verify that a NO_ACTION_REQUIRED incident has NO post-mortem report."""
    inc = IncidentRecord(
        incident_id="INC-REPORT-2",
        alerted_service="shipping",
        title="ShippingNominal",
        current_status="NO_ACTION_REQUIRED",
        approval_status="NOT_REQUIRED"
    )
    assert inc.post_mortem_report is None


def test_report_generated_only_after_successful_action_execution():
    """Verify report is generated after Action API execution and attached to incident."""
    manager = LiveIncidentManager.get_instance()
    inc = IncidentRecord(
        incident_id="INC-EXEC-REPORT-3",
        alerted_service="frontend",
        title="FrontendSpike",
        threshold_ms=1000.0,
        current_status="AWAITING_APPROVAL",
        root_cause_service="frontend-proxy",
        proposed_remediation={"action_type": "RESTART_CONTAINER", "target_service": "frontend-proxy", "reason": "Proxy bottleneck"}
    )
    with manager._state_lock:
        manager.active_incidents["INC-EXEC-REPORT-3"] = inc

    # Mock degraded recheck, successful action, and verified recovery
    mock_recheck = TelemetryObservation(
        tool_name="prometheus_inspect_service",
        success=True,
        summary="Degraded",
        data={"p95_latency_ms": 2500.0, "status": "CRITICAL"}
    )
    with patch.object(manager.prom_tool, "inspect_service_metrics", return_value=mock_recheck), \
         patch.object(manager.action_mgr, "execute_action", return_value={"success": True, "message": "Container restarted"}), \
         patch.object(manager.verifier, "verify_recovery", return_value={"recovered": True, "verification_duration_seconds": 10.0}):
        
        res = manager.approve_remediation("INC-EXEC-REPORT-3")
        assert res["success"] is True
        assert res["action_status"] == "EXECUTED"
        assert res["verification_status"] == "RECOVERED"
        assert res["post_mortem_report"] is not None
        assert "# Incident Post-Mortem" in res["post_mortem_report"]
        assert inc.post_mortem_report is not None


# ==============================================================================
# Domain 5: UI Contracts & Removal of Test-Scenario Sidebar
# ==============================================================================

def test_ui_has_no_test_scenario_sidebar_or_controls():
    """Verify that the production UI HTML contains zero test-scenario sidebar elements."""
    assert "Incident Scenarios (Test Suite)" not in HTML_TEMPLATE
    assert "btn-frontend_degraded_performance" not in HTML_TEMPLATE
    assert "btn-cart_datastore_timeout" not in HTML_TEMPLATE
    assert "btn-checkout_downstream_payment" not in HTML_TEMPLATE
    assert "btn-shipping_nominal_baseline" not in HTML_TEMPLATE
    assert "SCENARIOS" not in HTML_TEMPLATE
    assert "loadIncident(" not in HTML_TEMPLATE
