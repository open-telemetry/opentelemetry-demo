"""Isolated contract tests for the existing faultctl; never write the live flag file."""

import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch


OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent
sys.path.insert(0, str(ROOT / 'src'))
from faultctl import flags
from faultctl.client import FaultClient, HttpTransport
from faultctl.scenarios import SCENARIOS


BASE = json.loads((ROOT / 'src/flagd/demo.flagd.json').read_text(encoding='utf-8'))
COMMANDS = []
DETAILS = {}


class FakeAPI:
    def __init__(self, mode='apply'):
        self.mode = mode
        self.state = copy.deepcopy(BASE)
        self.writes = []
        self.requests = []

    def __enter__(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def respond(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                owner.requests.append(('GET', self.path))
                if self.path == '/feature/api/read':
                    self.respond(200, {'flags': owner.state.get('flags', {})})
                else:
                    self.respond(404, {})

            def do_POST(self):
                owner.requests.append(('POST', self.path))
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path != '/feature/api/write' or set(data) != {'data'}:
                    self.respond(400, {})
                    return
                owner.writes.append(data)
                if owner.mode == 'fail-revert' and len(owner.writes) > 1:
                    self.respond(500, {'error': 'simulated reset write failure'})
                else:
                    if owner.mode != 'ack-only':
                        owner.state = copy.deepcopy(data['data'])
                    self.respond(200, {})

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}/feature/api'
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class FaultctlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='fixture-', dir=OUT)
        self.directory = Path(self.tmp.name).resolve()
        assert self.directory.is_relative_to(OUT.resolve())
        self.file = self.directory / 'flags.json'
        self.write(BASE)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, data):
        self.file.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')

    def read(self):
        return json.loads(self.file.read_text(encoding='utf-8'))

    def run_cli(self, *args, api=None):
        transport = ['--api', '--api-url', api] if api else ['--local', '--file', str(self.file)]
        command = [sys.executable, '-B', str(ROOT / 'faultctl.py'), *transport, *args]
        done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=10)
        COMMANDS.append({'test': self.id(), 'command': command,
                         'exit_code': done.returncode, 'stdout': done.stdout, 'stderr': done.stderr})
        return done

    def active(self, name, data=None):
        return flags.get_active_variant((data or self.read())['flags'][name])

    def test_launchers_help_and_version(self):
        for args in (['--help'], ['--version']):
            done = subprocess.run([sys.executable, '-B', str(ROOT/'faultctl.py'), *args],
                                  capture_output=True, text=True, timeout=10)
            self.assertEqual(done.returncode, 0, done.stderr)
        env = dict(os.environ, PYTHONPATH=str(ROOT/'src'), PYTHONDONTWRITEBYTECODE='1')
        done = subprocess.run([sys.executable, '-B', '-m', 'faultctl', '--version'],
                              cwd=self.directory, env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_all_existing_variant_set_clear_combinations(self):
        combinations = 0
        for name, data in BASE['flags'].items():
            self.assertIn('off', data['variants'])
            for variant in data['variants']:
                config = copy.deepcopy(BASE)
                flags.set_flag(config, name, variant)
                self.assertEqual(self.active(name, config), variant)
                flags.clear_flag(config, name)
                self.assertEqual(self.active(name, config), 'off')
                combinations += 1
        DETAILS['variant_set_clear_combinations'] = combinations

    def test_targeted_flag_preserves_predicate_and_fallback(self):
        done = self.run_cli('set', 'productCatalogFailure', 'on')
        self.assertEqual(done.returncode, 0, done.stderr)
        before, after = BASE['flags']['productCatalogFailure'], self.read()['flags']['productCatalogFailure']
        self.assertEqual(after['targeting']['if'][1], 'on')
        self.assertEqual(after['targeting']['if'][0], before['targeting']['if'][0])
        self.assertEqual(after['targeting']['if'][2], before['targeting']['if'][2])
        self.assertEqual(after['defaultVariant'], before['defaultVariant'])

    def test_standard_set_and_clear(self):
        self.assertEqual(self.run_cli('set', 'paymentFailure', '100%').returncode, 0)
        self.assertEqual(self.active('paymentFailure'), '100%')
        self.assertEqual(self.run_cli('clear', 'paymentFailure').returncode, 0)
        self.assertEqual(self.active('paymentFailure'), 'off')

    def test_default_variant_is_documented_first_nonoff(self):
        self.assertEqual(self.run_cli('inject', 'paymentFailure').returncode, 0)
        self.assertEqual(self.active('paymentFailure'), '10%')

    def test_unknown_flag_and_variant_do_not_write(self):
        for args in (('set', 'notAFlag', 'on'), ('set', 'paymentFailure', 'notAVariant'),
                     ('clear', 'notAFlag'), ('scenario', 'apply', 'notAScenario')):
            before = self.file.read_bytes()
            done = self.run_cli(*args)
            self.assertNotEqual(done.returncode, 0)
            self.assertEqual(self.file.read_bytes(), before)

    def test_list_active_service_filters_and_status(self):
        self.assertEqual(self.run_cli('set', 'paymentFailure', '50%').returncode, 0)
        done = self.run_cli('list', '--active', '--service', 'payment', '--json')
        self.assertEqual(done.returncode, 0, done.stderr)
        records = json.loads(done.stdout)
        self.assertEqual([r['name'] for r in records], ['paymentFailure'])
        self.assertEqual(records[0]['active_variant'], '50%')
        self.assertEqual(self.run_cli('status').returncode, 0)

    def test_trigger_all_dry_run_does_not_write(self):
        before = self.file.read_bytes()
        self.assertEqual(self.run_cli('trigger-all', '--dry-run').returncode, 0)
        self.assertEqual(self.file.read_bytes(), before)

    def test_bulk_fault_injection_excludes_explicit_nonfailure_pii_flag(self):
        data = copy.deepcopy(BASE)
        flags.trigger_all(data)
        DETAILS['bulk_pii_flag'] = {
            'emitRawPii_after_trigger_all': self.active('emitRawPii', data),
            'metadata': BASE['flags']['emitRawPii'].get('metadata'),
            'description': BASE['flags']['emitRawPii'].get('description')}
        self.assertEqual(self.active('emitRawPii', data), 'off',
                         'Bulk incident injection enabled a flag explicitly described as not a failure scenario')

    def test_trigger_all_and_reset_local(self):
        self.assertEqual(self.run_cli('trigger-all').returncode, 0)
        self.assertTrue(all(flags.is_active(v) for v in self.read()['flags'].values()))
        self.assertEqual(self.run_cli('reset').returncode, 0)
        self.assertTrue(all(not flags.is_active(v) for v in self.read()['flags'].values()))
        self.assertEqual(self.read()['$schema'], BASE['$schema'])

    def test_all_preset_scenarios_resolve_and_apply(self):
        for name, scenario in SCENARIOS.items():
            with self.subTest(scenario=name):
                self.write(BASE)
                done = self.run_cli('scenario', 'apply', name)
                self.assertEqual(done.returncode, 0, done.stderr)
                for flag_name, variant in scenario['flags'].items():
                    self.assertEqual(self.active(flag_name), variant)
                for flag_name in BASE['flags'].keys() - scenario['flags'].keys():
                    self.assertEqual(self.read()['flags'][flag_name], BASE['flags'][flag_name])
        DETAILS['preset_scenarios_exercised'] = len(SCENARIOS)

    def test_timed_set_success(self):
        done = self.run_cli('set', 'paymentFailure', '100%', '--duration', '1')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.active('paymentFailure'), 'off')

    def test_timed_scenario_success(self):
        done = self.run_cli('scenario', 'apply', 'catalog-fail', '--duration', '1')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.active('productCatalogFailure'), 'off')

    def test_timed_trigger_all_success(self):
        done = self.run_cli('trigger-all', '--duration', '1')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(all(not flags.is_active(v) for v in self.read()['flags'].values()))

    def test_http_routes_envelope_and_flag_roundtrip(self):
        with FakeAPI() as api:
            done = self.run_cli('set', 'paymentFailure', '100%', api=api.url)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(self.active('paymentFailure', api.state), '100%')
            self.assertEqual(api.requests, [('GET', '/feature/api/read'), ('POST', '/feature/api/write')])
            self.assertEqual(set(api.writes[0]), {'data'})

    def test_explicit_api_failure_does_not_fall_back_to_file(self):
        before = self.file.read_bytes()
        with patch.object(HttpTransport, 'read', side_effect=OSError('simulated unavailable API')):
            client = FaultClient(mode='api', file_path=self.file)
            with self.assertRaises(OSError):
                client.read()
        self.assertEqual(self.file.read_bytes(), before)

    def test_auto_transport_falls_back_locally_as_implemented(self):
        with patch.object(HttpTransport, 'is_available', return_value=False):
            client = FaultClient(file_path=self.file)
            self.assertEqual(client.transport_name, 'local')
            data = client.read()
            flags.set_flag(data, 'paymentFailure', '100%')
            client.write(data)
            self.assertEqual(self.active('paymentFailure'), '100%')

    def test_negative_set_duration_rejected_before_mutation(self):
        before = self.file.read_bytes()
        done = self.run_cli('set', 'paymentFailure', '100%', '--duration', '-1')
        DETAILS['negative_set_duration'] = {'exit_code': done.returncode,
            'active_after_command': self.active('paymentFailure'), 'stderr': done.stderr}
        self.assertNotEqual(done.returncode, 0, 'CLI returned success with a fault still active')
        self.assertEqual(self.file.read_bytes(), before)

    def test_negative_scenario_duration_rejected_before_mutation(self):
        before = self.file.read_bytes()
        done = self.run_cli('scenario', 'apply', 'payment-fail', '--duration', '-1')
        DETAILS['negative_scenario_duration'] = {'exit_code': done.returncode,
                                               'active_after_command': self.active('paymentFailure')}
        self.assertEqual(self.file.read_bytes(), before, 'Invalid duration changed flags before failing')

    def test_negative_trigger_all_duration_rejected_before_mutation(self):
        before = self.file.read_bytes()
        done = self.run_cli('trigger-all', '--duration', '-1')
        DETAILS['negative_trigger_all_duration'] = {'exit_code': done.returncode,
            'active_count': sum(flags.is_active(v) for v in self.read()['flags'].values())}
        self.assertEqual(self.file.read_bytes(), before, 'Invalid duration activated every flag before failing')

    def test_failed_auto_revert_returns_nonzero(self):
        with FakeAPI(mode='fail-revert') as api:
            done = self.run_cli('set', 'paymentFailure', '100%', '--duration', '1', api=api.url)
            DETAILS['failed_auto_revert'] = {'exit_code': done.returncode,
                'active_after_command': self.active('paymentFailure', api.state), 'stderr': done.stderr}
            self.assertNotEqual(done.returncode, 0, 'Auto-revert HTTP 500 printed a thread exception but CLI returned success')

    def test_acknowledgement_without_apply_is_not_reported_as_success(self):
        with FakeAPI(mode='ack-only') as api:
            done = self.run_cli('set', 'paymentFailure', '100%', api=api.url)
            DETAILS['ack_only_api'] = {'exit_code': done.returncode,
                                      'active_after_command': self.active('paymentFailure', api.state),
                                      'stdout': done.stdout}
            self.assertNotEqual(done.returncode, 0, 'CLI reported success without detecting unchanged API state')

    def test_api_roundtrip_preserves_top_level_metadata(self):
        with FakeAPI() as api:
            self.assertEqual(self.run_cli('set', 'paymentFailure', '100%', api=api.url).returncode, 0)
            DETAILS['api_metadata'] = {'before_keys': list(BASE), 'after_keys': list(api.state)}
            self.assertIn('$schema', api.state, 'Read/replace API roundtrip discarded existing $schema')

    def test_interleaved_file_clients_preserve_both_changes(self):
        first, second = FaultClient(mode='local', file_path=self.file), FaultClient(mode='local', file_path=self.file)
        a, b = first.read(), second.read()
        flags.set_flag(a, 'paymentFailure', '100%')
        flags.set_flag(b, 'adHighCpu', 'on')
        first.write(a)
        second.write(b)
        DETAILS['interleaved_writers'] = {'paymentFailure': self.active('paymentFailure'),
                                          'adHighCpu': self.active('adHighCpu')}
        self.assertEqual(self.active('paymentFailure'), '100%', 'Second stale snapshot silently erased first client change')


def main():
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(FaultctlTests))
    baseline = json.loads((OUT/'baseline.json').read_text())['files']
    changed = [name for name, digest in baseline.items()
               if not (ROOT/name).is_file() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest]
    results = {'tests_run': result.testsRun, 'failures': len(result.failures),
        'errors': len(result.errors), 'passing': result.testsRun-len(result.failures)-len(result.errors),
        'failed_contracts': [test.id() for test, _ in result.failures],
        'details': DETAILS, 'protected_files': len(baseline), 'original_files_changed': changed,
        'live_demo_mutations': 0, 'live_flagd_api_calls': 0,
        'api_test_scope': 'Local disposable HTTP stub matching inspected API shape; not live Elixir/flagd validation'}
    (OUT/'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    (OUT/'commands.json').write_text(json.dumps(COMMANDS, indent=2), encoding='utf-8')
    (OUT/'test_output.txt').write_text(stream.getvalue(), encoding='utf-8')
    print(stream.getvalue())
    print(json.dumps({key: results[key] for key in ('tests_run', 'passing', 'failures', 'errors',
                                                  'protected_files', 'original_files_changed')}, indent=2))
    raise SystemExit(0 if result.wasSuccessful() and not changed else 1)


if __name__ == '__main__':
    main()
