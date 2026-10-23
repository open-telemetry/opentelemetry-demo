from __future__ import annotations

import json

import typer

from oncall.events import EventLog
from oncall.ledger import EvidenceLedger
from oncall.llm import FakeLLM, LLMClient

app = typer.Typer()


def _make_llm(kind: str, script: list | None = None):
    if kind == "fake":
        return FakeLLM(script or ["fake summary"])
    return LLMClient()


@app.command()
def tools() -> None:
    from oncall.tools import REGISTRY, load_all

    load_all()
    typer.echo(f"{len(REGISTRY.openai_specs())} tools")


@app.command()
def investigate(
    symptom: str = typer.Argument(..., help="e.g. 'checkout is failing'"),
    llm: str = typer.Option("real", "--llm", help="real or fake"),
) -> None:
    from oncall.agent.run import investigate as run_investigation
    from oncall.agent.run import new_run_id
    from oncall.config import settings
    from oncall.schema import to_submission

    calls = [
        {"id": "1", "name": "list_services", "arguments": {}},
        {"id": "2", "name": "get_error_rates", "arguments": {"window_minutes": 5}},
    ]
    final = json.dumps({
        "root_cause_service": "unknown", "fault_class": "unknown", "confidence": 0.2, "summary": "fake run",
        "evidence_ids": ["E-002", "E-099"], "escalate": True, "next_steps": [],
    })
    events = EventLog(new_run_id(), settings.RUNS_DIR)
    diagnosis, made = run_investigation(symptom, _make_llm(llm, [{"tool_calls": calls}, final]), EvidenceLedger(), events)
    typer.echo(json.dumps(to_submission(diagnosis), indent=2))
    typer.echo("\n#  tool                 args                                   ok  evidence")
    for number, call in enumerate(made, 1):
        typer.echo(f"{number:<2} {call['tool']:<20} {json.dumps(call['args']):<38} {'y' if call['ok'] else 'n':<3} {','.join(call['evidence'])}")
    typer.echo(f"\nevents: {events.path}")


@app.command()
def summarise(llm: str = typer.Option("real", "--llm", help="real or fake")) -> None:
    from oncall.agent.summarise import summarise as run_summary

    typer.echo(run_summary(_make_llm(llm), EvidenceLedger()))


@app.command()
def detect() -> None:
    typer.echo("Detector is not available yet; no investigation started.")


@app.command()
def serve() -> None:
    try:
        import uvicorn
        from oncall.service import app as service_app
    except (ImportError, ModuleNotFoundError) as exc:
        typer.echo(f"Service stub unavailable: {exc}")
        return
    uvicorn.run(service_app, host="0.0.0.0", port=8099)


if __name__ == "__main__":
    app()
