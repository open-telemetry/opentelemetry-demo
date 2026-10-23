"""Offline synthetic tests. No live telemetry, inference or incident injection."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from incident_tools.f02.boundary import Config, iso
from incident_tools.eyes.core import Detector, Investigator, Store
from incident_tools.eyes.runtime import DEFAULTS, Router, architecture, export, load

NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


class FakeTools:
    def __init__(self):
        self.config = Config({'origin': 'fixture', 'services': ['checkout', 'payment'], 'prometheus': {'endpoint': 'http://localhost:9090'}})
        self.now = NOW
        self.value, self.rate, self.source_age, self.metric_status = 1500, 1, 0, 'ok'
        self.calls = []
        self.http = self

    def json(self, *args, **kwargs):
        return {'status': 'success', 'data': {'resultType': 'vector', 'result': [{'value': [self.now.timestamp(), str(self.now.timestamp() - self.source_age)]}]}}

    def schemas(self):
        return [{'function': {'name': name}} for name in ('query_metrics', 'search_traces', 'search_logs', 'container_health')]

    def call(self, tool, args):
        self.calls.append((tool, args))
        value = self.rate if args.get('metric') == 'request_rate' else self.value
        return {'tool': tool, 'service': args['service'], 'window': {'start': args['start'], 'end': args['end']},
                'origin': 'fixture', 'status': self.metric_status, 'warnings': [],
                'collected_at': iso(self.now), 'evidence_id': 'fixture-' + str(len(self.calls)),
                'observations': [{'source_id': 'fixture-source', 'samples': [{'timestamp': iso(self.now), 'value': value}], 'symptom': 'timeout'}] if self.metric_status == 'ok' else [],
                'provenance': {'query': 'fixture metric expression'}}


class AdaptiveModel:
    def __init__(self, bad=None):
        self.calls, self.bad = [], bad

    def decide(self, messages, remaining):
        self.calls.append(deepcopy(messages))
        incident = json.loads(messages[1]['content'])['incident']
        args = {'service': 'checkout', **incident['window']}
        if len(self.calls) == 1:
            return {'action': 'tool', 'tool': self.bad or 'search_traces', 'arguments': args, 'rationale': 'Investigate slow requests'}, {'model': 'fixture-model', 'slot': 'fixture'}
        prior = json.loads(messages[-1]['content'])
        if len(self.calls) == 2:
            assert prior['observations'][0]['symptom'] == 'timeout'
            return {'action': 'tool', 'tool': 'search_logs', 'arguments': args, 'rationale': 'Trace showed timeout; inspect matching logs'}, {'model': 'fixture-model', 'slot': 'fixture'}
        return {'action': 'finish', 'interpretations': [{'text': 'Timeout symptoms require further investigation', 'evidence_ids': [prior['evidence_id']]}], 'limitations': ['Synthetic test data']}, {'model': 'fixture-model', 'slot': 'fixture'}


class EyesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        self.tools = FakeTools()
        self.settings = {**DEFAULTS, 'services': ['checkout'], 'warmup_seconds': 1, 'thresholds': {'latency_p95_ms': 1000}}
        self.detector = Detector(self.tools, self.store, self.settings, clock=lambda: self.tools.now)

    def tearDown(self):
        self.store.db.close()
        self.tmp.cleanup()

    def tick(self, seconds=15):
        self.tools.now += timedelta(seconds=seconds)
        return self.detector.poll()

    def incident(self):
        self.detector.poll()
        self.tick()
        self.tick()
        return self.store.incidents()[0]

    def test_sustained_breach_deduplicated_and_evidence_saved(self):
        incident = self.incident()
        self.assertEqual(len(incident['alerts']), 1)
        self.assertEqual(incident['investigation'], 'queued')
        self.assertNotIn('cause', incident)
        for _ in range(4):
            self.tick()
        self.assertEqual(len(self.store.incidents()), 1)
        alert = incident['alerts'][0]
        self.assertTrue((Path(self.tmp.name) / (alert['evidence_id'] + '.json')).exists())
        self.assertEqual(alert['value'], 1500)

    def test_duplicate_source_never_counts_twice(self):
        self.detector.poll()
        self.tick()
        self.detector.poll()
        self.assertEqual(self.store.incidents(), [])
        self.tick()
        self.assertEqual(len(self.store.incidents()), 1)

    def test_stale_missing_and_low_volume_do_not_alert(self):
        for attribute, value in [('source_age', 300), ('metric_status', 'no_data'), ('rate', 0.001)]:
            with self.subTest(attribute=attribute):
                old = getattr(self.tools, attribute)
                setattr(self.tools, attribute, value)
                for _ in range(4):
                    self.tick()
                setattr(self.tools, attribute, old)
                self.assertEqual(self.store.incidents(), [])

    def test_restart_retains_dedup(self):
        self.incident()
        self.store.db.close()
        self.store = Store(self.tmp.name)
        self.detector.store = self.store
        self.tick()
        self.assertEqual(len(self.store.incidents()), 1)

    def test_recovery_and_cooldown(self):
        self.incident()
        self.tools.value = 500
        self.tick()
        self.tick()
        self.assertEqual(self.store.incidents()[0]['state'], 'closed')
        self.tools.value = 1500
        self.tick()
        self.tick()
        self.assertEqual(len(self.store.incidents()), 1)
        self.tick(301)
        self.tick()
        self.assertEqual(len(self.store.incidents()), 2)

    def test_two_symptoms_join_one_incident(self):
        self.settings['thresholds'] = {'latency_p95_ms': 1000, 'error_rate': 0.05}
        incident = self.incident()
        self.assertEqual(len(self.store.incidents()), 1)
        self.assertEqual(len(incident['alerts']), 2)

    def test_unknown_data_does_not_close_active_incident(self):
        self.incident()
        self.tools.metric_status = 'no_data'
        self.tick()
        self.tick()
        self.assertEqual(self.store.incidents()[0]['state'], 'open')

    def test_adaptive_loop_and_report_artifacts(self):
        incident = self.incident()
        model = AdaptiveModel()
        run = Investigator(self.tools, self.store, model, self.settings).run(incident)
        self.assertEqual(run['stop_reason'], 'model_finished')
        self.assertEqual([e['tool'] for e in run['evidence']], ['search_traces', 'search_logs'])
        self.assertTrue(run['decisions'][1]['based_on_evidence'])
        directory = Path(self.tmp.name) / 'run'
        export(run, directory)
        ET.parse(directory / 'checkpoint1_architecture.svg')
        self.assertIn('fixture', (directory / 'checkpoint1_incident_report.md').read_text())
        with self.assertRaises(FileExistsError):
            export(run, directory)

    def test_mutation_tool_rejected(self):
        incident = self.incident()
        before = len(self.tools.calls)
        run = Investigator(self.tools, self.store, AdaptiveModel('restart'), self.settings).run(incident)
        self.assertEqual(len(self.tools.calls), before)
        self.assertEqual(run['stop_reason'], 'invalid_decision_or_provider_failure')

    def test_unknown_citation_rejected(self):
        class BadModel:
            def decide(self, *args):
                return {'action': 'finish', 'interpretations': [{'text': 'invented', 'evidence_ids': ['invented']}], 'limitations': []}, {'model': 'fixture'}
        run = Investigator(self.tools, self.store, BadModel(), self.settings).run(self.incident())
        self.assertEqual(run['interpretations'], [])
        self.assertNotEqual(run['stop_reason'], 'model_finished')

    def test_repeat_query_and_outside_window_rejected(self):
        class BadModel:
            def __init__(self, outside):
                self.outside = outside
            def decide(inner, messages, remaining):
                incident = json.loads(messages[1]['content'])['incident']
                args = {'service': 'checkout', **incident['window']}
                if inner.outside:
                    args['start'] = iso(NOW - timedelta(days=1))
                return {'action': 'tool', 'tool': 'search_logs', 'arguments': args, 'rationale': 'Inspect'}, {'model': 'fixture'}
        incident = self.incident()
        for outside in (False, True):
            run = Investigator(self.tools, self.store, BadModel(outside), self.settings).run(incident)
            self.assertEqual(len(run['evidence']), 0 if outside else 1)
            self.assertNotEqual(run['stop_reason'], 'model_finished')

    def test_model_call_budget_enforced(self):
        incident = self.incident()
        run = Investigator(self.tools, self.store, AdaptiveModel(), {**self.settings, 'max_calls': 1}).run(incident)
        self.assertEqual(len(run['evidence']), 1)
        self.assertEqual(run['stop_reason'], 'tool_budget')

    def test_config_and_svg(self):
        cfg, settings, _, _ = load('incident_tools/eyes/operator.example.toml')
        self.assertEqual(settings['thresholds']['error_rate'], 0.05)
        ET.fromstring(architecture())
        with self.assertRaises(ValueError):
            Router({'route': 'cloud-only', 'cloud': {'enabled': False}})

    def test_provider_fallback_and_response_identity(self):
        cfg = {'route': 'local-first',
               'local': {'enabled': True, 'backend': 'ollama', 'endpoint': 'http://localhost:11434', 'model': 'fixture-local'},
               'cloud': {'enabled': True, 'backend': 'openai-compatible', 'endpoint': 'https://fixture.invalid/v1', 'model': 'fixture-cloud', 'api_key_env': 'EYES_TEST_KEY'}}
        with patch.dict('os.environ', {'EYES_TEST_KEY': 'synthetic-test-token'}):
            router = Router(cfg)
            response = io.BytesIO(json.dumps({'choices': [{'message': {'content': '{"action":"finish"}'}}]}).encode())
            with patch.object(router.opener, 'open', side_effect=[OSError('secret not logged'), response]) as opened:
                result, identity = router.decide([{'role': 'user', 'content': 'fixture'}], 10)
            self.assertEqual(identity['slot'], 'cloud')
            self.assertEqual(identity['model'], 'fixture-cloud')
            self.assertEqual(opened.call_count, 2)
            self.assertEqual(result['action'], 'finish')


if __name__ == '__main__':
    unittest.main()
