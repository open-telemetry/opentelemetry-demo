import pytest

from eval.run_eval import calibration, load_expected, score

FAULT = {
    "component": "valkey-cart",
    "category": "dependency_unavailable",
    "accept_categories": ["container_down"],
}
HEALTHY = {"component": None, "category": "no_incident", "decision": "no_action"}


def _d(component, category, decision="act", confidence=0.9, affected=()):
    return {
        "component": component,
        "category": category,
        "decision": decision,
        "confidence": confidence,
        "affected_services": list(affected),
        "alternatives": [],
    }


@pytest.mark.parametrize(
    ("expected", "d", "valid", "want"),
    [
        (FAULT, _d("valkey-cart", "dependency_unavailable"), True, (1.0, "correct")),
        (FAULT, _d("valkey-cart", "container_down"), True, (1.0, "correct")),
        (
            FAULT,
            _d("valkey-cart", "app_error"),
            True,
            (0.5, "partial (category wrong)"),
        ),
        (
            FAULT,
            _d(None, "unknown", "escalate", affected=["cart", "valkey-cart"]),
            True,
            (0.5, "escalated, right component named"),
        ),
        (
            FAULT,
            _d("cart", "app_error"),
            True,
            (0.0, "RED confident act, wrong component"),
        ),
        (
            FAULT,
            _d(None, "no_incident", "no_action"),
            True,
            (0.0, "RED missed incident (no_action)"),
        ),
        (
            FAULT,
            _d("valkey-cart", "dependency_unavailable"),
            False,
            (0.0, "RED invalid report"),
        ),
        (HEALTHY, _d(None, "no_incident", "no_action"), True, (1.0, "correct")),
        (
            HEALTHY,
            _d("product-catalog", "resource_cpu"),
            True,
            (0.0, "RED confident act on a healthy system"),
        ),
        (
            HEALTHY,
            _d(None, "unknown", "escalate"),
            True,
            (0.5, "escalated on a healthy system"),
        ),
    ],
)
def test_score(expected, d, valid, want):
    assert score(expected, d, valid) == want


def test_expected_has_baseline_and_faults():
    expected = load_expected()
    assert expected["baseline"]["category"] == "no_incident"
    assert all("component" in e and "category" in e for e in expected.values())


def test_calibration_buckets():
    rows = [
        {"diagnosis": {"confidence": 0.95}, "score": 1.0},
        {"diagnosis": {"confidence": 0.75}, "score": 0.0},
    ]
    table = calibration(rows)
    assert "| 0.9-1.0 | 1 | 1.00 |" in table
    assert "| 0.7-0.9 | 1 | 0.00 |" in table


def test_default_run_only_uses_recorded_scenarios():
    from eval.run_eval import FIXTURES

    expected = load_expected()
    recorded = [n for n in expected if (FIXTURES / n).is_dir()]
    assert "baseline" in recorded and "scenario-01" not in recorded


def _row(name, diagnosis, report_valid=True):
    return {
        "scenario": name,
        "run_id": "r",
        "diagnosis": diagnosis,
        "steps": 1,
        "stopped": "finish",
        "tokens": 0,
        "seconds": 0.1,
        "report_valid": report_valid,
        "llm_models": [],
        "report_notes": [],
    }


_EXPECTED_06 = {"component": "valkey-cart", "category": "dependency_unavailable"}


def _patch_eval(tmp_path, monkeypatch, diagnosis):
    from eval import run_eval

    monkeypatch.setattr(run_eval, "RESULTS", tmp_path)
    monkeypatch.setattr(
        run_eval, "load_expected", lambda *a, **k: {"scenario-06": _EXPECTED_06}
    )
    monkeypatch.setattr(
        run_eval, "run_scenario", lambda name, live: _row(name, diagnosis)
    )
    return run_eval


def test_fail_on_red_returns_nonzero(tmp_path, monkeypatch):
    run_eval = _patch_eval(
        tmp_path, monkeypatch, _d("cart", "app_error")
    )  # wrong -> RED
    rc = run_eval.main(["--scenarios", "scenario-06", "--pause", "0", "--fail-on-red"])
    assert rc == 1


def test_no_red_returns_zero(tmp_path, monkeypatch):
    run_eval = _patch_eval(
        tmp_path,
        monkeypatch,
        _d("valkey-cart", "dependency_unavailable"),  # correct
    )
    rc = run_eval.main(["--scenarios", "scenario-06", "--pause", "0", "--fail-on-red"])
    assert rc == 0


def test_rerun_is_deterministic(tmp_path, monkeypatch, capsys):
    # F17 acceptance: same scenario twice -> same component/output.
    run_eval = _patch_eval(
        tmp_path, monkeypatch, _d("valkey-cart", "dependency_unavailable")
    )
    rc1 = run_eval.main(["--scenarios", "scenario-06", "--pause", "0"])
    out1 = capsys.readouterr().out
    rc2 = run_eval.main(["--scenarios", "scenario-06", "--pause", "0"])
    out2 = capsys.readouterr().out
    assert rc1 == rc2 == 0
    assert "valkey-cart" in out1
    assert out1 == out2
