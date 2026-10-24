"""Load an Eyes investigation record (Investigator.run output / checkpoint1_execution_log.json).

Internal Brain structures only; this is not the organiser scoring schema.
"""
from dataclasses import dataclass, field
import json
from pathlib import Path

from incident_tools.f02.boundary import timestamp

# F02 status values (incident_tools/f02/README.md "Result contract") mapped to Brain categories.
CATEGORIES = {'ok': 'usable', 'partial': 'usable_with_limits', 'no_data': 'empty',
              'unavailable': 'unavailable', 'invalid_request': 'invalid_request', 'error': 'error'}
USABLE = ('usable', 'usable_with_limits')

# Minimum observation fields per F02 tool, taken from the rows built in incident_tools/f02/tools.py.
REQUIRED = {
    'query_metrics': ('metric', 'samples', 'source_id'),
    'search_logs': ('timestamp', 'body', 'source_id'),
    'search_traces': ('timestamp', 'trace_id', 'span_id', 'name', 'status_code', 'source_id'),
    'container_health': ('status', 'running', 'observed_at', 'source_id'),
    'container_events': ('timestamp', 'action', 'source_id'),
    'deployment_history': ('timestamp', 'id', 'revision', 'source_id'),
}
TIME_FIELDS = {'search_logs': 'timestamp', 'search_traces': 'timestamp', 'container_health': 'observed_at',
               'container_events': 'timestamp', 'deployment_history': 'timestamp'}


class RunFormatError(ValueError):
    """The input is not a usable Eyes investigation record. Messages name fields, never values."""


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    tool: str | None
    service: str | None
    status: str
    category: str
    window: dict | None
    collected_at: str | None
    origin: str | None
    observations: tuple
    warnings: tuple
    error: dict | None
    provenance: dict | None

    @property
    def usable(self):
        return self.category in USABLE and bool(self.observations)


@dataclass(frozen=True)
class Run:
    incident: dict
    evidence: dict
    decisions: tuple
    interpretations: tuple
    limitations: tuple
    stop_reason: str
    origin: str | None
    finished_at: str | None
    unsupported: tuple = field(default=())
    notes: tuple = field(default=())


def _require(data, key, kind, where):
    if key not in data:
        raise RunFormatError(f'{where}: missing required field "{key}"')
    if not isinstance(data[key], kind):
        raise RunFormatError(f'{where}: field "{key}" has an invalid type')
    return data[key]


def _observation_problem(tool, item):
    if not isinstance(item, dict):
        return 'observation is not an object'
    missing = [k for k in REQUIRED[tool] if k not in item]
    if missing:
        return 'missing fields: ' + ', '.join(missing)
    try:
        if tool == 'query_metrics':
            if not isinstance(item['samples'], list) or not item['samples']:
                return 'samples must be a non-empty list'
            for sample in item['samples']:
                timestamp(sample['timestamp'])
                if isinstance(sample['value'], bool) or not isinstance(sample['value'], (int, float)):
                    return 'sample value is not numeric'
        else:
            timestamp(item[TIME_FIELDS[tool]])
    except (KeyError, TypeError, ValueError):
        return 'invalid sample or timestamp'
    return None


def _evidence(raw, index, unsupported):
    where = f'evidence[{index}]'
    if not isinstance(raw, dict):
        raise RunFormatError(where + ': not an object')
    evidence_id = _require(raw, 'evidence_id', str, where)
    status = _require(raw, 'status', str, where)
    observations = raw.get('observations', [])
    if not isinstance(observations, list):
        raise RunFormatError(where + ': field "observations" has an invalid type')
    category = CATEGORIES.get(status, 'unrecognized_status')
    tool = raw.get('tool')
    kept = []
    for position, item in enumerate(observations):
        if category not in USABLE:
            # Observations attached to a failed result are never treated as successful data.
            unsupported.append({'evidence_id': evidence_id, 'index': position, 'reason': 'status ' + status})
            continue
        problem = 'unknown tool' if tool not in REQUIRED else _observation_problem(tool, item)
        if problem:
            unsupported.append({'evidence_id': evidence_id, 'index': position, 'reason': problem})
        else:
            kept.append(item)
    if category in USABLE and not kept:
        category = 'empty'
    window = raw.get('window')
    return Evidence(evidence_id, tool, raw.get('service'), status, category,
                    window if isinstance(window, dict) else None, raw.get('collected_at'), raw.get('origin'),
                    tuple(kept), tuple(w for w in raw.get('warnings', []) if isinstance(w, str)),
                    raw.get('error') if isinstance(raw.get('error'), dict) else None,
                    raw.get('provenance') if isinstance(raw.get('provenance'), dict) else None)


def load_run(source):
    """Accept a path to checkpoint1_execution_log.json or an already-loaded dict."""
    if isinstance(source, (str, Path)):
        try:
            data = json.loads(Path(source).read_text(encoding='utf-8-sig'))
        except OSError:
            raise RunFormatError('run file cannot be read') from None
        except (ValueError, RecursionError):
            raise RunFormatError('run file is not valid JSON') from None
    elif isinstance(source, dict):
        data = source
    else:
        raise RunFormatError('expected a file path or a dict')
    if not isinstance(data, dict):
        raise RunFormatError('run must be a JSON object')
    incident = _require(data, 'incident', dict, 'run')
    for key, kind in (('id', str), ('service', str), ('window', dict), ('alerts', list)):
        _require(incident, key, kind, 'incident')
    raw_evidence = _require(data, 'evidence', list, 'run')
    stop_reason = _require(data, 'stop_reason', str, 'run')
    for key in ('decisions', 'interpretations', 'limitations'):
        if key in data and not isinstance(data[key], list):
            raise RunFormatError(f'run: field "{key}" has an invalid type')
    evidence, unsupported, notes = {}, [], []
    for index, raw in enumerate(raw_evidence):
        item = _evidence(raw, index, unsupported)
        if item.evidence_id in evidence:
            if raw_evidence[index] != next(r for r in raw_evidence if r.get('evidence_id') == item.evidence_id):
                raise RunFormatError(f'evidence[{index}]: duplicate evidence_id with different content')
            notes.append('Duplicate identical evidence ' + item.evidence_id + ' kept once')
            continue
        evidence[item.evidence_id] = item
    return Run(incident, evidence, tuple(data.get('decisions', [])), tuple(data.get('interpretations', [])),
               tuple(x for x in data.get('limitations', []) if isinstance(x, str)), stop_reason,
               data.get('origin'), data.get('finished_at'), tuple(unsupported), tuple(notes))
