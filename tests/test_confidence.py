"""Confidence caps, escalation rules and the reasons list (offline, no ledger needed)."""
import pytest

from oncall import confidence as C
from oncall import schema as S

ALT = [{"hypothesis": "h", "why_rejected": "w"}]


def ev(kind="container", ok=True, ledger_id="C1"):
    return {S.EV_LEDGER_ID: ledger_id, S.EV_KIND: kind, S.EV_VALIDATED: ok, S.EV_NOTE: "n"}


def cand(stated=0.9, component="cart", alternatives=ALT):
    return {S.COMPONENT: component, S.STATED_CONFIDENCE: stated, S.ALTERNATIVES: alternatives}


TWO_KINDS = [ev("container"), ev("log", ledger_id="L1")]


def test_clean_case_keeps_stated_confidence_and_does_not_escalate():
    a = C.assess(cand(0.9), TWO_KINDS)
    assert a.confidence == 0.9 and a.reasons == [] and not a.escalate


def test_threshold_constant_starts_at_0_7():
    assert C.CONFIDENCE_THRESHOLD == 0.7


def test_confidence_exactly_at_threshold_is_not_escalated():
    a = C.assess(cand(0.7), TWO_KINDS)
    assert a.confidence == 0.7 and not a.escalate


def test_below_threshold_escalates_with_reason():
    a = C.assess(cand(0.65), TWO_KINDS)
    assert a.escalate and any("below the threshold" in r for r in a.escalation_reasons)
    assert a.confidence == 0.65


def test_single_kind_caps_at_0_6_and_escalates():
    a = C.assess(cand(0.95), [ev("container"), ev("container", ledger_id="C2")])
    assert a.confidence == C.CAP_SINGLE_KIND == 0.6
    assert any("capped at 0.60" in r for r in a.reasons)
    assert a.escalate


def test_cap_not_written_down_when_it_does_not_lower_the_number():
    a = C.assess(cand(0.5), [ev("container")])
    assert a.confidence == 0.5 and a.reasons == []


def test_no_alternatives_caps_at_0_75_without_escalating():
    a = C.assess(cand(0.95, alternatives=[]), TWO_KINDS)
    assert a.confidence == 0.75 and not a.escalate
    assert any("no alternative" in r for r in a.reasons)


def test_missing_alternatives_key_counts_as_none():
    c = cand(0.95)
    del c[S.ALTERNATIVES]
    assert C.assess(c, TWO_KINDS).confidence == 0.75


def test_the_lower_cap_wins_and_only_binding_caps_are_listed():
    a = C.assess(cand(0.95, alternatives=[]), [ev("container")])
    assert a.confidence == 0.6
    assert len(a.reasons) == 1  # the 0.75 cap no longer lowers 0.6, so only the first is written down


def test_rejected_item_escalates_and_names_the_ids():
    a = C.assess(cand(0.9), TWO_KINDS + [ev("log", ok=False, ledger_id="L9")])
    assert a.escalate and any("L9" in r for r in a.escalation_reasons)


def test_unknown_component_escalates_in_any_case():
    for name in ("unknown", "UNKNOWN", " unknown ", "", None):
        a = C.assess(cand(0.9, component=name), TWO_KINDS)
        assert a.escalate, name


def test_zero_validated_items_escalates():
    a = C.assess(cand(0.9), [])
    assert a.escalate and any("no evidence item could be validated" in r for r in a.escalation_reasons)
    a = C.assess(cand(0.9), [ev(ok=False)])
    assert any("no evidence item could be validated" in r for r in a.escalation_reasons)


BUDGET = {S.RUN_BUDGET_EXHAUSTED: True, S.RUN_STOP_REASON: "step_budget"}


def test_budget_exhausted_with_two_kinds_of_validated_evidence_does_not_escalate():
    a = C.assess(cand(0.9), TWO_KINDS, BUDGET)
    assert not a.escalate and a.confidence == 0.9
    assert "step budget was reached" in a.reasons


def test_budget_exhausted_without_validated_evidence_escalates():
    a = C.assess(cand(0.9), [ev(ok=False)], BUDGET)
    assert any("ran out of budget" in r and "step_budget" in r for r in a.escalation_reasons)
    assert "step budget was reached" not in a.reasons


def test_budget_exhausted_with_one_kind_escalates():
    a = C.assess(cand(0.9), [ev("container"), ev("container", ledger_id="C2")], BUDGET)
    assert any("ran out of budget" in r for r in a.escalation_reasons)


