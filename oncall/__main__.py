from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import typer

from oncall.contracts import Alert
from oncall.events import EventLog
from oncall.ledger import EvidenceLedger

app = typer.Typer()


@app.command()
def tools() -> None:
    from oncall.tools import REGISTRY, load_all

    load_all()
    typer.echo(f"{len(REGISTRY.openai_specs())} tools")


@app.command()
def investigate(
    service: str = typer.Option(..., "--service"),
    kind: str = typer.Option("error_rate", "--kind"),
) -> None:
    from oncall.agent.run import investigate as run_investigation

    try:
        alert_kind = kind if kind in {"error_rate", "latency", "container", "traffic", "memory", "manual"} else "manual"
        alert = Alert(
            alert_id=str(uuid4()),
            fired_at=datetime.now(timezone.utc).isoformat(),
            kind=alert_kind,
            service=service,
            description=f"Manual investigation for {service}",
        )
        result = asyncio.run(run_investigation(alert, EvidenceLedger(), EventLog(alert.alert_id)))
        typer.echo(result.model_dump_json() if hasattr(result, "model_dump_json") else _json(result))
    except (ImportError, ModuleNotFoundError) as exc:
        typer.echo(f"Investigation stub unavailable: {exc}")


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


def _json(value: object) -> str:
    import json

    return json.dumps(value, default=str)


if __name__ == "__main__":
    app()
