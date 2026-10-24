"""Evidence checker: every evidence item the LLM cites must exist in the data the tools returned.

"Evidence must exist in the data; invented evidence is penalised" -> we check it ourselves first:
  * a quoted `reference` (trace ID, log line, metric value) must appear in a tool result, or
  * every trace ID in the signal must appear, and most of its numbers must appear.
Unverified items are flagged (verified=false), dropped from the official output, and cost confidence.
"""
import re

HEX_ID = re.compile(r"\b[0-9a-f]{16,32}\b")
NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace('\\"', '"')).strip().lower()


def _num_seen(n: str, corpus: str) -> bool:
    if n in corpus:
        return True
    try:
        x = float(n)
    except ValueError:
        return False
    # "45%" in prose vs 0.45 in data, "1200ms" vs 1200.0
    variants = {f"{x / 100:.4f}".rstrip("0").rstrip("."), f"{x / 100:.2f}", f"{x / 100:.3f}", f"{x:.1f}",
                str(int(x)) if x.is_integer() else n}
    return any(v and v in corpus for v in variants)


def check_item(e: dict, corpus: str) -> bool:
    c = _norm(corpus)
    ref = _norm(e.get("reference") or "")
    if ref and len(ref) >= 4:
        if ref in c or ref[:60] in c:
            return True
        ref_ids = HEX_ID.findall(ref)
        if ref_ids and all(i in c for i in ref_ids):
            return True
    sig = _norm(e.get("signal") or "")
    ids = HEX_ID.findall(sig)
    if ids and not all(i in c for i in ids):
        return False
    nums = [n for n in NUM.findall(sig) if n not in ("0", "1", "2", "5", "95", "30")]  # skip trivial/window nums
    if nums:
        seen = sum(_num_seen(n, c) for n in nums)
        return seen >= max(1, (len(nums) + 1) // 2)
    if ids:
        return True
    # no numbers and no ids: accept only if a distinctive chunk of the signal is in the data
    words = [w for w in re.findall(r"[a-z][a-z0-9_.:/-]{5,}", sig)]
    return sum(w in c for w in words) >= max(1, len(words) // 2)


def check(diag: dict, corpus: str) -> dict:
    n_bad = 0
    for e in diag.get("evidence", []):
        e["verified"] = check_item(e, corpus)
        n_bad += not e["verified"]
    n_ok = len(diag.get("evidence", [])) - n_bad
    return {"verified": n_ok, "unverified": n_bad}
