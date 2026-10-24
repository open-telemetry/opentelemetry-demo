"""Check every evidence item of a candidate diagnosis against the evidence ledger.

An item is valid only when the model's own words can be found in what the tools returned:
  1. its ledger_id exists;
  2. its quote is an EXACT substring of a string value inside that entry's result
     (trace IDs, log messages and container names compare exactly, with no trimming or case change);
  3. for kind "metric" the quote may instead be a number within METRIC_REL_TOL (2 %) or
     METRIC_ABS_TOL (0.05) of a numeric value in that entry. Metric entries also carry text such as
     "errors 0.00% -> 3.38%"; a quote that is an exact substring of that text is valid by rule 2;
  4. if a value is given it must also occur in the same entry (exact text, or an equal number).
A separate soft check only warns when no valid item's entry mentions the claimed component.

Only what the tool observed is searched (the entry's result without its query strings), so a model
cannot "prove" a claim by quoting the command that was run.

The ledger is the dict stored in ledger.json: a list of entries {id, tool, arguments, query, window,
timestamp, result}. `Ledger` has no load method, so `load_ledger` reads that file directly.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

from oncall import schema as S

METRIC_REL_TOL = 0.02
METRIC_ABS_TOL = 0.05
MIN_QUOTE_CHARS = 3  # a text quote shorter than this would match almost anything


@dataclass
class ValidationResult:
    items: list[dict] = field(default_factory=list)  # one dict per evidence item, in order
    warnings: list[str] = field(default_factory=list)

    @property
    def validated(self) -> list[dict]:
        return [i for i in self.items if i[S.EV_VALIDATED]]

    @property
    def rejected(self) -> list[dict]:
        return [i for i in self.items if not i[S.EV_VALIDATED]]


# --- ledger access -----------------------------------------------------------------------------

def load_ledger(source) -> dict[str, dict]:
    """Return {id: entry dict}. `source` is a path to ledger.json, a list of entries, a dict keyed by id,
    or a `tools.ledger.Ledger`. Entries may be dicts or objects with `.id` and `.result`."""
    if isinstance(source, (str, Path)):
        source = json.loads(Path(source).read_text(encoding="utf-8"))
    if hasattr(source, "list") and callable(source.list):
        source = source.list()
    if isinstance(source, dict):
        entries = [(key, value) for key, value in source.items()]
    else:
        entries = [(None, entry) for entry in source]
    loaded = {}
    for key, entry in entries:
        if isinstance(entry, dict):
            plain = entry
        else:
            plain = {"id": getattr(entry, "id", key), "tool": getattr(entry, "tool", None),
                     "result": getattr(entry, "result", None)}
        entry_id = plain.get("id", key)
        if entry_id is not None:
            loaded[str(entry_id)] = plain
    return loaded


def _leaves(node):
    """Yield every string and every number (not bool) inside a nested structure."""
    if isinstance(node, dict):
        for value in node.values():
            yield from _leaves(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _leaves(value)
    elif isinstance(node, str):
        yield node
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        yield node


def _observed(entry: dict):
    """What the tool observed: the entry's result without its copy of the query that was run."""
    result = entry.get("result")
    if isinstance(result, dict):
        return {key: value for key, value in result.items() if key != "query"}
    return result


def _split(observed) -> tuple[list[str], list[float]]:
    texts, numbers = [], []
    for leaf in _leaves(observed):
        (texts if isinstance(leaf, str) else numbers).append(leaf)
    return texts, numbers


def _as_number(text: str):
    """Parse '3.38', '3.38%' or ' 12 ' as a number; None when the text is not a plain number."""
    cleaned = text.strip().rstrip("%").strip()
    try:
        number = float(cleaned)
    except ValueError:
        return None
    return number if number == number and number not in (float("inf"), float("-inf")) else None


def _within_tolerance(quoted: float, actual: float) -> bool:
    return abs(quoted - actual) <= max(METRIC_REL_TOL * abs(actual), METRIC_ABS_TOL)


# --- one item ----------------------------------------------------------------------------------

def _check_item(item: dict, ledger: dict[str, dict]) -> tuple[bool, str]:
    ledger_id = item.get(S.EV_LEDGER_ID)
    quote = item.get(S.EV_QUOTE)
    value = item.get(S.EV_VALUE)
    kind = item.get(S.EV_KIND)

    entry = ledger.get(ledger_id) if isinstance(ledger_id, str) else None
    if entry is None:
        return False, f"ledger id {ledger_id!r} does not exist"
    if not isinstance(quote, str) or not quote.strip():
        return False, f"{ledger_id}: the quote is empty"

    texts, numbers = _split(_observed(entry))

    found = False
    note = ""
    if len(quote) >= MIN_QUOTE_CHARS and any(quote in text for text in texts):
        found, note = True, f"quote found verbatim in {ledger_id}"
    elif kind == "metric":
        quoted = _as_number(quote)
        if quoted is None:
            return False, f"{ledger_id}: metric quote {quote!r} is not a number and not found in the entry text"
        close = [n for n in numbers if _within_tolerance(quoted, n)]
        if close:
            found, note = True, f"metric quote {quote} matches {close[0]} in {ledger_id} (within tolerance)"
        else:
            return False, f"{ledger_id}: no number within 2% or 0.05 of {quote}"
    if not found:
        reason = "too short to check" if len(quote) < MIN_QUOTE_CHARS else "not found in the entry"
        return False, f"{ledger_id}: quote {quote!r} {reason}"

    if value:  # None and "" both mean "no value given"
        if not isinstance(value, str):
            return False, f"{ledger_id}: value must be text"
        number = _as_number(value)
        in_text = any(value in text for text in texts)
        in_numbers = number is not None and any(number == n for n in numbers)
        if not (in_text or in_numbers):
            return False, f"{ledger_id}: value {value!r} not found in the entry"
        note += f"; value {value!r} found"
    return True, note


def _mentions(entry: dict, component: str) -> bool:
    return component.lower() in json.dumps(_observed(entry), default=str).lower()


# --- whole candidate ---------------------------------------------------------------------------

def validate_evidence(candidate: dict, ledger_source) -> ValidationResult:
    """Validate every evidence item. Returns the items (each with validated and validation_note) and warnings."""
    ledger = load_ledger(ledger_source)
    raw = candidate.get(S.EVIDENCE)
    evidence = [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []

    result = ValidationResult()
    for item in evidence:
        ok, note = _check_item(item, ledger)
        result.items.append({
            S.EV_LEDGER_ID: item.get(S.EV_LEDGER_ID),
            S.EV_KIND: item.get(S.EV_KIND),
            S.EV_CLAIM: item.get(S.EV_CLAIM),
            S.EV_QUOTE: item.get(S.EV_QUOTE),
            S.EV_VALUE: item.get(S.EV_VALUE),
            S.EV_VALIDATED: ok,
            S.EV_NOTE: note,
        })

    component = candidate.get(S.COMPONENT)
    if isinstance(component, str) and component.strip() and component.strip().lower() != S.UNKNOWN_COMPONENT:
        checked = [ledger[i[S.EV_LEDGER_ID]] for i in result.validated]
        if checked and not any(_mentions(entry, component.strip()) for entry in checked):
            result.warnings.append(f"none of the validated evidence mentions the component {component.strip()!r}")
    return result
