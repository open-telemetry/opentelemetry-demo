"""Tool schemas, argument checks and compact views (no network, no LLM)."""
import json
from pathlib import Path

import pytest

from dev.faultctl.catalog import CATALOGUE
from oncall import prompts, toolbox
from oncall.loop import SUBMIT_SPEC
from tests.test_leak import FLAG_KEYS, OTHER_FORBIDDEN, leaks
from tools.ledger import Ledger
from tools.result import ToolResult, backend_error

REPO = Path(__file__).resolve().parent.parent
FIXTURES = sorted((REPO / "tests" / "fixtures" / "ledgers").glob("*.json"))
HIDDEN_PARAMS = {"base_url", "http_get", "http_post", "runner", "project", "include_stats"}


def ledger_from(path: Path) -> Ledger:
    """Replay a recorded live ledger into a fresh one (the sanitiser runs again, as it would live)."""
    ledger = Ledger()
    for recorded in json.loads(path.read_text(encoding="utf-8")):
        ledger.add(recorded["tool"], recorded["arguments"], ToolResult(**recorded["result"]))
    return ledger


def leaves(node) -> set[str]:
    """Every scalar in a JSON structure, as its JSON text (so 1.0 and "1.0" differ)."""
    if isinstance(node, dict):
        return set().union(*(leaves(v) for v in node.values())) if node else set()
    if isinstance(node, list):
        return set().union(*(leaves(v) for v in node)) if node else set()
    return {json.dumps(node)}


def test_there_are_recorded_ledgers():
    assert len(FIXTURES) >= 3


@pytest.mark.parametrize("name", sorted(toolbox.TOOLS))
def test_schema_is_generated_from_the_signature_and_hides_test_hooks(name):
    tool = toolbox.TOOLS[name]
    schema = tool.spec().parameters
    assert schema["type"] == "object"
    assert set(schema["properties"]) == set(tool.exposed)
    assert not HIDDEN_PARAMS & set(schema["properties"])
    assert schema["required"] == []
    json.dumps(schema)  # serialisable


def test_schema_types_limits_and_defaults():
    traces = toolbox.TOOLS["query_traces"].spec().parameters["properties"]
    assert traces["mode"]["enum"] == ["errors", "slow"] and traces["mode"]["type"] == "string"
    assert traces["window_minutes"]["type"] == "integer" and traces["window_minutes"]["maximum"] == 30
    assert traces["limit"]["default"] == 4  # the loop's own default, not the tool's
    assert traces["window_minutes"]["default"] == 10
    assert toolbox.TOOLS["query_logs"].spec().parameters["properties"]["window_minutes"]["default"] == 10
    assert toolbox.TOOLS["query_logs"].spec().parameters["properties"]["window_minutes"]["maximum"] == 30
    assert toolbox.TOOLS["query_metrics"].spec().parameters["properties"]["window_minutes"]["default"] == 5
    assert "default" not in traces["service"]  # None is "not given", not a default
    metrics = toolbox.TOOLS["query_metrics"].spec().parameters["properties"]
    assert metrics["window_minutes"]["minimum"] == 2 and metrics["top_n"]["maximum"] == 10


def test_argument_checks():
    metrics = toolbox.TOOLS["query_metrics"]
    assert toolbox.validate_arguments(metrics, {}) == {"window_minutes": 5, "top_n": 6}
    assert toolbox.validate_arguments(metrics, {"window_minutes": 30, "service": None}) == {"window_minutes": 30, "top_n": 6}
    for bad in ({"bogus": 1}, {"window_minutes": "5"}, {"window_minutes": True}, {"service": 3}):
        with pytest.raises(toolbox.ArgumentError):
            toolbox.validate_arguments(metrics, bad)
    with pytest.raises(toolbox.ArgumentError):
        toolbox.validate_arguments(toolbox.TOOLS["query_traces"], {"mode": "bogus"})
    with pytest.raises(toolbox.ArgumentError):
        toolbox.validate_arguments(toolbox.TOOLS["container_health"], {"include_stats": False})


def test_out_of_range_is_an_argument_error_and_a_crash_is_a_backend_error():
    def explode(**_):
        raise RuntimeError("boom")

    def too_big(**_):
        raise ValueError("limit must be between 1 and 20")

    crashing = toolbox.Tool("query_logs", "d", explode, (), {})
    result = toolbox.call_tool(crashing, {})
    assert result.state == "backend_error" and "RuntimeError: boom" in result.error
    with pytest.raises(toolbox.ArgumentError, match="between 1 and 20"):
        toolbox.call_tool(toolbox.Tool("query_logs", "d", too_big, (), {}), {})


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_every_string_and_number_in_a_view_is_verbatim_in_the_ledger_entry(path):
    ledger = ledger_from(path)
    for entry in ledger.list():
        view = toolbox.compact_view(entry)
        assert view["id"] == entry.id
        assert leaves({k: v for k, v in view.items() if k != "id"}) <= leaves(entry.result), entry.id


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_views_are_much_smaller_than_the_ledger_entries(path):
    for entry in ledger_from(path).list():
        assert len(toolbox.view_text(toolbox.compact_view(entry))) < 0.7 * len(json.dumps(entry.result)), entry.id


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_views_and_findings_carry_no_flag_data(path):
    for entry in ledger_from(path).list():
        view = toolbox.compact_view(entry)
        assert leaks(toolbox.view_text(view)) == []
        line = toolbox.finding_line(view, entry.tool)
        assert line.startswith(f"{entry.id}: ") and leaks(line) == [] and len(line) < 200


