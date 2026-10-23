"""The one result shape every tool returns.

state is deliberately three-valued so a failure can never be mistaken for "all healthy":
  data          = the backend answered and there are items
  no_data       = the backend answered but had nothing for this query/window
  backend_error = the backend could not be asked or gave a bad answer (see `error`)
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

STATES = ("data", "no_data", "backend_error")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def window_dict(minutes: int, end: datetime) -> dict:
    """The time window a query covered: [end - minutes, end]."""
    return {"minutes": minutes, "start": iso(end - timedelta(minutes=minutes)), "end": iso(end)}


@dataclass
class ToolResult:
    tool: str
    state: str
    query: list[str]  # the exact queries / commands that were run
    window: dict
    items: list = field(default_factory=list)  # already capped by the tool
    total_items: int = 0  # how many existed before the cap
    extra: dict = field(default_factory=dict)  # secondary sections, e.g. kafka lag
    notes: list[str] = field(default_factory=list)  # limitations seen on this call
    error: str | None = None

    def __post_init__(self):
        if self.state not in STATES:
            raise ValueError(f"state must be one of {STATES}, got {self.state!r}")
        if self.state == "data" and not self.items:
            raise ValueError("state 'data' needs items; use 'no_data' for an empty answer")
        if self.state == "backend_error" and not self.error:
            raise ValueError("state 'backend_error' needs an error message")

    def to_dict(self) -> dict:
        return asdict(self)


def backend_error(tool: str, query: list[str], window: dict, error: str) -> ToolResult:
    return ToolResult(tool=tool, state="backend_error", query=query, window=window, error=error)
