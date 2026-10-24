"""Deterministic fact extraction from a loaded Run. No model calls, no inference beyond arithmetic."""
from dataclasses import dataclass
import hashlib
import json

OTLP_STATUS_ERROR = 2  # OTLP Status.StatusCode STATUS_CODE_ERROR


@dataclass(frozen=True)
class Fact:
    fact_id: str
    type: str
    description: str
    evidence_ids: tuple
    service: str | None
    timestamp: str | None
    value: object
    unit: str | None
    details: dict
    limitations: tuple


def _fact(kind, description, evidence_ids, key, service=None, when=None, value=None, unit=None,
          details=None, limitations=()):
    identity = json.dumps([kind, list(evidence_ids), key], sort_keys=True, default=str)
    return Fact('fact-' + hashlib.sha256(identity.encode()).hexdigest()[:16], kind, description,
                tuple(evidence_ids), service, when, value, unit, details or {}, tuple(limitations))


def _alerts(run):
    for alert in run.incident['alerts']:
        if not isinstance(alert, dict) or not all(k in alert for k in ('metric', 'value', 'threshold')):
            continue
        refs = tuple(r for r in (alert.get('evidence_id'),) if isinstance(r, str))
        present = all(r in run.evidence for r in refs)
        value, threshold = alert['value'], alert['threshold']
        yield _fact('alert', f"{alert['metric']} {value} exceeded threshold {threshold} on {run.incident['service']}",
                    refs, [alert['metric'], alert.get('timestamp')], run.incident['service'], alert.get('timestamp'),
                    value, None, {'metric': alert['metric'], 'threshold': threshold,
                                  'source_time': alert.get('source_time'), 'query': alert.get('query'),
                                  'freshness_evidence_id': alert.get('freshness_evidence_id'),
                                  'coverage_evidence_id': alert.get('coverage_evidence_id'),
                                  'evidence_in_run': present},
                    () if present else ('Alert evidence is held in the detector store, not in this run',))


def _metric(e, row):
    values = [s['value'] for s in row['samples']]
    last = row['samples'][-1]
    return _fact('metric_series', f"{row['metric']} for {e.service}: last {last['value']} {row.get('unit') or ''} "
                 f"at {last['timestamp']} (min {min(values)}, max {max(values)}, {len(values)} samples)".replace('  ', ' '),
                 (e.evidence_id,), row['source_id'], e.service, last['timestamp'], last['value'], row.get('unit'),
                 {'metric': row['metric'], 'labels': row.get('labels', {}), 'min': min(values), 'max': max(values),
                  'sample_count': len(values), 'first_timestamp': row['samples'][0]['timestamp'],
                  'window': e.window, 'source_id': row['source_id']}, e.warnings)


def _log(e, row):
    return _fact('log_entry', f"{row.get('severity') or 'UNKNOWN'} log from {row.get('service', e.service)} at "
                 f"{row['timestamp']}: {row['body'][:300]}", (e.evidence_id,), row['source_id'],
                 row.get('service', e.service), row['timestamp'], row['body'], None,
                 {'severity': row.get('severity'), 'trace_id': row.get('traceId'), 'span_id': row.get('spanId'),
                  'body_truncated': row.get('body_truncated', False), 'source_id': row['source_id']}, e.warnings)


def _span(e, row):
    error = row['status_code'] == OTLP_STATUS_ERROR
    return _fact('span', f"span {row['name']} in {row.get('service', e.service)} status_code {row['status_code']}"
                 f"{' (ERROR)' if error else ''}, duration {row.get('duration_ms')} ms",
                 (e.evidence_id,), row['source_id'], row.get('service', e.service), row['timestamp'],
                 row.get('duration_ms'), 'ms' if 'duration_ms' in row else None,
                 {'name': row['name'], 'trace_id': row['trace_id'], 'span_id': row['span_id'],
                  'parent_span_id': row.get('parent_span_id'), 'kind': row.get('kind'),
                  'status_code': row['status_code'], 'is_error': error,
                  'attributes': row.get('attributes', {}), 'source_id': row['source_id']}, e.warnings)


def _container(e, row):
    return _fact('container_state', f"container for {row.get('service', e.service)} status {row['status']}, "
                 f"running {row['running']}, health {row.get('health')} at {row['observed_at']}",
                 (e.evidence_id,), row['source_id'], row.get('service', e.service), row['observed_at'], row['status'],
                 None, {k: row.get(k) for k in ('running', 'health', 'exit_code', 'started_at', 'finished_at',
                                                'container_id', 'source_id')},
                 e.warnings + ('Collection-time snapshot, not state over the window',))


def _event(e, row):
    return _fact('container_event', f"container event {row['action']} for {row.get('service', e.service)} at "
                 f"{row['timestamp']}", (e.evidence_id,), row['source_id'], row.get('service', e.service),
                 row['timestamp'], row['action'], None,
                 {'container_id': row.get('container_id'), 'source_id': row['source_id']}, e.warnings)


def _deployment(e, row):
    return _fact('deployment', f"deployment {row['id']} revision {row['revision']} for {row.get('service', e.service)}"
                 f" at {row['timestamp']}", (e.evidence_id,), row['source_id'], row.get('service', e.service),
                 row['timestamp'], row['revision'], None,
                 {'source': row.get('source'), 'source_id': row['source_id']}, e.warnings)


EXTRACTORS = {'query_metrics': _metric, 'search_logs': _log, 'search_traces': _span,
              'container_health': _container, 'container_events': _event, 'deployment_history': _deployment}


def extract(run):
    facts = list(_alerts(run))
    for e in run.evidence.values():
        if not e.usable:
            code = (e.error or {}).get('code')
            facts.append(_fact('evidence_gap', f"{e.tool or 'unknown tool'} for {e.service or 'unknown service'} "
                               f"returned {e.status}{' (' + code + ')' if code else ''}; no observation is available",
                               (e.evidence_id,), e.status, e.service, e.collected_at, None, None,
                               {'tool': e.tool, 'status': e.status, 'category': e.category,
                                'error_code': code, 'window': e.window},
                               ('Absence of data is not evidence of health or failure',)))
            continue
        facts.extend(EXTRACTORS[e.tool](e, row) for row in e.observations)
    spans = {}
    for f in facts:
        if f.type == 'span':
            spans.setdefault(f.details['trace_id'], []).append(f)
    for f in [f for f in facts if f.type == 'log_entry' and f.details.get('trace_id') in spans]:
        matches = spans[f.details['trace_id']]
        refs = tuple(dict.fromkeys(f.evidence_ids + tuple(r for m in matches for r in m.evidence_ids)))
        facts.append(_fact('log_trace_link', f"log {f.details['source_id']} shares trace_id "
                           f"{f.details['trace_id']} with {len(matches)} span(s)", refs,
                           [f.fact_id] + [m.fact_id for m in matches], f.service, f.timestamp, None, None,
                           {'trace_id': f.details['trace_id'], 'log_fact_id': f.fact_id,
                            'span_fact_ids': [m.fact_id for m in matches]},
                           ('Shared trace ID shows the records belong to one request, not a causal relation',)))
    return facts
