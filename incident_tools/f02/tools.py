"""Agent-callable observations. No arbitrary URLs, queries, commands, or writes."""
import base64
import hashlib
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re

from .boundary import Config, Docker, HTTP, ToolError, digest, finite, iso, timestamp, utc_now


METRICS = {
    'request_rate': ('requests/second', 'sum by (service_name) (rate(traces_span_metrics_calls_total{SEL}[2m]))'),
    'error_rate': ('fraction', '(sum by (service_name) (rate(traces_span_metrics_calls_total{SEL,status_code="STATUS_CODE_ERROR"}[2m]))) / (sum by (service_name) (rate(traces_span_metrics_calls_total{SEL}[2m])))'),
    'latency_p95_ms': ('milliseconds', 'histogram_quantile(0.95, sum by (service_name, le) (rate(traces_span_metrics_duration_milliseconds_bucket{SEL}[2m])))'),
    'service_presence': ('target_info', 'target_info{SEL}'),
}
DESCRIPTIONS = {
    'query_metrics': 'Read bounded Prometheus series using an allowlisted metric; missing data is not health.',
    'search_logs': 'Read scoped OpenSearch log excerpts with document IDs; redacts common secrets and omits flag-resolution records.',
    'search_traces': 'Read Jaeger v3 OTLP spans for one service and time window, optionally filter an exact trace ID.',
    'container_health': 'Read current scoped Docker state. This is a collection-time snapshot, not historical health.',
    'deployment_history': 'Read an operator-configured deployment JSONL audit feed, or report unavailable.',
    'container_events': 'Read bounded Docker lifecycle events. These are not deployment history.',
}


def get_field(data, field):
    if field in data:
        return data[field]
    parts = field.split('.')
    for i in range(1, len(parts) + 1):
        prefix = '.'.join(parts[:i])
        if prefix in data:
            child = data[prefix]
            if i == len(parts):
                return child
            if isinstance(child, dict):
                return get_field(child, '.'.join(parts[i:]))
    return None


def otlp_id(value, size):
    if not isinstance(value, str):
        raise ValueError('Missing trace/span ID')
    # OTLP JSON uses hex; accept the base64 protobuf-JSON variant as well.
    if re.fullmatch('[0-9a-fA-F]{' + str(size * 2) + '}', value):
        return value.lower()
    raw = base64.b64decode(value, validate=True)
    if len(raw) != size:
        raise ValueError('Invalid trace/span ID')
    return raw.hex()


def otlp_attributes(items):
    result = {}
    for item in items:
        value = item.get('value', {})
        if not isinstance(value, dict):
            continue
        for kind in ('stringValue', 'intValue', 'boolValue', 'doubleValue'):
            if kind in value:
                result[item['key']] = value[kind]
                break
    return result


