"""Compute the confidence the report states, and decide whether to escalate to a human.

The model's own number is only an upper bound: it is clamped to 0..1, then lowered by caps, never raised.
Every cap that lowers it is written down in plain words. Separately, some findings force escalation
whatever the number is (an invented quote, no usable evidence, a run that failed). A run that ran out of
budget forces escalation only when it has no validated evidence of at least two kinds to show for it.
The kinds are those of the ledger entries the items cite, never the labels the model chose.
"""
from dataclasses import dataclass, field

from oncall import schema as S
from oncall.validator import derived_kind

CONFIDENCE_THRESHOLD = 0.7  # below this the report escalates to a human instead of asserting a cause
CAP_SINGLE_KIND = 0.6  # validated evidence of fewer than two different kinds
CAP_NO_ALTERNATIVES = 0.75  # the model did not say which other explanations it ruled out
MIN_DISTINCT_KINDS = 2


@dataclass
class Assessment:
    confidence: float
    reasons: list[str] = field(default_factory=list)  # every cap or clamp that changed the number
    escalation_reasons: list[str] = field(default_factory=list)

    @property
    def escalate(self) -> bool:
        return bool(self.escalation_reasons)


def kind_mismatch(item: dict) -> str | None:
    """A sentence when the model's kind label for a validated item differs from its ledger entry's kind."""
    derived = derived_kind(item[S.EV_LEDGER_ID])
    label = str(item[S.EV_KIND]).strip().lower()
    label = "container" if label == "deploy" else label
    if derived is None or label == derived:
        return None
    return f"evidence {item[S.EV_LEDGER_ID]} labelled kind {item[S.EV_KIND]} but cites a {derived} entry"


def _clamp(stated) -> tuple[float, str | None]:
    if isinstance(stated, bool) or not isinstance(stated, (int, float)) or stated != stated:
        return 0.0, f"stated confidence {stated!r} is not a number, so it was treated as 0.00"
    if stated < 0:
        return 0.0, f"stated confidence {stated:.2f} was below 0 and was raised to 0.00"
    if stated > 1:
        return 1.0, f"stated confidence {stated:.2f} was above 1 and was lowered to 1.00"
    return float(stated), None


def assess(candidate: dict, evidence_items: list[dict], run_info: dict | None = None) -> Assessment:
    """`evidence_items` are the validated/rejected dicts from validator.validate_evidence."""
    run_info = run_info or {}
    confidence, clamp_note = _clamp(candidate.get(S.STATED_CONFIDENCE))
    reasons = [clamp_note] if clamp_note else []
    escalation = []

    validated = [i for i in evidence_items if i[S.EV_VALIDATED]]
    rejected = [i for i in evidence_items if not i[S.EV_VALIDATED]]
    component = candidate.get(S.COMPONENT)
    component_unknown = not isinstance(component, str) or component.strip().lower() in ("", S.UNKNOWN_COMPONENT)

    # --- escalation rules -------------------------------------------------------------------
    if rejected:
        ids = ", ".join(str(i[S.EV_LEDGER_ID]) for i in rejected)
        escalation.append(f"{len(rejected)} of {len(evidence_items)} evidence items failed validation ({ids})")
    if component_unknown:
        escalation.append("the agent could not name a component")
    if not validated:
        escalation.append("no evidence item could be validated against the ledger")

    kinds = {derived_kind(i[S.EV_LEDGER_ID]) or "other" for i in validated}
    reasons += [note for note in map(kind_mismatch, validated) if note]

    if run_info.get(S.RUN_BUDGET_EXHAUSTED):
        if validated and len(kinds) >= MIN_DISTINCT_KINDS and not run_info.get(S.RUN_LLM_ERROR):
            reasons.append("step budget was reached")
        else:
            escalation.append(f"the investigation ran out of budget (stop reason: {run_info.get(S.RUN_STOP_REASON)})")
    if run_info.get(S.RUN_LLM_ERROR):
        escalation.append(f"the run reported an error: {run_info[S.RUN_LLM_ERROR]}")

    # --- caps (only written down when they actually lower the number) --------------------------
    binding = []  # short phrases for the escalation reason
    if len(kinds) < MIN_DISTINCT_KINDS and CAP_SINGLE_KIND < confidence:
        reasons.append(f"capped at {CAP_SINGLE_KIND:.2f}: validated evidence has {len(kinds)} kind(s), "
                       f"at least {MIN_DISTINCT_KINDS} different kinds are needed for more")
        binding.append(f"{'only one kind of' if kinds else 'no validated'} evidence (capped at {CAP_SINGLE_KIND:.2f})")
        confidence = CAP_SINGLE_KIND
    if not candidate.get(S.ALTERNATIVES) and CAP_NO_ALTERNATIVES < confidence:
        reasons.append(f"capped at {CAP_NO_ALTERNATIVES:.2f}: no alternative explanation was considered")
        binding.append(f"no alternative explanation considered (capped at {CAP_NO_ALTERNATIVES:.2f})")
        confidence = CAP_NO_ALTERNATIVES

    if confidence < CONFIDENCE_THRESHOLD:
        if binding:
            escalation.append(f"{' and '.join(binding)}, below the {CONFIDENCE_THRESHOLD:.2f} threshold")
        else:
            escalation.append(f"confidence {confidence:.2f} is below the threshold {CONFIDENCE_THRESHOLD:.2f}")

    return Assessment(confidence=confidence, reasons=reasons, escalation_reasons=escalation)
