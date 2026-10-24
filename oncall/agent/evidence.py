"""Evidence validator (F13): a Diagnosis may only cite evidence the run log holds."""

import re

from oncall.agent.runlog import RunLog
from oncall.models import Diagnosis, Evidence

MAX_REASONING_CHARS = 800
THIN_EVIDENCE_FACTOR = 0.6
NUMBER_TOLERANCE = 0.05
# An evidence id cited in reasoning: "[metric:error_rate:cart@2026-...]".
CITED_ID = re.compile(r"\[([a-z]+:[^\]]+)\]")
# Sentence boundary: ".", "!" or "?" followed by whitespace (not "0.31").
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
# A number such as 0.31, 3521 or 12.5 (a trailing "%" is read separately).
NUMBER = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(%?)")


def tool_of(evidence_id: str) -> str:
    """'metric:error_rate:cart@ts' -> 'metric' (one tool per id prefix)."""
    return evidence_id.split(":", 1)[0]


def service_of(evidence: Evidence) -> str | None:
    """The service an evidence item is about, from its id or (traces) its text."""
    eid, text = evidence["id"], evidence.get("text") or ""
    kind, _, rest = eid.partition(":")
    if kind == "metric":
        key = rest.split(":", 1)[1] if ":" in rest else rest
        return key.split("@", 1)[0].split("/", 1)[0]
    if kind in ("container", "deploy"):
        return rest.split("@", 1)[0]
    if kind == "log":
        return rest.split(":", 1)[0]
    if kind == "trace":
        return text.split(" ", 1)[0] or None
    return None


def salvage(evidence_id: str, index: dict[str, Evidence]) -> str | None:
    """The real id behind a malformed one, or None.

    A model sometimes glues the evidence text onto the id
    ("container:cart: cart: state=..."). Only salvage when exactly one known id
    is a strict prefix of it.
    """
    if evidence_id in index:
        return evidence_id
    matches = [
        k for k in index if evidence_id.startswith(k) and len(k) < len(evidence_id)
    ]
    return matches[0] if len(matches) == 1 else None


def _numbers(text: str) -> list[float]:
    values = []
    for value, percent in NUMBER.findall(text):
        number = float(value)
        values.append(number / 100 if percent else number)
    return values


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= NUMBER_TOLERANCE * max(abs(a), abs(b), 1e-9)


def _check_numbers(
    sentence: str, ids: list[str], index: dict[str, Evidence]
) -> str | None:
    """A problem if the sentence quotes metric numbers none of its cited metrics hold."""
    metric_ids = [i for i in ids if tool_of(i) == "metric"]
    if not metric_ids:
        return None
    claimed = _numbers(CITED_ID.sub("", sentence))
    if not claimed:
        return None
    recorded = [n for i in metric_ids for n in _numbers(index[i].get("text") or "")]
    if any(_close(c, r) for c in claimed for r in recorded):
        return None
    return f"numbers {claimed} in reasoning do not match {', '.join(metric_ids)}"


def _clean_reasoning(
    reasoning: str, index: dict[str, Evidence], problems: list[str]
) -> str:
    kept = []
    for sentence in (s for s in SENTENCE_END.split(reasoning) if s.strip()):
        cited = CITED_ID.findall(sentence)
        fixed = {c: salvage(c, index) for c in cited}
        unknown = [c for c, real in fixed.items() if real is None]
        if unknown:
            problems.append(f"removed reasoning sentence citing unknown ids {unknown}")
            continue
        for cited_id, real in fixed.items():
            if real != cited_id:
                sentence = sentence.replace(f"[{cited_id}]", f"[{real}]")
        problem = _check_numbers(sentence, list(fixed.values()), index)
        if problem:
            problems.append(problem)
        kept.append(sentence.strip())
    return " ".join(kept)[:MAX_REASONING_CHARS]


def validate(d: Diagnosis, run: RunLog) -> tuple[Diagnosis, list[str]]:
    """Return a cleaned copy of `d` and the problems found (F13 rules)."""
    index = run.evidence_index()
    problems: list[str] = []
    out: Diagnosis = {**d, "alternatives": list(d["alternatives"])}

    ids: list[str] = []
    for cited in d["evidence_ids"]:
        real = salvage(cited, index)
        if real is None:
            problems.append(f"dropped evidence id not in run log: {cited[:120]}")
        elif real != cited:
            problems.append(
                f"repaired malformed evidence id: {cited[:60]}... -> {real}"
            )
        if real is not None and real not in ids:
            ids.append(real)
    out["evidence_ids"] = ids
    out["reasoning"] = _clean_reasoning(d["reasoning"], index, problems)

    if not ids:
        problems.append("no valid evidence: escalate with category unknown")
        out.update(component=None, category="unknown", decision="escalate")
        out["confidence"] = min(out["confidence"], 0.3)
        return out, problems

    if out["component"]:
        own = [i for i in ids if service_of(index[i]) == out["component"]]
        tools = {tool_of(i) for i in own}
        if len(own) < 2 or len(tools) < 2:
            out["confidence"] = round(out["confidence"] * THIN_EVIDENCE_FACTOR, 3)
            problems.append(
                f"thin evidence for {out['component']}: {len(own)} items from "
                f"{len(tools)} tool(s); confidence x{THIN_EVIDENCE_FACTOR}"
            )
    return out, problems
