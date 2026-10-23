"""Offline checks and explicitly synthetic end-to-end export, with source preservation audit."""
import argparse
import ast
from datetime import timedelta
import hashlib
import io
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from .core import Detector, Investigator, Store
from .runtime import DEFAULTS, architecture, export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=False)
    checked = []
    for file in Path('incident_tools').rglob('*.py'):
        ast.parse(file.read_text(encoding='utf-8-sig'), filename=str(file))
        checked.append(str(file))
    ET.fromstring(architecture())
    suite = unittest.TestSuite()
    for directory in ('incident_tools/f02/tests', 'incident_tools/eyes/tests'):
        suite.addTests(unittest.TestLoader().discover(directory))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    (output / 'test_results.txt').write_text(stream.getvalue(), encoding='utf-8')
    baseline = json.loads(Path('artifacts/eyes/baseline.json').read_text(encoding='utf-8'))
    changed = [p for p,h in baseline.items() if not Path(p).is_file() or hashlib.sha256(Path(p).read_bytes()).hexdigest() != h]
    from test_eyes import FakeTools, AdaptiveModel
    tools = FakeTools()
    store = Store(output / 'synthetic-state')
    settings = {**DEFAULTS, 'services': ['checkout'], 'warmup_seconds': 1, 'thresholds': {'latency_p95_ms': 1000}}
    detector = Detector(tools, store, settings, clock=lambda: tools.now)
    for _ in range(3):
        detector.poll()
        tools.now += timedelta(seconds=15)
    run = Investigator(tools, store, AdaptiveModel(), settings).run(store.incidents()[0])
    export(run, output / 'SYNTHETIC-fixture-report')
    store.db.close()
    summary = {'ast_files': checked, 'tests_run': result.testsRun, 'failures': len(result.failures),
               'errors': len(result.errors), 'baseline_files_checked': len(baseline), 'changed_existing_files': changed,
               'svg_xml_valid': True, 'fixture_stop_reason': run['stop_reason'],
               'fixture_tools': [e['tool'] for e in run['evidence']], 'live_incident_executed': False,
               'real_llm_called': False, 'notice': 'Offline synthetic verification only. Checkpoint 1 live acceptance is pending.'}
    (output / 'verification.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
    return 0 if result.wasSuccessful() and not changed and run['stop_reason'] == 'model_finished' else 1


if __name__ == '__main__':
    raise SystemExit(main())
