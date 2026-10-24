"""Offline regression verification; no live telemetry, credentials or incident injection."""
import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
ROOT = Path("artifacts/f02-timestamp-fix")
EXPECTED = {"incident_tools/f02/tools.py", "incident_tools/f02/tests/test_f02.py", "incident_tools/f02/README.md"}


def main():
    parsed = []
    for file in Path("incident_tools").rglob("*.py"):
        ast.parse(file.read_text(encoding="utf-8-sig"), filename=str(file))
        parsed.append(str(file))
    legacy = unittest.TestSuite()
    for directory in ("incident_tools/f02/tests", "incident_tools/eyes/tests"):
        legacy.addTests(unittest.TestLoader().discover(directory))
    baseline_module = types.ModuleType("incident_tools.f02.timestamp_baseline")
    baseline_module.__package__ = "incident_tools.f02"
    source = subprocess.check_output(["git", "show", "HEAD:incident_tools/f02/tools.py"]).decode("utf-8-sig")
    exec(compile(source, "<HEAD F02 source: regression comparison only>", "exec"), baseline_module.__dict__)
    comparison = unittest.TestLoader().loadTestsFromName(
        "test_f02.ToolTests.test_fractional_metric_windows_match_millisecond_backend_precision")
    stream = io.StringIO()
    with patch("test_f02.ObservabilityTools", baseline_module.ObservabilityTools):
        original = unittest.TextTestRunner(stream=stream, verbosity=2).run(comparison)
    (ROOT / "baseline_regression.txt").write_text(
        "EXPECTED FAILURE: the new fractional-window regression against unchanged HEAD source.\n\n" + stream.getvalue(),
        encoding="utf-8")
    stream = io.StringIO()
    first = unittest.TextTestRunner(stream=stream, verbosity=2).run(legacy)
    suite = unittest.TestLoader().discover("incident_tools/eyes_acceptance/tests")
    with patch("socket.socket", side_effect=AssertionError("No network in acceptance fixture tests")), patch(
            "subprocess.Popen", side_effect=AssertionError("No processes in acceptance fixture tests")):
        second = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    (ROOT / "test_results.txt").write_text(stream.getvalue(), encoding="utf-8")
    baseline = json.loads((ROOT / "baseline.json").read_text())
    changed = {name for name, digest in baseline.items()
               if not Path(name).is_file() or hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest}
    summary = {
        "tests_run": first.testsRun + second.testsRun,
        "failures": len(first.failures) + len(second.failures),
        "errors": len(first.errors) + len(second.errors),
        "regression_fails_on_original_code": len(original.failures) == 1 and not original.errors,
        "ast_files_checked": len(parsed),
        "baseline_files_checked": len(baseline),
        "changed_tracked_files": sorted(changed),
        "only_expected_files_changed": changed == EXPECTED,
        "live_telemetry_queried": False, "real_llm_called": False,
        "practice_fault_executed": False,
        "notice": "Synthetic regression verification. Legacy HTTP tests use loopback fixtures only. No live success is claimed.",
    }
    (ROOT / "verification.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if first.wasSuccessful() and second.wasSuccessful() and summary["regression_fails_on_original_code"] and changed == EXPECTED else 1


if __name__ == "__main__":
    raise SystemExit(main())