class ObservabilityTools:
    def __init__(self, config, http=None, docker=None, clock=utc_now):
        self.config = config if isinstance(config, Config) else Config.load(config)
        self.http = http or HTTP(self.config)
        self.docker = docker or Docker(self.config)
        self.clock = clock

    def schemas(self):
        props = {
            'service': {'type': 'string', 'enum': self.config.services},
            'start': {'type': 'string', 'format': 'date-time'},
            'end': {'type': 'string', 'format': 'date-time'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': self.config.limits['max_items']},
        }
        result = []
        for name, description in DESCRIPTIONS.items():
            fields = dict(props)
            required = ['service', 'start', 'end']
            if name == 'query_metrics':
                fields['metric'] = {'type': 'string', 'enum': list(METRICS)}
                fields['step_seconds'] = {'type': 'integer', 'minimum': self.config.limits['min_step_seconds'], 'maximum': 3600}
                required.append('metric')
            if name == 'search_traces':
                fields['trace_id'] = {'type': 'string', 'minLength': 32, 'maxLength': 32}
            result.append({'type': 'function', 'function': {'name': name, 'description': description,
                'parameters': {'type': 'object', 'properties': fields, 'required': required, 'additionalProperties': False}}})
        return result

    def _validate(self, tool, args):
        if tool not in DESCRIPTIONS or not isinstance(args, dict):
            raise ValueError('Unknown tool or invalid argument object')
        schema = next(x['function']['parameters'] for x in self.schemas() if x['function']['name'] == tool)
        if set(args) - set(schema['properties']) or not set(schema['required']) <= set(args):
            raise ValueError('Missing or unsupported argument')
        if args['service'] not in self.config.services:
            raise ValueError('Service is outside the configured allowlist')
        start, end = timestamp(args['start']), timestamp(args['end'])
        if not 0 < (end - start).total_seconds() <= self.config.limits['max_window_seconds']:
            raise ValueError('Invalid or excessive time window')
        limit = args.get('limit', min(50, self.config.limits['max_items']))
        if type(limit) is not int or not 1 <= limit <= self.config.limits['max_items']:
            raise ValueError('Invalid result limit')
        args = {**args, 'start': iso(start), 'end': iso(end), 'limit': limit}
        if tool == 'query_metrics':
            if args['metric'] not in METRICS:
                raise ValueError('Unsupported metric')
            step = args.get('step_seconds', max(30, self.config.limits['min_step_seconds']))
            if type(step) is not int or not self.config.limits['min_step_seconds'] <= step <= 3600:
                raise ValueError('Invalid metric step')
            if (int((end - start).total_seconds() / step) + 1) > self.config.limits['max_samples']:
                raise ValueError('Metric range exceeds sample budget')
            args['step_seconds'] = step
        if tool == 'search_traces' and 'trace_id' in args:
            # Model-selected trace IDs must be exactly 32 hex characters.
            if not isinstance(args['trace_id'], str) or not re.fullmatch(r'[0-9a-fA-F]{32}', args['trace_id']):
                raise ValueError('trace_id must contain 32 hex characters')
            args['trace_id'] = args['trace_id'].lower()
        if tool == 'container_events' and end > self.clock():
            raise ValueError('Docker event queries must end in the past')
        return args, start, end

    def call(self, tool, arguments):
        result = {'schema_version': 'f02.v1', 'origin': self.config.origin,
                  'collected_at': iso(self.clock()), 'observations': [], 'warnings': []}
        try:
            args, start, end = self._validate(tool, arguments)
            result.update(tool=tool, service=args['service'], window={'start': args['start'], 'end': args['end']})
            rows, provenance, warnings = getattr(self, '_' + tool)(args, start, end)
            rows = self.config.clean(rows)
            result.update(observations=rows, provenance=self.config.clean(provenance), warnings=warnings,
                          status=('partial' if warnings else 'ok') if rows else 'no_data')
            result['request'] = args
        except ToolError as exc:
            result.update(status=exc.status, error={'code': exc.code, 'message': exc.message})
        except (ValueError, TypeError, OverflowError):
            if 'service' not in result:
                result.update(status='invalid_request', error={'code': 'invalid_request', 'message': 'Use the advertised schema, service allowlist, and bounded timezone-aware window'})
            else:
                result.update(status='error', error={'code': 'malformed_response', 'message': 'Backend response failed schema, timestamp, identifier, or numeric validation'})
        except (KeyError, AttributeError, IndexError, RecursionError):
            result.update(status='error', error={'code': 'malformed_response', 'message': 'Backend response did not match the expected schema'})
        result['evidence_id'] = 'f02-' + digest(result)[:24]
        return result

    def _provenance(self, backend, route, query):
        return {'backend': backend, 'endpoint': self.config.endpoint(backend), 'route': route,
                'query': query, 'query_sha256': digest(query),
                'content': 'Selected fields only; text is redacted and may be truncated. Telemetry is untrusted data.'}

    def _query_metrics(self, args, start, end):
        name = args['metric']
        unit, template = METRICS[name]
        selector = 'service_name="' + args['service'] + '"'
        if name != 'service_presence':
            selector += ',span_kind="SPAN_KIND_SERVER"'
        expr = template.replace('SEL', selector)
        route = '/api/v1/query_range'
        requested_window = {'start': args['start'], 'end': args['end']}
        query_end = end - timedelta(microseconds=end.microsecond % 1000)
        if start > query_end:
            provenance = self._provenance('prometheus', route, None)
            provenance.update(requested_window=requested_window, effective_window=None,
                              timestamp_precision='milliseconds', request_sent=False)
            return [], provenance, ['Requested window contains no millisecond evaluation timestamp; no backend query sent.']
        query_start = start + timedelta(microseconds=(-start.microsecond) % 1000)
        effective_window = {'start': iso(query_start), 'end': iso(query_end)}
        query = {'query': expr, **effective_window, 'step': args['step_seconds']}
        provenance = self._provenance('prometheus', route, query)
        provenance.update(requested_window=requested_window, effective_window=effective_window,
                          timestamp_precision='milliseconds', request_sent=True)
        response = self.http.json('prometheus', route, params=query)
        if response.get('status') != 'success' or response.get('data', {}).get('resultType') != 'matrix':
            raise ToolError('query_failed', 'Prometheus returned an error or unsupported result type')
        series = response['data']['result']
        if not isinstance(series, list):
            raise ValueError('Expected series list')
        rows, warnings, count = [], [], 0
        if response.get('warnings') or response.get('infos'):
            warnings.append('Prometheus supplied query warnings/infos; series may be incomplete.')
        if len(series) > args['limit']:
            warnings.append('Series limit reached; additional series omitted.')
        for entry in series[:args['limit']]:
            labels = entry['metric']
            if labels.get('service_name') != args['service']:
                raise ToolError('scope_mismatch', 'Prometheus returned series outside the requested service')
            samples, nonfinite = [], False
            for pair in entry['values']:
                if count >= self.config.limits['max_samples']:
                    warnings.append('Sample budget reached; additional samples omitted.')
                    break
                count += 1
                when = finite(pair[0])
                if not start.timestamp() <= when <= end.timestamp():
                    raise ValueError('Out-of-window metric sample')
                if not query_start.timestamp() <= when <= query_end.timestamp():
                    raise ValueError('Metric sample outside effective query window')
                try:
                    value = finite(pair[1])
                except ValueError:
                    if str(pair[1]) not in ('NaN', '+Inf', '-Inf', 'Inf'):
                        raise
                    nonfinite = True
                    continue
                samples.append({'timestamp': iso(datetime.fromtimestamp(when, timezone.utc)), 'value': value, 'raw_value': str(pair[1])})
            if nonfinite:
                warnings.append('Non-finite metric samples omitted; undefined values are not zero or healthy.')
            if samples:
                if end.timestamp() - timestamp(samples[-1]['timestamp']).timestamp() > max(120, 2 * args['step_seconds']):
                    warnings.append('Series does not cover the end of the requested range.')
                rows.append({'metric': name, 'unit': unit, 'labels': {k: v for k, v in labels.items() if k in ('service_name', 'status_code', 'span_kind', 'le', '__name__', 'job', 'instance')},
                             'samples': samples, 'source_id': 'promql:' + digest({'query': expr, 'labels': labels}),
                             'temporal_semantics': 'Prometheus evaluation times; underlying sample freshness is not independently verified'})
        return rows, provenance, list(dict.fromkeys(warnings))

    def _search_logs(self, args, start, end):
        cfg = self.config.section('opensearch')
        service_field = cfg.get('service_field', 'resource.service.name')
        time_field = cfg.get('time_field', 'observedTimestamp')
        query = {'size': args['limit'], 'track_total_hits': True,
                 'sort': [{time_field: 'asc'}],
                 '_source': [service_field, time_field, 'body', 'severity.text', 'traceId', 'spanId'],
                 'query': {'bool': {'filter': [
                     {'match_phrase': {cfg.get('service_query_field', service_field): args['service']}},
                     {'range': {time_field: {'gte': args['start'], 'lte': args['end']}}}]}}}
        route = '/' + cfg.get('index', 'otel-logs-*') + '/_search'
        response = self.http.json('opensearch', route, body=query)
        rows, warnings = [], []
        if response.get('timed_out') or response.get('_shards', {}).get('failed', 0):
            warnings.append('OpenSearch timed out or failed shards; results may be incomplete.')
        hits = response['hits']['hits']
        if not isinstance(hits, list):
            raise ValueError('Expected hits list')
        total = response['hits'].get('total', len(hits))
        total_value = total.get('value', 0) if isinstance(total, dict) else total
        if total_value > args['limit'] or len(hits) > args['limit'] or (isinstance(total, dict) and total.get('relation') == 'gte'):
            warnings.append('Log limit reached; more matching documents may exist.')
        for hit in hits[:args['limit']]:
            source = hit['_source']
            if get_field(source, service_field) != args['service']:
                raise ToolError('scope_mismatch', 'Log search returned a different service')
            when = timestamp(get_field(source, time_field))
            if not start <= when <= end:
                raise ValueError('Out-of-window log')
            body = get_field(source, 'body')
            body = body if isinstance(body, str) else json.dumps(self.config.clean(body), sort_keys=True)
            # Omit feature-flag resolution records rather than exposing the injected-fault oracle.
            if re.search(r'(?i)feature[_. -]?flag|flagd|flag[_ .-]?(?:key|value|variant)|(?:evaluation|evaluated)[_ .-]?(?:reason|flag)', body):
                warnings.append('Feature-flag resolution records omitted by evidence policy.')
                continue
            row = {'timestamp': iso(when), 'service': args['service'], 'body': body,
                   'severity': get_field(source, 'severity.text'), 'body_truncated': len(body) > 4096,
                   'source_id': str(hit['_index']) + '/' + str(hit['_id'])}
            for key, size in (('traceId', 16), ('spanId', 8)):
                if source.get(key):
                    row[key] = otlp_id(source[key], size)
            if row['body_truncated']:
                warnings.append('Log text was truncated to 4096 characters; use the document ID for the original.')
            rows.append(row)
        return rows, self._provenance('opensearch', route, query), list(dict.fromkeys(warnings))

    def _search_traces(self, args, start, end):
        route = '/jaeger/ui/api/v3/traces'
        query = {'query.service_name': args['service'], 'query.num_traces': args['limit'],
                 'query.start_time_min': args['start'], 'query.start_time_max': args['end']}
        response = self.http.json('jaeger', route, params=query)
        if response.get('error'):
            raise ToolError('query_failed', 'Jaeger returned a query error')
        resources = response['result'].get('resourceSpans', [])
        if resources is None:
            resources = []
        rows, warnings, trace_ids = [], [], set()
        for resource in resources:
            attrs = otlp_attributes(resource.get('resource', {}).get('attributes', []))
            if attrs.get('service.name') != args['service']:
                continue
            for scope in resource.get('scopeSpans', []):
                for span in scope.get('spans', []):
                    trace_id, span_id = otlp_id(span['traceId'], 16), otlp_id(span['spanId'], 8)
                    trace_ids.add(trace_id)
                    if args.get('trace_id') and args['trace_id'] != trace_id:
                        continue
                    begin, finish = int(span['startTimeUnixNano']), int(span['endTimeUnixNano'])
                    if finish < begin:
                        raise ValueError('Negative span duration')
                    when = datetime.fromtimestamp(begin / 1e9, timezone.utc)
                    if not start <= when < end:
                        continue
                    if len(rows) >= args['limit']:
                        warnings.append('Span limit reached; additional spans omitted.')
                        continue
                    attributes = otlp_attributes(span.get('attributes', []))
                    allowed = ('error.type', 'exception.type', 'http.response.status_code', 'rpc.grpc.status_code', 'db.system', 'server.address')
                    status = span.get('status', {})
                    rows.append({'timestamp': iso(when), 'start_time_unix_nano': str(begin),
                                 'end_time_unix_nano': str(finish), 'duration_ms': (finish - begin) / 1e6,
                                 'service': args['service'], 'trace_id': trace_id, 'span_id': span_id,
                                 'parent_span_id': otlp_id(span['parentSpanId'], 8) if span.get('parentSpanId') else None,
                                 'name': str(span.get('name', '')), 'kind': span.get('kind'),
                                 'status_code': status.get('code', 0),
                                 'attributes': {k: v for k, v in attributes.items() if k in allowed},
                                 'source_id': 'jaeger:' + trace_id + '/' + span_id})
        if len(trace_ids) >= args['limit']:
            warnings.append('Trace search limit reached; additional traces may exist.')
        if args.get('trace_id'):
            warnings.append('Trace-ID filtering applies to this bounded service search; absence is not proof that the trace does not exist.')
        return rows, self._provenance('jaeger', route, query), list(dict.fromkeys(warnings))

    def _docker_scope(self, args):
        project = self.config.section('docker').get('project', 'opentelemetry-demo')
        filters = ['--filter', 'label=com.docker.compose.project=' + project,
                   '--filter', 'label=com.docker.compose.service=' + args['service']]
        return project, filters

    def _container_health(self, args, start, end):
        project, filters = self._docker_scope(args)
        ids = self.docker.run(['ps', '-a', '--no-trunc', '--format', '{{.ID}}', *filters]).splitlines()
        rows, warnings = [], ['Health is a current snapshot at collection time, not historical state within the requested window.']
        if len(ids) > args['limit']:
            warnings.append('Container limit reached; additional containers omitted.')
        template = '{"id":{{json .Id}},"project":{{json (index .Config.Labels "com.docker.compose.project")}},"service":{{json (index .Config.Labels "com.docker.compose.service")}},"status":{{json .State.Status}},"running":{{json .State.Running}},"exit_code":{{json .State.ExitCode}},"started_at":{{json .State.StartedAt}},"finished_at":{{json .State.FinishedAt}},"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}}}'
        for container in ids[:args['limit']]:
            # Full Docker IDs are validated before becoming subprocess arguments.
            if not re.fullmatch(r'[0-9a-f]{64}', container):
                raise ValueError('Unexpected container identifier')
            state = json.loads(self.docker.run(['inspect', '--format', template, container]))
            if state['project'] != project or state['service'] != args['service'] or state['id'] != container:
                raise ToolError('scope_mismatch', 'Container did not match the configured Compose project/service')
            if type(state['running']) is not bool or type(state['exit_code']) is not int:
                raise ValueError('Invalid container state')
            rows.append({'source_id': 'docker:' + container, 'container_id': container,
                         'service': args['service'], 'observed_at': iso(self.clock()),
                         **{key: state[key] for key in ('status', 'running', 'exit_code', 'started_at', 'finished_at', 'health')}})
        return rows, {'backend': 'docker', 'project': project, 'commands': ['ps (scoped)', 'inspect (selected state only)'],
                      'temporal_semantics': 'current_snapshot'}, warnings

    def _container_events(self, args, start, end):
        project, filters = self._docker_scope(args)
        output = self.docker.run(['events', '--since', args['start'], '--until', args['end'],
                                  '--filter', 'type=container', *filters, '--format', '{{json .}}'])
        rows, warnings = [], ['Docker retains a bounded recent event buffer; lifecycle events do not establish deployments or complete history.']
        lines = output.splitlines()
        if len(lines) > args['limit']:
            warnings.append('Event limit reached; additional events omitted.')
        for line in lines[:args['limit']]:
            event = json.loads(line)
            attrs = event['Actor']['Attributes']
            if attrs.get('com.docker.compose.project') != project or attrs.get('com.docker.compose.service') != args['service']:
                raise ToolError('scope_mismatch', 'Container event is outside the configured project/service')
            when = finite(event['timeNano']) / 1e9
            if not start.timestamp() <= when <= end.timestamp():
                raise ValueError('Out-of-window container event')
            rows.append({'timestamp': iso(datetime.fromtimestamp(when, timezone.utc)), 'service': args['service'],
                         'container_id': event['Actor']['ID'], 'action': event['Action'],
                         'source_id': 'docker-event:' + event['Actor']['ID'] + ':' + str(event['timeNano']) + ':' + event['Action']})
        return rows, {'backend': 'docker', 'project': project, 'since': args['start'], 'until': args['end'],
                      'commands': ['events (scoped, finite window)']}, warnings

    def _deployment_history(self, args, start, end):
        configured = self.config.section('deployments').get('audit_file')
        if not configured:
            raise ToolError('not_configured', 'No deployment audit source is configured. Docker events and Git commits are not deployment evidence.', 'unavailable')
        file = Path(configured)
        if not file.is_absolute():
            file = self.config.base_dir / file
        try:
            with file.open('rb') as stream:
                data = stream.read(self.config.limits['max_response_bytes'] + 1)
        except OSError:
            raise ToolError('audit_unavailable', 'Configured deployment audit file cannot be read', 'unavailable') from None
        if len(data) > self.config.limits['max_response_bytes']:
            raise ToolError('response_too_large', 'Deployment audit file exceeds byte budget')
        rows, warnings = [], ['Deployment evidence is operator-supplied; the tool cannot establish audit completeness or authenticity.']
        for number, line in enumerate(data.decode('utf-8').splitlines(), 1):
            if not line.strip():
                continue
            record = json.loads(line)
            if record['service'] != args['service']:
                continue
            when = timestamp(record['timestamp'])
            if start <= when <= end:
                if len(rows) >= args['limit']:
                    warnings.append('Deployment result limit reached; additional records omitted.')
                    continue
                if not all(isinstance(record[key], str) and record[key] for key in ('id', 'revision', 'source')):
                    raise ValueError('Invalid audit event')
                rows.append({'timestamp': iso(when), 'service': args['service'],
                             **{key: record[key] for key in ('id', 'revision', 'source')},
                             'source_id': 'deployment-audit:' + record['id'], 'line': number})
        rows.sort(key=lambda row: row['timestamp'])
        return rows, {'backend': 'deployment_audit_file', 'file_name': file.name,
                      'file_sha256': hashlib.sha256(data).hexdigest(), 'source': 'operator-configured JSONL audit feed'}, list(dict.fromkeys(warnings))
