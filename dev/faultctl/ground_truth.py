"""Append-only log of every inject and reset, in tests/ground_truth.md.

It is read only after a run, to mark the agent right or wrong. The agent never reads it.
"""
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "tests" / "ground_truth.md"
COLUMNS = ["time", "action", "incident", "mechanism", "target", "variant", "outcome", "note"]

HEADER = (
    "# Ground truth\n\n"
    "Written by `dev/faultctl`, append-only: one row per inject or reset, including dry-runs,\n"
    "refusals and failures. `time` is when the operation started. Operator-only: the agent\n"
    "must never read this file.\n\n"
    "| " + " | ".join(COLUMNS) + " |\n"
    "|" + "---|" * len(COLUMNS) + "\n"
)


def _cell(value: str) -> str:
    # Keep each entry on one table row.
    return str(value).replace("|", "/").replace("\n", " ").strip() or "-"


class GroundTruthLog:
    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = Path(path)

    def append(self, when: str, action: str, incident: str, mechanism: str,
               target: str, variant: str, outcome: str, note: str = "") -> None:
        """Add one row, creating the file with its header first if it is missing."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        row = "| " + " | ".join(_cell(v) for v in
                                [when, action, incident, mechanism, target, variant, outcome, note]) + " |\n"
        with open(self.path, "a+", encoding="utf-8") as f:
            f.seek(0, 2)
            if f.tell() == 0:
                f.write(HEADER)
            f.write(row)