def test_budget_exhausted_with_an_llm_error_still_escalates():
    a = C.assess(cand(0.9), TWO_KINDS, dict(BUDGET, **{S.RUN_LLM_ERROR: "timeout"}))
    assert any("ran out of budget" in r for r in a.escalation_reasons)


def test_budget_exhausted_still_applies_the_normal_confidence_rules():
    a = C.assess(cand(0.5), TWO_KINDS, BUDGET)
    assert a.escalate and not any("ran out of budget" in r for r in a.escalation_reasons)


# --- kinds come from the ledger entry, not from the model's label ------------------------------

def test_two_items_citing_the_same_entry_with_different_labels_are_one_kind():
    a = C.assess(cand(0.95), [ev("a", ledger_id="C1"), ev("b", ledger_id="C1")])
    assert a.confidence == C.CAP_SINGLE_KIND and a.escalate


def test_label_is_ignored_and_the_kind_is_derived_from_the_ledger_id():
    a = C.assess(cand(0.95), [ev("trace", ledger_id="M1"), ev("log", ledger_id="L1")])
    assert a.confidence == 0.95 and not a.escalate  # metric + log, whatever the labels say
    mismatch = [r for r in a.reasons if "labelled kind trace but cites a metric entry" in r]
    assert mismatch == ["evidence M1 labelled kind trace but cites a metric entry"]


def test_kind_derived_from_prefix_for_every_tool():
    assert {C.derived_kind(i) for i in ("M1", "C1", "T1", "L1", "D1")} == {"metric", "container", "trace", "log"}


def test_container_and_deploy_entries_count_as_one_kind():
    a = C.assess(cand(0.95), [ev("container", ledger_id="C1"), ev("container", ledger_id="D1")])
    assert a.confidence == C.CAP_SINGLE_KIND and a.escalate


def test_matching_labels_add_no_mismatch_line():
    assert C.assess(cand(0.9), TWO_KINDS).reasons == []
    assert C.assess(cand(0.9), [ev("container", ledger_id="D1"), ev("log", ledger_id="L1")]).reasons == []


def test_rejected_items_do_not_count_towards_kinds():
    a = C.assess(cand(0.95), [ev("container"), ev("log", ok=False, ledger_id="L1")])
    assert a.confidence == C.CAP_SINGLE_KIND


# --- escalation reason names the cap that contributed ------------------------------------------

def test_single_kind_escalation_reason_names_the_cap():
    a = C.assess(cand(0.95), [ev("container")])
    assert "only one kind of evidence (capped at 0.60), below the 0.70 threshold" in a.escalation_reasons


def test_no_alternatives_cap_is_named_when_it_pushes_below_the_threshold(monkeypatch):
    monkeypatch.setattr(C, "CAP_NO_ALTERNATIVES", 0.65)
    a = C.assess(cand(0.95, alternatives=[]), TWO_KINDS)
    assert any("no alternative explanation considered (capped at 0.65)" in r and "below the 0.70 threshold" in r
               for r in a.escalation_reasons)


def test_plain_low_confidence_reason_is_unchanged_when_no_cap_applied():
    a = C.assess(cand(0.65), TWO_KINDS)
    assert a.escalation_reasons == ["confidence 0.65 is below the threshold 0.70"]


def test_llm_error_escalates():
    a = C.assess(cand(0.9), TWO_KINDS, {S.RUN_LLM_ERROR: "timeout"})
    assert a.escalate and any("timeout" in r for r in a.escalation_reasons)


def test_run_info_may_be_missing():
    assert not C.assess(cand(0.9), TWO_KINDS, None).escalate


def test_never_raises_confidence_above_stated():
    for stated in (0.0, 0.2, 0.69, 0.7, 0.8, 1.0):
        assert C.assess(cand(stated), TWO_KINDS).confidence <= stated


@pytest.mark.parametrize("stated, expected", [(1.4, 1.0), (-0.3, 0.0), ("high", 0.0), (None, 0.0), (True, 0.0)])
def test_stated_confidence_is_clamped_and_the_clamp_is_explained(stated, expected):
    a = C.assess(cand(stated), TWO_KINDS)
    assert a.confidence == expected
    assert a.reasons and "stated confidence" in a.reasons[0]


def test_confidence_is_not_a_constant():
    values = {C.assess(cand(s), TWO_KINDS).confidence for s in (0.72, 0.8, 0.9)}
    assert len(values) == 3


def test_several_escalation_reasons_are_all_kept():
    a = C.assess(cand(0.9, component="unknown"), [ev(ok=False)], {S.RUN_LLM_ERROR: "boom"})
    assert len(a.escalation_reasons) >= 4
