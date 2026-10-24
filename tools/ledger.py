"""In-memory evidence ledger: every tool result the agent sees is stored here with an ID.

The agent cites these IDs (M1, C2, ...) and the validator later checks each citation
against what is stored. Results are sanitised on the way in, so the ledger never holds
flag data even if a tool forgot to filter.
"""
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from tools import sanitize
from tools.result import ToolResult, iso, utc_now

# One letter per tool. Unknown tools get "X" so they still get a unique ID.
PREFIXES = {
    "query_metrics": "M",
    "container_health": "C",
    "query_traces": "T",
    "query_logs": "L",
    "deploy_history": "D",
}


@dataclass
class LedgerEntry:
    id: str
    tool: str
    arguments: dict
    query: list[str]
    window: dict
    timestamp: str  # when the tool ran
    result: dict  # the sanitised ToolResult, as plain JSON


class Ledger:
    def __init__(self):
        self._entries: dict[str, LedgerEntry] = {}
        self._counters: dict[str, int] = {}

    def add(self, tool: str, arguments: dict, result: ToolResult) -> LedgerEntry:
        """Sanitise a tool result, give it the next ID for its tool, and store it."""
        cleaned = sanitize.clean_result(result)
        prefix = PREFIXES.get(tool, "X")
        self._counters[prefix] = self._counters.get(prefix, 0) + 1
        entry = LedgerEntry(
            id=f"{prefix}{self._counters[prefix]}",
            tool=tool,
            arguments=sanitize.clean(dict(arguments)),
            query=cleaned.query,
            window=cleaned.window,
            timestamp=iso(utc_now()),
            result=cleaned.to_dict(),
        )
        self._entries[entry.id] = entry
        return entry

    def get(self, entry_id: str) -> LedgerEntry | None:
        return self._entries.get(entry_id)

    def list(self) -> list[LedgerEntry]:
        return list(self._entries.values())

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([asdict(e) for e in self.list()], indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        return path
