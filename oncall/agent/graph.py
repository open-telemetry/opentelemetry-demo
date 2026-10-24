from __future__ import annotations

import re
from typing import Any, TypedDict

try:
    from langgraph.graph import END, StateGraph
except ImportError:
    END = None
    StateGraph = None

from oncall.agent.prompts import FINAL_REMINDER, SYSTEM_PROMPT
from oncall.agent.run import MAX_ITERATIONS, _assistant_message, _parse_diagnosis
from oncall.events import EventLog
from oncall.ledger import EvidenceLedger
from oncall.schema import Diagnosis
from oncall.tools import REGISTRY, load_all

class InvestigationState(TypedDict):
    messages: list[dict[str, Any]]
    made: list[dict[str, Any]]
    pending: list[dict[str, Any]]
    diagnosis: Diagnosis | None
    step: int


def _record(name: str, args: dict[str, Any], result: str) -> dict[str, Any]:
    return {"tool": name, "args": args, "ok": not result.startswith("Error"), "evidence": re.findall(r"E-\d+", result)}


def build_graph(llm: Any, ledger: EvidenceLedger, events: EventLog) -> Any:
    specs = REGISTRY.openai_specs()

    def overview(state: InvestigationState) -> dict[str, Any]:
        result = REGISTRY.call("list_services", {}, ledger)
        events.emit("tool_result", {"name": "list_services", "result": result})
        messages = [dict(m) for m in state["messages"]]
        messages[1]["content"] += f"\n\nService overview (already fetched with list_services):\n{result}"
        return {"messages": messages, "made": state["made"] + [_record("list_services", {}, result)]}

    def reason(state: InvestigationState) -> dict[str, Any]:
        step = state["step"]
        last_step = step == MAX_ITERATIONS - 1
        messages = list(state["messages"])
        if last_step:
            messages.append({"role": "user", "content": FINAL_REMINDER})
        response = llm.chat(messages, tools=None if last_step else specs)
        events.emit("agent_step", {"step": step, "content": response.content, "tool_calls": response.tool_calls})
        update: dict[str, Any] = {"step": step + 1, "pending": []}
        if response.tool_calls:
            messages.append(_assistant_message(response.content, response.tool_calls))
            update.update(messages=messages, pending=response.tool_calls)
            return update
        diagnosis = _parse_diagnosis(response.content)
        if diagnosis is None:
            messages += [{"role": "assistant", "content": response.content}, {"role": "user", "content": FINAL_REMINDER}]
        update.update(messages=messages, diagnosis=diagnosis)
        return update

    def act(state: InvestigationState) -> dict[str, Any]:
        messages = list(state["messages"])
        made = list(state["made"])
        for call in state["pending"]:
            events.emit("tool_call", {"name": call["name"], "args": call["arguments"]})
            result = REGISTRY.call(call["name"], call["arguments"], ledger)
            events.emit("tool_result", {"name": call["name"], "result": result})
            made.append(_record(call["name"], call["arguments"], result))
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
        return {"messages": messages, "made": made, "pending": []}

    def finalize(state: InvestigationState) -> dict[str, Any]:
        diagnosis = state["diagnosis"]
        if diagnosis is None:
            diagnosis = Diagnosis(summary="Agent did not produce a valid diagnosis", next_steps=["Escalate to a human"])
            events.emit("error", {"reason": "no valid diagnosis"})
        final = ledger.enforce(diagnosis)
        events.emit("diagnosis", final.to_dict())
        return {"diagnosis": final}

    def after_reason(state: InvestigationState) -> str:
        if state["pending"]:
            return "act"
        if state["diagnosis"] is not None or state["step"] >= MAX_ITERATIONS:
            return "finalize"
        return "reason"

    def after_act(state: InvestigationState) -> str:
        return "finalize" if state["step"] >= MAX_ITERATIONS else "reason"

    graph = StateGraph(InvestigationState)
    graph.add_node("overview", overview)
    graph.add_node("reason", reason)
    graph.add_node("act", act)
    graph.add_node("finalize", finalize)
    graph.set_entry_point("overview")
    graph.add_edge("overview", "reason")
    graph.add_conditional_edges("reason", after_reason, {"act": "act", "finalize": "finalize", "reason": "reason"})
    graph.add_conditional_edges("act", after_act, {"reason": "reason", "finalize": "finalize"})
    graph.add_edge("finalize", END)
    return graph.compile()


def investigate(symptom: str, llm: Any, ledger: EvidenceLedger, events: EventLog) -> tuple[Diagnosis, list[dict[str, Any]]]:
    """LangGraph investigation: overview -> reason <-> act -> finalize. Returns the enforced Diagnosis and tool calls made."""
    load_all()
    initial: InvestigationState = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Incident report: {symptom}"},
        ],
        "made": [],
        "pending": [],
        "diagnosis": None,
        "step": 0,
    }
    state = build_graph(llm, ledger, events).invoke(initial, {"recursion_limit": 3 * MAX_ITERATIONS + 10})
    return state["diagnosis"], state["made"]


def mermaid() -> str:
    from oncall.llm import FakeLLM

    return build_graph(FakeLLM([]), EvidenceLedger(), EventLog("graph", ".")).get_graph().draw_mermaid()