def test_container_view_lists_only_abnormal_containers_and_a_summary():
    ledger = ledger_from(REPO / "tests" / "fixtures" / "ledgers" / "live_container_fault.json")
    entry = next(e for e in ledger.list() if e.tool == "container_health")
    view = toolbox.compact_view(entry)
    expected = {c["name"] for c in entry.result["items"] if toolbox._abnormal_container(c)}
    assert {c["name"] for c in view["abnormal"]} == expected
    assert len(view["abnormal"]) < len(entry.result["items"])
    assert view["summary"]["total"] == entry.result["extra"]["summary"]["total"]
    stopped = entry.result["extra"]["summary"]["not_running"]
    assert stopped and set(stopped) <= expected
    assert stopped[0] in toolbox.finding_line(view, "container_health")


def test_deploy_view_lists_only_containers_marked_restarted():
    ledger = ledger_from(REPO / "tests" / "fixtures" / "ledgers" / "live_container_fault.json")
    entry = next(e for e in ledger.list() if e.tool == "deploy_history")
    view = toolbox.compact_view(entry)
    marked = {c["name"] for c in entry.result["items"] if c["restarted_recently"]}
    assert {c["name"] for c in view["restarted_recently"]} == marked
    assert len(view["restarted_recently"]) < len(entry.result["items"])


def test_a_backend_error_or_empty_answer_is_stated_outright_never_as_healthy():
    ledger = Ledger()
    error = ledger.add("query_logs", {}, backend_error("query_logs", ["q"], {}, "OpenSearch unreachable: boom"))
    empty = ledger.add("query_traces", {}, ToolResult("query_traces", "no_data", ["q"], {}, notes=["found nothing; this is NOT a healthy signal", "3 items removed by sanitiser"]))
    bad = toolbox.compact_view(error)
    assert bad == {"id": "L1", "state": "backend_error", "error": "OpenSearch unreachable: boom", "notes": []}
    none = toolbox.compact_view(empty)
    assert none["state"] == "no_data" and none["notes"] == ["found nothing; this is NOT a healthy signal"]
    assert toolbox.finding_line(bad, "query_logs").startswith("L1: backend_error - OpenSearch unreachable")


def test_prompt_and_tool_text_are_generic():
    """Nothing the model is told may name a fault, a flag, or the services the catalogue breaks."""
    words = [i.id for i in CATALOGUE.values()] + [i.target for i in CATALOGUE.values()] + FLAG_KEYS + OTHER_FORBIDDEN
    texts = [prompts.system_prompt(10), prompts.DEFAULT_SYMPTOM, json.dumps(SUBMIT_SPEC.parameters), SUBMIT_SPEC.description]
    for tool in toolbox.TOOLS.values():
        texts += [tool.description, json.dumps(tool.spec().parameters)]
    for path in sorted((REPO / "oncall").glob("*.py")):
        texts.append(path.read_text(encoding="utf-8"))
    joined = "\n".join(texts).lower()
    assert [w for w in words if w.lower() in joined] == []


def test_prompt_carries_the_tuned_reasoning_guidance():
    text = prompts.system_prompt(11)
    for phrase in ("not running", "strong root-cause candidate", "WHEN each anomaly began", "otherwise say it is unknown",
                   "short window (5 to 10 minutes)", "may be stale", "every abnormal container", "Prefer distinctive evidence"):
        assert phrase in text, phrase


def test_clamp_caps_windows_at_30_and_reports_what_it_cut():
    assert toolbox.clamp_arguments({"window_minutes": 90, "limit": 5}) == (
        {"window_minutes": 30, "limit": 5}, {"window_minutes": {"requested": 90, "used": 30}})
    assert toolbox.clamp_arguments({"window_minutes": 30}) == ({"window_minutes": 30}, {})
    assert toolbox.clamp_arguments({"limit": 5}) == ({"limit": 5}, {})


def test_every_query_tool_says_the_maximum_window():
    for name in ("query_metrics", "query_traces", "query_logs"):
        tool = toolbox.TOOLS[name]
        assert "at most 30 minutes" in tool.description
        assert "at most 30" in tool.spec().parameters["properties"]["window_minutes"]["description"]


def test_prompt_ties_start_times_to_the_shortest_window_and_asks_for_a_rejected_hypothesis():
    text = prompts.system_prompt(11)
    assert "SHORTEST window that shows the problem" in text
    assert "at least one rejected hypothesis whenever any other service or container also looked abnormal" in text


def test_prompt_explains_the_change_line_without_growing_much():
    text = prompts.system_prompt(11)
    for phrase in ('"change" line', "got worse recently", "always like this", "absent now", "began more than"):
        assert phrase in text, phrase
    assert len(text.splitlines()) <= 62
