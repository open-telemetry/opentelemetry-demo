"""Run offline contracts and verify that pre-existing repository files are unchanged."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import unittest

from .boundary import iso, utc_now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', default='artifacts/f02/baseline.json')
    parser.add_argument('--output-dir', required=True, help='A NEW directory for verification artifacts')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if Path.cwd().resolve() != root:
        parser.error('Run from the repository root')
    baseline = json.loads(Path(args.baseline).read_text(encoding='utf-8-sig'))
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=False)
    stream = io.StringIO()
    suite = unittest.TestLoader().discover(str(root / 'incident_tools' / 'f02' / 'tests'))
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    changed, missing = [], []
    for name, expected in baseline['files'].items():
        file = root / name
        if not file.is_file():
            missing.append(name)
        elif hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            changed.append(name)
    diff = subprocess.check_output(['git', 'diff', '--name-only', 'HEAD'], text=True).splitlines()
    added = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], text=True).splitlines()
    summary = {
        'verified_at': iso(utc_now()),
        'baseline_head': baseline['head'],
        'current_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'baseline_files_checked': len(baseline['files']),
        'changed_existing_files': changed, 'missing_existing_files': missing,
        'tracked_diff': diff, 'new_paths': added,
        'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'skipped': len(result.skipped), 'fixture_contracts_passed': result.wasSuccessful(),
        'source_preservation_passed': not (changed or missing or diff),
        'live_demo_validation': 'not_run',
        'evidence_notice': 'Tests use synthetic HTTP/Docker/audit fixtures. They are not incident telemetry or live acceptance.',
    }
    (output / 'test_results.txt').write_text(stream.getvalue(), encoding='utf-8')
    (output / 'verification.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'new_paths'}, indent=2))
    return 0 if result.wasSuccessful() and summary['source_preservation_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
