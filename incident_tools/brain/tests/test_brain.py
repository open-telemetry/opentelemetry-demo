"""Brain stage 1 tests. All evidence is SYNTHETIC: produced by real F02 code over fake transports."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from incident_tools.brain import RunFormatError, extract, load_run
from incident_tools.f02 import ObservabilityTools
from incident_tools.f02.boundary import Config, timestamp

START, END = '2026-01-02T10:00:00Z', '2026-01-02T10:05:00Z'
NOW = datetime(2026, 1, 2, 10, 6, tzinfo=timezone.utc)
TRACE, SPAN, CONTAINER = 'ab' * 16, 'cd' * 8, 'e' * 64
REPO = Path(__file__).resolve().parents[3]


def metric_response(values=('1500',)):
    end = timestamp(END).timestamp()
    return {'status': 'success', 'data': {'resultType': 'matrix', 'result': [
        {'metric': {'service_name': 'checkout'},
         'values': [[end - 30 * (len(values) - 1 - i), v] for i, v in enumerate(values)]}]}}


def span(code=2, trace=TRACE):
    begin = int(timestamp(END).timestamp() - 10) * 10**9
    return {'traceId': trace, 'spanId': SPAN, 'name': 'oteldemo.ShippingService/GetQuote', 'kind': 3,
            'startTimeUnixNano': str(begin), 'endTimeUnixNano': str(begin + 4_000_000_000),
            'status': {'code': code}, 'attributes': [{'key': 'rpc.grpc.status_code', 'value': {'intValue': '4'}}]}


def logs_response(total=1, trace=TRACE):
    return {'timed_out': False, '_shards': {'failed': 0}, 'hits': {'total': {'value': total, 'relation': 'eq'}, 'hits': [
        {'_index': 'otel-logs-2026-01-02', '_id': 'doc-1', '_source': {
            'resource': {'service': {'name': 'checkout'}}, 'observedTimestamp': '2026-01-02T10:04:00Z',
            'body': 'failed to get shipping quote: context deadline exceeded', 'severity': {'text': 'ERROR'},
            'traceId': trace, 'spanId': SPAN}}]}}


class FakeHTTP:
    def __init__(self, responses):
        self.responses = responses

    def json(self, backend, route, params=None, body=None):
        return deepcopy(self.responses[backend])


class FakeDocker:
    def __init__(self, status='running', events=()):
        self.status, self.events = status, events

    def run(self, args):
        if args[0] == 'ps':
            return CONTAINER + '\n'
        if args[0] == 'inspect':
            return json.dumps({'id': CONTAINER, 'project': 'opentelemetry-demo', 'service': 'checkout',
                               'status': self.status, 'running': self.status == 'running', 'exit_code': 0,
                               'started_at': '2026-01-02T09:00:00Z', 'finished_at': '0001-01-01T00:00:00Z',
                               'health': 'healthy'})
        return ''.join(json.dumps({'Actor': {'ID': CONTAINER, 'Attributes': {
            'com.docker.compose.project': 'opentelemetry-demo', 'com.docker.compose.service': 'checkout'}},
            'Action': action, 'timeNano': int(timestamp(END).timestamp() - 60) * 10**9}) + '\n' for action in self.events)


def tools(responses=None, docker=None):
    config = Config({'origin': 'fixture', 'services': ['checkout', 'payment'], 'limits': {'retries': 0},
                     **{k: {'endpoint': 'http://fixture.invalid'} for k in ('prometheus', 'jaeger', 'opensearch')}})
    base = {'prometheus': metric_response(), 'opensearch': logs_response(),
            'jaeger': {'result': {'resourceSpans': [{'resource': {'attributes': [
                {'key': 'service.name', 'value': {'stringValue': 'checkout'}}]}, 'scopeSpans': [{'spans': [span()]}]}]}}}
    return ObservabilityTools(config, http=FakeHTTP({**base, **(responses or {})}),
                              docker=docker or FakeDocker(events=('die', 'start')), clock=lambda: NOW)


def call(t, tool, **extra):
    return t.call(tool, {'service': 'checkout', 'start': START, 'end': END, **extra})


def run_dict(evidence, alert_ref=None):
    """Mirror of incident_tools.eyes.core.Investigator.run output."""
    return {'incident': {'id': 'incident-synthetic', 'service': 'checkout', 'window': {'start': START, 'end': END},
                         'detected_at': END, 'state': 'open', 'investigation': 'finished', 'origin': 'fixture',
                         'alerts': [{'metric': 'latency_p95_ms', 'threshold': 1000, 'value': 1500, 'timestamp': END,
                                     'source_time': END, 'evidence_id': alert_ref or 'f02-detector-only',
                                     'freshness_evidence_id': 'fresh-x', 'coverage_evidence_id': 'f02-y',
                                     'query': 'synthetic'}]},
            'evidence': evidence, 'decisions': [], 'interpretations': [], 'limitations': ['synthetic'],
            'stop_reason': 'model_finished', 'finished_at': END, 'origin': 'fixture'}


def full_run():
    t = tools()
    metric = call(t, 'query_metrics', metric='latency_p95_ms')
    evidence = [metric, call(t, 'search_traces'), call(t, 'search_logs'), call(t, 'container_health'),
                call(t, 'container_events'), call(t, 'deployment_history')]
    return run_dict(evidence, metric['evidence_id'])


def by_type(facts, kind):
    return [f for f in facts if f.type == kind]


class LoaderTests(unittest.TestCase):
    def test_real_f02_shapes_load_and_classify(self):
        run = load_run(full_run())
        categories = {e.tool: e.category for e in run.evidence.values()}
        self.assertEqual(categories['query_metrics'], 'usable')
        self.assertEqual(categories['container_health'], 'usable_with_limits')
        self.assertEqual(categories['deployment_history'], 'unavailable')
        self.assertEqual(run.unsupported, ())
        self.assertEqual(run.stop_reason, 'model_finished')
        self.assertEqual(run.incident['id'], 'incident-synthetic')

    def test_path_and_dict_inputs_are_equivalent(self):
        data = full_run()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'checkpoint1_execution_log.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            self.assertEqual(load_run(path), load_run(str(path)))
            self.assertEqual(load_run(path), load_run(data))

    def test_repository_synthetic_eyes_log_loads_with_unsupported_shapes_recorded(self):
        path = REPO / 'artifacts/eyes/check-01/SYNTHETIC-fixture-report/checkpoint1_execution_log.json'
        run = load_run(path)
        self.assertEqual(run.origin, 'fixture')
        self.assertTrue(run.unsupported)
        self.assertTrue(all('missing fields' in u['reason'] for u in run.unsupported))
        facts = extract(run)
        self.assertEqual({f.type for f in facts}, {'alert', 'evidence_gap'})

    def test_malformed_and_unreadable_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / 'bad.json'
            bad.write_text('{not json', encoding='utf-8')
            for source in (bad, Path(tmp) / 'missing.json', 42, ['list']):
                with self.subTest(source=source), self.assertRaises(RunFormatError):
                    load_run(source)

    def test_missing_fields_and_invalid_types_name_the_field_only(self):
        data = full_run()
        cases = [('incident', None), ('evidence', None), ('stop_reason', None), ('evidence', {}),
                 ('stop_reason', 3), ('decisions', 'x')]
        for key, value in cases:
            broken = deepcopy(data)
            if value is None:
                del broken[key]
            else:
                broken[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(RunFormatError) as ctx:
                load_run(broken)
            self.assertIn(key, str(ctx.exception))
        broken = deepcopy(data)
        broken['incident']['alerts'] = 'secret-value'
        with self.assertRaises(RunFormatError) as ctx:
            load_run(broken)
        self.assertNotIn('secret-value', str(ctx.exception))
        broken = deepcopy(data)
        broken['evidence'][0] = {'status': 'ok'}
        with self.assertRaises(RunFormatError):
            load_run(broken)

    def test_duplicate_identifiers(self):
        data = full_run()
        data['evidence'].append(deepcopy(data['evidence'][0]))
        run = load_run(data)
        self.assertEqual(len(run.evidence), 6)
        self.assertTrue(run.notes)
        data['evidence'][-1]['status'] = 'error'
        with self.assertRaises(RunFormatError):
            load_run(data)

    def test_empty_error_and_unavailable_are_never_usable(self):
        t = tools({'prometheus': {'status': 'success', 'data': {'resultType': 'matrix', 'result': []}}})
        no_data = call(t, 'query_metrics', metric='error_rate')
        error = call(tools({'prometheus': {'status': 'error'}}), 'query_metrics', metric='error_rate')
        invalid = tools().call('query_metrics', {'service': 'not-allowed', 'start': START, 'end': END})
        unavailable = call(t, 'deployment_history')
        run = load_run(run_dict([no_data, error, invalid, unavailable]))
        self.assertEqual([e.category for e in run.evidence.values()], ['empty', 'error', 'invalid_request', 'unavailable'])
        self.assertFalse(any(e.usable for e in run.evidence.values()))
        self.assertEqual(load_run(run_dict([])).evidence, {})

    def test_failed_result_with_observations_is_not_trusted(self):
        good = call(tools(), 'search_logs')
        forged = {**deepcopy(good), 'status': 'error', 'evidence_id': 'f02-forged'}
        run = load_run(run_dict([forged]))
        self.assertEqual(run.evidence['f02-forged'].observations, ())
        self.assertEqual(run.unsupported[0]['reason'], 'status error')

    def test_partial_keeps_valid_observations_and_warnings(self):
        partial = call(tools({'opensearch': logs_response(total=500)}), 'search_logs', limit=1)
        self.assertEqual(partial['status'], 'partial')
        e = load_run(run_dict([partial])).evidence[partial['evidence_id']]
        self.assertTrue(e.usable)
        self.assertEqual(len(e.observations), 1)
        self.assertTrue(e.warnings)

    def test_unexpected_shapes_and_unknown_tools_are_recorded(self):
        metric = call(tools(), 'query_metrics', metric='latency_p95_ms')
        odd = deepcopy(metric)
        odd['evidence_id'] = 'f02-odd'
        odd['observations'] = [{'metric': 'x', 'samples': [{'timestamp': END, 'value': 'NaN'}], 'source_id': 's'},
                               {'unexpected': True}, 'text', metric['observations'][0]]
        unknown = {**deepcopy(metric), 'evidence_id': 'f02-unknown', 'tool': 'run_shell'}
        status = {**deepcopy(metric), 'evidence_id': 'f02-status', 'status': 'maybe'}
        run = load_run(run_dict([odd, unknown, status]))
        self.assertEqual(len(run.evidence['f02-odd'].observations), 1)
        self.assertEqual(len([u for u in run.unsupported if u['evidence_id'] == 'f02-odd']), 3)
        self.assertEqual(run.evidence['f02-unknown'].category, 'empty')
        self.assertEqual(run.evidence['f02-status'].category, 'unrecognized_status')


class FactTests(unittest.TestCase):
    def setUp(self):
        self.data = full_run()
        self.facts = extract(load_run(self.data))

    def test_alert_fact_preserves_values_and_reference(self):
        alert = by_type(self.facts, 'alert')[0]
        self.assertEqual((alert.value, alert.details['threshold'], alert.timestamp), (1500, 1000, END))
        self.assertTrue(alert.details['evidence_in_run'])
        detached = extract(load_run(run_dict([])))[0]
        self.assertFalse(detached.details['evidence_in_run'])
        self.assertTrue(detached.limitations)

    def test_metric_fact_values_units_window_and_provenance(self):
        data = run_dict([call(tools({'prometheus': metric_response(('900', '1500', '1200'))}),
                              'query_metrics', metric='latency_p95_ms')])
        fact = by_type(extract(load_run(data)), 'metric_series')[0]
        self.assertEqual((fact.value, fact.unit, fact.timestamp), (1200.0, 'milliseconds', END))
        self.assertEqual((fact.details['min'], fact.details['max'], fact.details['sample_count']), (900.0, 1500.0, 3))
        self.assertEqual(fact.details['window'], {'start': START, 'end': END})
        self.assertEqual(fact.evidence_ids, (data['evidence'][0]['evidence_id'],))
        self.assertTrue(fact.details['source_id'].startswith('promql:'))

    def test_log_trace_and_container_facts(self):
        log = by_type(self.facts, 'log_entry')[0]
        self.assertEqual((log.details['severity'], log.details['trace_id']), ('ERROR', TRACE))
        self.assertIn('context deadline exceeded', log.value)
        self.assertEqual(log.details['source_id'], 'otel-logs-2026-01-02/doc-1')
        sp = by_type(self.facts, 'span')[0]
        self.assertTrue(sp.details['is_error'])
        self.assertEqual((sp.value, sp.unit, sp.details['attributes']), (4000.0, 'ms', {'rpc.grpc.status_code': '4'}))
        state = by_type(self.facts, 'container_state')[0]
        self.assertEqual((state.value, state.details['running']), ('running', True))
        self.assertIn('Collection-time snapshot, not state over the window', state.limitations)
        self.assertEqual([f.value for f in by_type(self.facts, 'container_event')], ['die', 'start'])

    def test_gap_and_link_facts_make_no_causal_claim(self):
        gap = by_type(self.facts, 'evidence_gap')[0]
        self.assertEqual((gap.details['tool'], gap.details['status']), ('deployment_history', 'unavailable'))
        self.assertIsNone(gap.value)
        link = by_type(self.facts, 'log_trace_link')[0]
        self.assertEqual(len(link.evidence_ids), 2)
        self.assertIn('not a causal relation', link.limitations[0])
        unlinked = run_dict([call(tools({'opensearch': logs_response(trace='12' * 16)}), 'search_logs'),
                             call(tools(), 'search_traces')])
        self.assertEqual(by_type(extract(load_run(unlinked)), 'log_trace_link'), [])

    def test_fact_ids_are_stable_and_unique(self):
        again = extract(load_run(deepcopy(self.data)))
        self.assertEqual([f.fact_id for f in self.facts], [f.fact_id for f in again])
        self.assertEqual(len({f.fact_id for f in self.facts}), len(self.facts))

    def test_partial_evidence_limitations_flow_into_facts(self):
        partial = call(tools({'opensearch': logs_response(total=500)}), 'search_logs', limit=1)
        fact = by_type(extract(load_run(run_dict([partial]))), 'log_entry')[0]
        self.assertIn('Log limit reached; more matching documents may exist.', fact.limitations)

    def test_conflicting_observations_are_both_kept(self):
        data = run_dict([call(tools(docker=FakeDocker('exited')), 'container_health'),
                         call(tools(docker=FakeDocker(events=('die',))), 'container_events'),
                         call(tools(), 'container_health')])
        facts = extract(load_run(data))
        self.assertEqual(sorted(f.value for f in by_type(facts, 'container_state')), ['exited', 'running'])
        self.assertEqual(len(by_type(facts, 'container_event')), 1)

    def test_no_invented_facts(self):
        no_data = call(tools({'prometheus': {'status': 'success', 'data': {'resultType': 'matrix', 'result': []}}}),
                       'query_metrics', metric='error_rate')
        facts = extract(load_run(run_dict([no_data])))
        self.assertEqual(sorted(f.type for f in facts), ['alert', 'evidence_gap'])
        ok_span = call(tools({'jaeger': {'result': {'resourceSpans': [{'resource': {'attributes': [
            {'key': 'service.name', 'value': {'stringValue': 'checkout'}}]}, 'scopeSpans': [{'spans': [span(code=0)]}]}]}}}),
            'search_traces')
        sp = by_type(extract(load_run(run_dict([ok_span]))), 'span')[0]
        self.assertFalse(sp.details['is_error'])
        self.assertNotIn('ERROR', sp.description)
        allowed = {e['evidence_id'] for e in self.data['evidence']} | {'f02-detector-only'}
        self.assertTrue(all(set(f.evidence_ids) <= allowed for f in self.facts))


if __name__ == '__main__':
    unittest.main()
