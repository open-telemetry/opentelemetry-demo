"""
test_harshita.py - Test script for Harshita's module.
Simulates Neha's real Evidence returns to verify the citation gate.
"""
import os
from datetime import datetime, timezone, timedelta
from Bosch.new.LLM_brain.agent.brain.models import Incident, Evidence, ToolStatus, TimeWindow
from Bosch.new.LLM_brain.agent.brain.investigator import HarshitaBrain
from dotenv import load_dotenv

load_dotenv()

# 1. Mock Neha's Telemetry Tool (generates real Evidence objects)
def mock_neha_telemetry(tool_name: str, args: dict) -> Evidence:
    print(f"\n[Tool Invocated] -> {tool_name} with args: {args}")
    now = datetime.now(timezone.utc)
    window = TimeWindow(start_time=now - timedelta(minutes=10), end_time=now)

    if tool_name == "query_traces":
        return Evidence(
            evidence_id="ev-tra-3873a079",
            status=ToolStatus.OK,
            source="jaeger",
            service=args.get("service_name", "frontend"),
            event_time_window=window,
            tool="query_traces",
            query=f"service={args.get('service_name')}&status=error",
            observed_value={"span": "GetCart", "child_error": "valkey connection timeout", "status_code": 500},
            trace_or_log_id="3873a079-trace-uuid"
        )
    elif tool_name == "query_metrics":
        return Evidence(
            evidence_id="ev-met-a1b2c3d4",
            status=ToolStatus.OK,
            source="prometheus",
            service=args.get("service_name", "cart"),
            event_time_window=window,
            tool="query_metrics",
            query=args.get("query", ""),
            observed_value={"error_rate": 0.45, "p99_latency_ms": 3200}
        )
    elif tool_name == "query_logs":
        return Evidence(
            evidence_id="ev-log-99f8e7d6",
            status=ToolStatus.OK,
            source="opensearch",
            service=args.get("service_name", "cart"),
            event_time_window=window,
            tool="query_logs",
            query=args.get("query_string", "error"),
            observed_value="Stack trace: Valkey.Redis.ConnectionTimeout: Pool exhausted"
        )
    
    return Evidence(
        evidence_id="ev-empty-0000",
        status=ToolStatus.EMPTY,
        source="health",
        service="unknown",
        event_time_window=window,
        tool=tool_name,
        query="",
        observed_value=None
    )

# 2. Run the test
if __name__ == "__main__":
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable is missing.")
        exit(1)

    now = datetime.now(timezone.utc)
    sample_incident = Incident(
        id="INC-20261023-001",
        source="alertmanager",
        symptom="Elevated 500 status codes on /api/cart",
        affected_service="frontend",
        detection_time=now,
        observation_window=TimeWindow(start_time=now - timedelta(minutes=15), end_time=now),
        recovery_condition="frontend HTTP 500 error rate < 0.01 for 2 consecutive minutes"
    )

    print("=== Testing Harshita's Anthropic SRE Brain ===")
    brain = HarshitaBrain(max_turns=4)
    diagnosis, evidence_list = brain.investigate(sample_incident, mock_neha_telemetry)

    print("\n" + "="*50)
    print("DIAGNOSIS PRODUCED:")
    print("="*50)
    print(f"Suspected Component: {diagnosis.suspected_component}")
    print(f"Suspected Cause:     {diagnosis.suspected_cause}")
    print(f"Confidence Label:    {diagnosis.confidence_label.value}")
    print(f"Supporting Evidence: {diagnosis.supporting_evidence_ids}")
    print(f"Conflicting Evidence:{diagnosis.conflicting_evidence_ids}")
    print(f"Alternatives:        {diagnosis.alternatives}")
    print(f"Uncertainty:         {diagnosis.uncertainty}")
    print(f"Next Step:           {diagnosis.next_step}")

    # 3. Simulate Aditya's Citation Integrity Gate
    print("\n[Simulating Aditya's validate_citations() Gate]:")
    valid_ids = {e.evidence_id for e in evidence_list}
    all_cited = set(diagnosis.supporting_evidence_ids + diagnosis.conflicting_evidence_ids)
    hallucinated = all_cited - valid_ids

    if hallucinated:
        print(f"FAILED: Found hallucinated IDs: {hallucinated}")
    else:
        print("PASSED: 100% Citation Integrity! All cited evidence IDs were produced by Neha.")