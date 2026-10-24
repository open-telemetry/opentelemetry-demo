"""One offline verification pass: existing tests, new acceptance tests and synthetic export."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from .tests.test_acceptance import fixture_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--baseline", default="artifacts/eyes-acceptance/baseline.json")
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=False)
    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8-sig"))
    parsed = []
    for path in Path("incident_tools").rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        parsed.append(str(path))
    suite = unittest.TestSuite()
    for directory in ("incident_tools/f02/tests", "incident_tools/eyes/tests"):
        suite.addTests(unittest.TestLoader().discover(directory))
    stream = io.StringIO()
    legacy = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    suite = unittest.TestLoader().discover("incident_tools/eyes_acceptance/tests")
    with patch("socket.socket", side_effect=AssertionError("Static checks forbid network access")), patch(
            "subprocess.Popen", side_effect=AssertionError("Static checks forbid external processes")):
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        fixture, _, _, _, _ = fixture_run(output / "SYNTHETIC-fixture-run")
    (output / "test_results.txt").write_text(stream.getvalue(), encoding="utf-8")
    ET.parse(output / "SYNTHETIC-fixture-run/report/checkpoint1_architecture.svg")
    changed = [name for name, digest in baseline.items()
               if not Path(name).is_file() or hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest]
    checks = fixture["checks"]
    summary = {"tests_run": legacy.testsRun + result.testsRun,
               "failures": len(legacy.failures) + len(result.failures),
               "errors": len(legacy.errors) + len(result.errors),
               "ast_files_checked": len(parsed), "baseline_files_checked": len(baseline),
               "changed_existing_files": changed, "svg_xml_valid": True,
               "fixture_structural_checks_passed": all(value for name, value in checks.items() if name != "real_backend_evidence"),
               "fixture_rejected_as_live_acceptance": not fixture["automated_checks_passed"],
               "live_incident_executed": False, "real_llm_called": False,
               "new_suite_network_and_external_processes_blocked": True,
               "legacy_suite_transport": "Loopback fixture HTTP servers and local Python CLI tests only",
               "notice": "Offline verification only. Real telemetry, provider connectivity and live semantic review remain pending."}
    (output / "verification.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if legacy.wasSuccessful() and result.wasSuccessful() and not changed and summary["fixture_structural_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
