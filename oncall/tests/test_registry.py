from oncall.contracts import Fact, Signal, ToolOutput
from oncall.ledger import EvidenceLedger
from oncall.tools.registry import REGISTRY, tool


@tool(
    name="test_registry_tool",
    description="test",
    params={"service": {"type": "string"}},
    required=["service"],
)
def registry_test_tool(service: str) -> ToolOutput:
    return ToolOutput(
        text="x" * 2000,
        facts=[Fact(signal=Signal.TRACE, summary=f"service={service}")],
    )


def test_registry_tags_and_truncates():
    ledger = EvidenceLedger()
    result = REGISTRY.call("test_registry_tool", {"service": "payment"}, ledger)
    assert "[E-001]" in result
    assert len(result) <= 1800
    assert ledger.has("E-001")


def test_registry_rejects_banned_argument():
    result = REGISTRY.call("test_registry_tool", {"service": "flagd"}, EvidenceLedger())
    assert result.startswith("Error:")


def test_registry_event_emission(tmp_path):
    from oncall.events import EventLog
    ledger = EvidenceLedger()
    events = EventLog("test-run", runs_dir=str(tmp_path))
    result = REGISTRY.call("test_registry_tool", {"service": "payment"}, ledger, events=events)
    assert "[E-001]" in result
    event_file = tmp_path / "test-run" / "events.jsonl"
    lines = event_file.read_text().splitlines()
    assert len(lines) == 2  # tool_call, tool_result
