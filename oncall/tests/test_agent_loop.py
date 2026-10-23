import json

from oncall.agent.run import MAX_ITERATIONS, investigate
from oncall.contracts import Fact, Signal, ToolOutput
from oncall.events import EventLog
from oncall.ledger import EvidenceLedger
from oncall.llm import FakeLLM
from oncall.tools.registry import tool


@tool(name="loop_probe", description="test", params={"service": {"type": "string"}}, required=["service"])
def loop_probe(service: str) -> ToolOutput:
    return ToolOutput(text=f"probe {service}", facts=[Fact(signal=Signal.TRACE, summary=f"{service} errors")])


def _call(call_id: str = "1") -> dict:
    return {"tool_calls": [{"id": call_id, "name": "loop_probe", "arguments": {"service": "payment"}}]}


def _final(ids: list[str], confidence: float = 0.9, escalate: bool = False) -> str:
    return json.dumps({
        "root_cause_service": "payment", "fault_class": "app_error", "confidence": confidence,
        "summary": "payment fails", "evidence_ids": ids, "escalate": escalate, "next_steps": [],
    })


def _run(script, tmp_path):
    return investigate("checkout is failing", FakeLLM(script), EvidenceLedger(), EventLog("t", str(tmp_path)))


def test_valid_evidence_is_kept(tmp_path):
    diagnosis, made = _run([_call(), _final(["E-001"])], tmp_path)
    assert diagnosis.evidence_ids == ["E-001"]
    assert not diagnosis.escalate and diagnosis.confidence == 0.9
    assert made[0]["evidence"] == ["E-001"]


def test_invented_ids_are_stripped_and_force_escalation(tmp_path):
    diagnosis, _ = _run([_call(), _final(["E-001", "E-042"])], tmp_path)
    assert diagnosis.evidence_ids == ["E-001"]
    assert diagnosis.escalate and diagnosis.confidence <= 0.3


def test_only_invented_ids_escalate(tmp_path):
    diagnosis, _ = _run([_final(["E-007"])], tmp_path)
    assert diagnosis.evidence_ids == [] and diagnosis.escalate


def test_unparseable_answer_falls_back_to_escalation(tmp_path):
    diagnosis, _ = _run(["not json"] * MAX_ITERATIONS, tmp_path)
    assert diagnosis.escalate and diagnosis.fault_class == "unknown"


def test_loop_stops_at_iteration_cap(tmp_path):
    llm = FakeLLM([_call(str(i)) for i in range(MAX_ITERATIONS)])
    diagnosis, made = investigate("x", llm, EvidenceLedger(), EventLog("cap", str(tmp_path)))
    assert llm.calls == MAX_ITERATIONS and len(made) == MAX_ITERATIONS
    assert diagnosis.escalate
