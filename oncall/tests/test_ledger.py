from oncall.contracts import Fact, Signal
from oncall.ledger import EvidenceLedger


def test_ledger_assigns_ids_and_round_trips(tmp_path):
    ledger = EvidenceLedger()
    first = ledger.add("test", "{}", Fact(signal=Signal.LOG, summary="one"))
    second = ledger.add("test", "{}", Fact(signal=Signal.METRIC, summary="two"))
    assert first.id == "E-001"
    assert second.id == "E-002"
    assert ledger.has("E-001")
    assert ledger.signals_for(["E-001", "E-002"]) == {Signal.LOG, Signal.METRIC}
    path = tmp_path / "evidence.jsonl"
    ledger.dump_jsonl(str(path))
    assert len(path.read_text().splitlines()) == 2
