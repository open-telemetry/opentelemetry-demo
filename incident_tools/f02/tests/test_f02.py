"""Synthetic contract fixtures, never live incident evidence."""
import base64
from copy import deepcopy
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from urllib.error import URLError

from incident_tools.f02.boundary import Config, Docker, HTTP, ToolError, timestamp
from incident_tools.f02.tools import ObservabilityTools

START = '2026-01-02T10:00:00Z'
END = '2026-01-02T10:05:00Z'
NOW = datetime(2026, 1, 2, 10, 6, tzinfo=timezone.utc)
TRACE = '1' * 32
SPAN = '2' * 16
CONTAINER = 'a' * 64


def metric_response(value='0.125', when=None):
    return {'status': 'success', 'data': {'resultType': 'matrix', 'result': [
        {'metric': {'service_name': 'checkout'}, 'values': [[when or timestamp(END).timestamp(), value]]}]}}


def log_response(body='upstream timeout', service='checkout', when=END):
    return {'timed_out': False, '_shards': {'failed': 0}, 'hits': {'total': {'value': 1, 'relation': 'eq'}, 'hits': [
        {'_index': 'otel-logs-2026-01-02', '_id': 'fixture-log-1', '_source': {
            'resource': {'service': {'name': service}}, 'observedTimestamp': when,
            'body': body, 'severity': {'text': 'ERROR'}, 'traceId': TRACE, 'spanId': SPAN}}]}}


def traces_response():
    return {'result': {'resourceSpans': [{'resource': {'attributes': [
        {'key': 'service.name', 'value': {'stringValue': 'checkout'}}]}, 'scopeSpans': [{'spans': [{
            'traceId': TRACE, 'spanId': SPAN, 'name': 'POST checkout', 'kind': 2,
            'startTimeUnixNano': str((int(timestamp(END).timestamp()) - 1) * 1000000000),
            'endTimeUnixNano': str((int(timestamp(END).timestamp()) - 1) * 1000000000 + 250000000),
            'status': {'code': 2, 'message': 'password=should-not-be-returned'},
            'attributes': [{'key': 'http.response.status_code', 'value': {'intValue': '503'}},
                           {'key': 'feature_flag.result.variant', 'value': {'stringValue': 'SECRET_ORACLE'}}]
        }]}]}]}}


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.reply()

    def do_POST(self):
        self.reply()

    def reply(self):
        route = urlsplit(self.path)
        length = int(self.headers.get('Content-Length', '0'))
        body = self.rfile.read(length) if length else None
        self.server.requests.append({'method': self.command, 'path': route.path,
                                     'query': parse_qs(route.query), 'body': json.loads(body) if body else None})
        code, value, headers = self.server.responses.get((self.command, route.path), (404, {}, {}))
        raw = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)


class FakeDocker:
    def __init__(self):
        self.commands = []
        self.project = 'opentelemetry-demo'
        self.service = 'checkout'
        self.container = CONTAINER
        self.events = []

    def run(self, args):
        self.commands.append(args)
        if args[0] == 'ps':
            return self.container + '\n' if self.container else ''
        if args[0] == 'inspect':
            return json.dumps({'id': self.container, 'project': self.project, 'service': self.service,
                               'status': 'running', 'running': True, 'exit_code': 0,
                               'started_at': START, 'finished_at': '0001-01-01T00:00:00Z', 'health': None,
                               'env': ['API_KEY=DO_NOT_RETURN']})
        if args[0] == 'events':
            return '\n'.join(json.dumps(e) for e in self.events)
        raise AssertionError('Unexpected command')


class ToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), FixtureHandler)
        cls.server.daemon_threads = True
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.endpoint = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()

    def setUp(self):
        self.server.requests = []
        self.server.responses = {}
        self.config = Config({'origin': 'fixture', 'services': ['checkout', 'payment'],
                              'limits': {'retries': 0},
                              **{key: {'endpoint': self.endpoint} for key in ('prometheus', 'jaeger', 'opensearch')}})
        self.docker = FakeDocker()
        self.tools = ObservabilityTools(self.config, docker=self.docker, clock=lambda: NOW)
        self.args = {'service': 'checkout', 'start': START, 'end': END}

    def reply(self, backend, payload, code=200, headers=None):
        routes = {'prometheus': ('GET', '/api/v1/query_range'), 'jaeger': ('GET', '/jaeger/ui/api/v3/traces'),
                  'opensearch': ('POST', '/otel-logs-*/_search')}
        self.server.responses[routes[backend]] = (code, payload, headers or {})

    def metrics(self, **extra):
        return self.tools.call('query_metrics', {**self.args, 'metric': 'error_rate', **extra})

    def test_schemas_are_callable_and_disallow_additional_properties(self):
        schemas = self.tools.schemas()
        self.assertEqual(len(schemas), 6)
        self.assertEqual({s['function']['name'] for s in schemas}, {'query_metrics', 'search_logs', 'search_traces', 'container_health', 'container_events', 'deployment_history'})
        self.assertTrue(all(s['function']['parameters']['additionalProperties'] is False for s in schemas))

    def test_invalid_requests_never_reach_transports(self):
        cases = [dict(service='not-allowed'), dict(service='checkout"} or vector(1)'),
                 dict(start='2026-01-02T10:00:00'), dict(start=END), dict(end='2026-01-04T10:00:00Z'),
                 dict(limit=True), dict(limit=10001), dict(url='http://evil'), dict(query='vector(1)'),
                 dict(metric='arbitrary'), dict(step_seconds=1), dict(step_seconds=True)]
        for extra in cases:
            with self.subTest(extra=extra):
                self.assertEqual(self.metrics(**extra)['status'], 'invalid_request')
        self.assertEqual(self.tools.call('restart', self.args)['status'], 'invalid_request')
        self.assertEqual(self.server.requests, [])
        self.assertEqual(self.docker.commands, [])

    def test_metric_values_units_scope_and_provenance(self):
        self.reply('prometheus', metric_response())
        result = self.metrics()
        self.assertEqual(result['status'], 'ok')
        row = result['observations'][0]
        self.assertEqual(row['unit'], 'fraction')
        self.assertEqual(row['samples'][0]['value'], 0.125)
        self.assertEqual(row['samples'][0]['raw_value'], '0.125')
        self.assertEqual(result['origin'], 'fixture')
        self.assertTrue(result['evidence_id'].startswith('f02-'))
        self.assertEqual(len(result['provenance']['query_sha256']), 64)
        req = self.server.requests[-1]
        self.assertEqual(req['method'], 'GET')
        self.assertIn('service_name="checkout"', req['query']['query'][0])
        self.assertIn('span_kind="SPAN_KIND_SERVER"', req['query']['query'][0])
        self.assertEqual(req['query']['end'], [END])

    def test_all_allowlisted_metrics_build_bounded_queries(self):
        for metric, unit in [('request_rate', 'requests/second'), ('error_rate', 'fraction'),
                             ('latency_p95_ms', 'milliseconds'), ('service_presence', 'target_info')]:
            with self.subTest(metric=metric):
                self.reply('prometheus', metric_response('5'))
                result = self.metrics(metric=metric)
                self.assertEqual(result['status'], 'ok')
                self.assertEqual(result['observations'][0]['unit'], unit)
                self.assertNotIn('SEL', self.server.requests[-1]['query']['query'][0])

    def test_missing_metrics_are_no_data_not_zero(self):
        self.reply('prometheus', {'status': 'success', 'data': {'resultType': 'matrix', 'result': []}})
        result = self.metrics()
        self.assertEqual(result['status'], 'no_data')
        self.assertEqual(result['observations'], [])
        self.assertIn('provenance', result)

    def test_nonfinite_values_are_not_zero(self):
        for value in ('NaN', '+Inf', '-Inf'):
            with self.subTest(value=value):
                self.reply('prometheus', metric_response(value))
                result = self.metrics()
                self.assertEqual(result['status'], 'no_data')
                self.assertTrue(result['warnings'])
                json.dumps(result, allow_nan=False)

    def test_stale_range_coverage_is_partial(self):
        self.reply('prometheus', metric_response(when=timestamp(START).timestamp()))
        result = self.metrics()
        self.assertEqual(result['status'], 'partial')
        self.assertIn('end of the requested range', result['warnings'][0])

    def test_scope_mismatch_rejected_for_each_backend(self):
        response = metric_response()
        response['data']['result'][0]['metric']['service_name'] = 'other'
        self.reply('prometheus', response)
        self.assertEqual(self.metrics()['error']['code'], 'scope_mismatch')
        self.reply('opensearch', log_response(service='other'))
        self.assertEqual(self.tools.call('search_logs', self.args)['error']['code'], 'scope_mismatch')
        self.docker.project = 'other-project'
        self.assertEqual(self.tools.call('container_health', self.args)['error']['code'], 'scope_mismatch')

    def test_out_of_window_observations_rejected(self):
        self.reply('prometheus', metric_response(when=timestamp(END).timestamp() + 1))
        self.assertEqual(self.metrics()['status'], 'error')
        self.reply('opensearch', log_response(when='2026-01-03T10:00:00Z'))
        self.assertEqual(self.tools.call('search_logs', self.args)['status'], 'error')

    def test_bad_schemas_and_backend_errors_never_become_empty_success(self):
        for value in ({}, [], {'status': 'error', 'error': 'password=SECRET'}, metric_response('not-a-number')):
            with self.subTest(value=value):
                self.reply('prometheus', value)
                result = self.metrics()
                self.assertEqual(result['status'], 'error')
                self.assertNotIn('SECRET', json.dumps(result))
        self.reply('opensearch', {})
        self.assertEqual(self.tools.call('search_logs', self.args)['status'], 'error')
        self.reply('jaeger', {})
        self.assertEqual(self.tools.call('search_traces', self.args)['status'], 'error')

    def test_http_failures_and_invalid_json(self):
        for code in (401, 403, 404, 429, 500, 503):
            with self.subTest(code=code):
                self.reply('prometheus', {'secret': 'DO_NOT_RETURN'}, code)
                result = self.metrics()
                self.assertEqual(result['status'], 'unavailable')
                self.assertEqual(result['error']['code'], 'http_' + str(code))
                self.assertNotIn('DO_NOT_RETURN', json.dumps(result))
        self.reply('prometheus', b'not JSON')
        self.assertEqual(self.metrics()['error']['code'], 'malformed_response')

    def test_redirects_not_followed(self):
        self.reply('prometheus', {}, 302, {'Location': self.endpoint + '/forbidden'})
        self.assertEqual(self.metrics()['status'], 'unavailable')
        self.assertEqual(len(self.server.requests), 1)

    def test_network_failures_are_bounded_and_retry_limited(self):
        self.config.limits['retries'] = 2
        with patch.object(self.tools.http.opener, 'open', side_effect=URLError('token=NEVER_PRINT')) as opened:
            result = self.metrics()
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(opened.call_count, 3)
        self.assertNotIn('NEVER_PRINT', json.dumps(result))

    def test_response_byte_budget(self):
        self.config.limits['max_response_bytes'] = 30
        self.reply('prometheus', metric_response())
        self.assertEqual(self.metrics()['error']['code'], 'response_too_large')

    def test_series_and_sample_limits(self):
        response = metric_response()
        response['data']['result'] *= 2
        self.reply('prometheus', response)
        result = self.metrics(limit=1)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(len(result['observations']), 1)
        self.config.limits['max_samples'] = 2
        self.assertEqual(self.metrics()['status'], 'invalid_request')

    def test_logs_use_read_only_post_with_exact_scope(self):
        self.reply('opensearch', log_response())
        result = self.tools.call('search_logs', self.args)
        self.assertEqual(result['status'], 'ok')
        row = result['observations'][0]
        self.assertEqual(row['source_id'], 'otel-logs-2026-01-02/fixture-log-1')
        self.assertEqual(row['traceId'], TRACE)
        req = self.server.requests[-1]
        self.assertEqual(req['method'], 'POST')
        self.assertEqual(req['body']['size'], 50)
        self.assertEqual(req['body']['query']['bool']['filter'][0], {'match_phrase': {'resource.service.name': 'checkout'}})
        self.assertEqual(req['body']['query']['bool']['filter'][1]['range']['observedTimestamp']['gte'], START)

    def test_flattened_log_fields_supported(self):
        response = log_response()
        src = response['hits']['hits'][0]['_source']
        src.pop('resource')
        src['resource.service.name'] = 'checkout'
        src['severity.text'] = 'ERROR'
        self.reply('opensearch', response)
        self.assertEqual(self.tools.call('search_logs', self.args)['status'], 'ok')

    def test_credential_and_pii_redaction(self):
        self.config.secrets.append('FIXTURE_CONFIGURED_SECRET')
        body = 'password=FIXTURE_PASSWORD api_key="FIXTURE_KEY" Bearer FIXTURE_TOKEN email=person@example.test FIXTURE_CONFIGURED_SECRET https://user:pass@host/path'
        self.reply('opensearch', log_response(body))
        text = json.dumps(self.tools.call('search_logs', self.args))
        for secret in ('FIXTURE_PASSWORD', 'FIXTURE_KEY', 'FIXTURE_TOKEN', 'person@example.test', 'FIXTURE_CONFIGURED_SECRET', 'user:pass'):
            self.assertNotIn(secret, text)
        self.assertIn('REDACTED', text)

    def test_structured_log_credentials_redacted(self):
        self.reply('opensearch', log_response({'api_key': 'STRUCTURED_SECRET', 'message': 'failed'}))
        self.assertNotIn('STRUCTURED_SECRET', json.dumps(self.tools.call('search_logs', self.args)))

    def test_fault_oracle_logs_are_suppressed(self):
        for body in ('feature_flag variant=broken', 'flagd evaluation result enabled', 'flag_key=paymentFail'):
            self.reply('opensearch', log_response(body))
            result = self.tools.call('search_logs', self.args)
            self.assertEqual(result['status'], 'no_data')
            self.assertTrue(result['warnings'])

    def test_log_partial_shards_and_truncation(self):
        response = log_response()
        response['_shards']['failed'] = 1
        response['timed_out'] = True
        response['hits']['total']['value'] = 100
        self.reply('opensearch', response)
        result = self.tools.call('search_logs', {**self.args, 'limit': 1})
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(len(result['warnings']), 2)

    def test_trace_ids_duration_and_selected_attributes(self):
        self.reply('jaeger', traces_response())
        result = self.tools.call('search_traces', self.args)
        self.assertEqual(result['status'], 'ok')
        row = result['observations'][0]
        self.assertEqual(row['trace_id'], TRACE)
        self.assertEqual(row['span_id'], SPAN)
        self.assertEqual(row['duration_ms'], 250.0)
        self.assertEqual(row['status_code'], 2)
        self.assertEqual(row['attributes']['http.response.status_code'], '503')
        text = json.dumps(result)
        self.assertNotIn('SECRET_ORACLE', text)
        self.assertNotIn('should-not-be-returned', text)
        self.assertEqual(self.server.requests[-1]['query']['query.service_name'], ['checkout'])

    def test_base64_otlp_ids_and_parent_supported(self):
        response = traces_response()
        span = response['result']['resourceSpans'][0]['scopeSpans'][0]['spans'][0]
        span['traceId'] = base64.b64encode(bytes.fromhex(TRACE)).decode()
        span['spanId'] = base64.b64encode(bytes.fromhex(SPAN)).decode()
        span['parentSpanId'] = base64.b64encode(bytes.fromhex('3' * 16)).decode()
        self.reply('jaeger', response)
        result = self.tools.call('search_traces', self.args)
        self.assertEqual(result['observations'][0]['trace_id'], TRACE)
        self.assertEqual(result['observations'][0]['parent_span_id'], '3' * 16)

    def test_trace_filter_is_bounded_and_honest(self):
        self.reply('jaeger', traces_response())
        result = self.tools.call('search_traces', {**self.args, 'trace_id': 'f' * 32})
        self.assertEqual(result['status'], 'no_data')
        self.assertIn('absence is not proof', result['warnings'][0])
        self.assertEqual(self.tools.call('search_traces', {**self.args, 'trace_id': '../evil'})['status'], 'invalid_request')

    def test_cross_service_spans_and_bad_span_ids(self):
        response = traces_response()
        other = deepcopy(response['result']['resourceSpans'][0])
        other['resource']['attributes'][0]['value']['stringValue'] = 'payment'
        response['result']['resourceSpans'].append(other)
        self.reply('jaeger', response)
        self.assertEqual(len(self.tools.call('search_traces', self.args)['observations']), 1)
        response['result']['resourceSpans'][0]['scopeSpans'][0]['spans'][0]['spanId'] = 'bad'
        self.reply('jaeger', response)
        self.assertEqual(self.tools.call('search_traces', self.args)['status'], 'error')

    def test_empty_jaeger_result_is_not_malformed(self):
        self.reply('jaeger', {'result': {'resourceSpans': None}})
        self.assertEqual(self.tools.call('search_traces', self.args)['status'], 'no_data')

    def test_container_state_is_current_scoped_and_not_env(self):
        result = self.tools.call('container_health', self.args)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['provenance']['temporal_semantics'], 'current_snapshot')
        self.assertEqual(result['observations'][0]['container_id'], CONTAINER)
        self.assertNotIn('DO_NOT_RETURN', json.dumps(result))
        command = self.docker.commands[0]
        self.assertIn('label=com.docker.compose.project=opentelemetry-demo', command)
        self.assertIn('label=com.docker.compose.service=checkout', command)
        self.assertEqual([cmd[0] for cmd in self.docker.commands], ['ps', 'inspect'])

    def test_docker_injected_id_is_not_executed(self):
        self.docker.container = '--format=evil'
        result = self.tools.call('container_health', self.args)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(len(self.docker.commands), 1)

    def test_empty_container_inventory_does_not_invent_health(self):
        self.docker.container = ''
        result = self.tools.call('container_health', self.args)
        self.assertEqual(result['status'], 'no_data')
        self.assertEqual(result['observations'], [])

    def test_docker_transport_forbids_mutation_and_uses_no_shell(self):
        transport = Docker(self.config)
        for args in (['restart', 'checkout'], ['exec', CONTAINER, 'bash'], ['stop', CONTAINER]):
            with self.assertRaises(ToolError):
                transport.run(args)
        with patch('incident_tools.f02.boundary.subprocess.Popen') as popen:
            popen.return_value.returncode = 0
            self.assertEqual(transport.run(['ps', '-a']), '')
            self.assertFalse(popen.call_args.kwargs['shell'])
            self.assertEqual(popen.call_args.args[0], ['docker', 'ps', '-a'])
        self.config.data['docker'] = {'transport': 'wsl', 'distro': 'Ubuntu'}
        with patch('incident_tools.f02.boundary.subprocess.Popen') as popen:
            popen.return_value.returncode = 0
            transport.run(['ps', '-a'])
            self.assertEqual(popen.call_args.args[0][:5], ['wsl', '-d', 'Ubuntu', '--', 'docker'])

    def test_docker_timeout_and_daemon_failure(self):
        transport = Docker(self.config)
        with patch('incident_tools.f02.boundary.subprocess.Popen') as popen:
            popen.return_value.wait.side_effect = [subprocess.TimeoutExpired(['docker'], 10), None]
            with self.assertRaises(ToolError) as caught:
                transport.run(['ps'])
            self.assertEqual(caught.exception.code, 'docker_timeout')
            popen.return_value.kill.assert_called_once()
        with patch('incident_tools.f02.boundary.subprocess.Popen') as popen:
            popen.return_value.returncode = 1
            with self.assertRaises(ToolError) as caught:
                transport.run(['ps'])
            self.assertEqual(caught.exception.code, 'docker_failed')

    def test_events_are_not_deployments_and_use_past_window(self):
        self.docker.events = [{'Actor': {'ID': CONTAINER, 'Attributes': {'com.docker.compose.project': 'opentelemetry-demo', 'com.docker.compose.service': 'checkout'}},
                               'Action': 'start', 'timeNano': str(int(timestamp(END).timestamp()) * 1000000000)}]
        result = self.tools.call('container_events', self.args)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['observations'][0]['action'], 'start')
        self.assertTrue(any('not establish deployments' in w for w in result['warnings']))
        self.assertIn('--until', self.docker.commands[-1])
        self.assertEqual(self.tools.call('container_events', {**self.args, 'end': '2026-01-02T10:10:00Z'})['status'], 'invalid_request')

    def test_missing_deployment_feed_is_unavailable(self):
        result = self.tools.call('deployment_history', self.args)
        self.assertEqual(result['status'], 'unavailable')
        self.assertIn('not deployment evidence', result['error']['message'])
        self.assertEqual(self.docker.commands, [])

    def test_deployment_audit_reads_only_operator_selected_feed(self):
        with tempfile.TemporaryDirectory() as folder:
            audit = Path(folder) / 'fixture-deployments.jsonl'
            audit.write_text(json.dumps({'id': 'fixture-deploy-1', 'service': 'checkout', 'timestamp': END,
                                         'revision': 'fixture-sha', 'source': 'fixture://test-pipeline/run1', 'token': 'OMIT_ME'}) + '\n', encoding='utf-8')
            self.config.data['deployments'] = {'audit_file': str(audit)}
            before = audit.read_bytes()
            result = self.tools.call('deployment_history', self.args)
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(result['observations'][0]['source_id'], 'deployment-audit:fixture-deploy-1')
            self.assertNotIn('OMIT_ME', json.dumps(result))
            self.assertEqual(audit.read_bytes(), before)
            audit.write_text('{bad json}\n', encoding='utf-8')
            self.assertEqual(self.tools.call('deployment_history', self.args)['status'], 'error')

    def test_invalid_operator_configuration(self):
        for extra in ({'services': ['bad/service']}, {'prometheus': {'endpoint': 'http://user:pass@host'}},
                      {'opensearch': {'index': '../_delete'}}, {'docker': {'transport': 'shell'}},
                      {'limits': {'retries': 100}}, {'limits': {'max_items': True}}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                Config({'services': ['checkout'], **extra})
        with patch.dict(os.environ, {'F02_TEST_TOKEN': 'synthetic-fixture-secret'}):
            with self.assertRaises(ValueError):
                Config({'services': ['checkout'], 'prometheus': {'endpoint': 'http://host', 'bearer_token_env': 'F02_TEST_TOKEN'}})
            config = Config({'services': ['checkout'], 'prometheus': {'endpoint': 'https://host', 'bearer_token_env': 'F02_TEST_TOKEN'}})
            self.assertNotIn('synthetic-fixture-secret', config.clean('synthetic-fixture-secret'))


    def test_empty_jaeger_proto_omits_repeated_field(self):
        self.reply('jaeger', {'result': {}})
        self.assertEqual(self.tools.call('search_traces', self.args)['status'], 'no_data')

    def test_keyword_log_query_keeps_source_field_separate(self):
        self.config.data['opensearch']['service_query_field'] = 'resource.service.name.keyword'
        self.reply('opensearch', log_response())
        result = self.tools.call('search_logs', self.args)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(self.server.requests[-1]['body']['query']['bool']['filter'][0],
                         {'match_phrase': {'resource.service.name.keyword': 'checkout'}})

    def test_text_json_credentials_and_truncation(self):
        self.reply('opensearch', log_response('{"password": "QUOTED_SECRET", "message": "failure"}'))
        result = self.tools.call('search_logs', self.args)
        self.assertNotIn('QUOTED_SECRET', json.dumps(result))
        self.reply('opensearch', log_response('x' * 5000))
        result = self.tools.call('search_logs', self.args)
        self.assertEqual(result['status'], 'partial')
        self.assertTrue(result['observations'][0]['body_truncated'])
        self.assertEqual(len(result['observations'][0]['body']), 4096)

    def test_nonstandard_json_numbers_rejected(self):
        self.reply('prometheus', b'{"status":"success","data":{"resultType":"matrix","result":NaN}}')
        result = self.metrics()
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error']['code'], 'malformed_response')

    def test_valid_stdio_call_returns_source_ids(self):
        self.reply('opensearch', log_response())
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'fixture.toml'
            config.write_text('origin = "fixture"\nservices = ["checkout"]\n[opensearch]\nendpoint = "' + self.endpoint + '"\n', encoding='utf-8')
            command = [sys.executable, '-B', '-m', 'incident_tools.f02', '--config', str(config), 'serve']
            completed = subprocess.run(command, input=json.dumps({'tool': 'search_logs', 'arguments': self.args}) + '\n',
                                       capture_output=True, text=True, timeout=10)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(result['origin'], 'fixture')
            self.assertEqual(result['observations'][0]['source_id'], 'otel-logs-2026-01-02/fixture-log-1')


    def test_jaeger_streamed_chunks_and_empty_stream(self):
        first, second = traces_response(), traces_response()
        second['result']['resourceSpans'][0]['scopeSpans'][0]['spans'][0]['spanId'] = '3' * 16
        payload = (json.dumps(first) + '\n' + json.dumps(second) + '\n').encode()
        self.reply('jaeger', payload)
        result = self.tools.call('search_traces', self.args)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(len(result['observations']), 2)
        self.reply('jaeger', b'')
        self.assertEqual(self.tools.call('search_traces', self.args)['status'], 'no_data')

    def test_jaeger_late_stream_errors_do_not_become_success(self):
        payload = (json.dumps(traces_response()) + '\n' + json.dumps({'error': {'message': 'token=STREAM_SECRET'}}) + '\n').encode()
        self.reply('jaeger', payload)
        result = self.tools.call('search_traces', self.args)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error']['code'], 'query_failed')
        self.assertEqual(result['observations'], [])
        self.assertNotIn('STREAM_SECRET', json.dumps(result))

    def test_trace_end_is_exclusive(self):
        response = traces_response()
        span = response['result']['resourceSpans'][0]['scopeSpans'][0]['spans'][0]
        span['startTimeUnixNano'] = span['endTimeUnixNano'] = str(int(timestamp(END).timestamp()) * 1000000000)
        self.reply('jaeger', response)
        self.assertEqual(self.tools.call('search_traces', self.args)['status'], 'no_data')


class CLITests(unittest.TestCase):
    def test_stdio_dispatch_rejects_mutation_and_bad_envelopes(self):
        result = subprocess.run([sys.executable, '-B', '-m', 'incident_tools.f02', '--config', 'incident_tools/f02/operator.example.toml', 'serve'],
            input='not json\n' + json.dumps({'tool': 'restart', 'arguments': {'service': 'checkout', 'start': START, 'end': END}}) + '\n',
            capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([r['status'] for r in rows], ['invalid_request', 'invalid_request'])

    def test_cli_creates_evidence_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'evidence.json'
            command = [sys.executable, '-B', '-m', 'incident_tools.f02', '--config', 'incident_tools/f02/operator.example.toml', 'call', 'deployment_history',
                       '--service', 'checkout', '--start', START, '--end', END, '--output', str(output)]
            first = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(first.returncode, 1)
            before = output.read_bytes()
            self.assertEqual(json.loads(before)['status'], 'unavailable')
            second = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(second.returncode, 2)
            self.assertEqual(output.read_bytes(), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
