"""Deterministic claim validation of a Stage 2 Diagnosis against Stage 1 facts.

Internal result (brain.claim_validation.draft.v0), not the official hackathon schema.
Only mechanically recognisable claims in root_cause_hypothesis and confidence_rationale are checked:
numbers with an explicit unit, ISO timestamps, quoted text, status/error codes and Docker container
states. Causal statements are never proven here; the hypothesis itself always stays unverified.
"""
from dataclasses import dataclass
import math
import re

from incident_tools.f02.boundary import timestamp
from incident_tools.f02.tools import METRICS

CONTRACT = 'brain.claim_validation.draft.v0'
UNITS = {'ms': 'ms', 'msec': 'ms', 'millisecond': 'ms', 'milliseconds': 'ms', 's': 's', 'sec': 's',
         'second': 's', 'seconds': 's', '%': '%', 'percent': '%', 'fraction': 'fraction',
         'requests/second': 'requests/second', 'req/s': 'requests/second', 'rps': 'requests/second'}
# Docker container states and the lifecycle event actions that can establish them.
STATES = {'paused': ('pause',), 'exited': ('die', 'stop', 'kill'), 'restarting': ('restart',),
          'dead': ('die',), 'oomkilled': ('oom',)}
NUMBER = re.compile(r'(?<![\w.])(-?\d+(?:\.\d+)?)\s*(milliseconds|millisecond|msec|ms|seconds|second|sec|s|'
                    r'percent|%|req/s|rps|requests/second)(?![\w/])', re.I)
ISO = re.compile(r'\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?')
QUOTE = re.compile(r'"([^"]{4,})"|`([^`]{4,})`')
CODE = re.compile(r'\b(?:http(?:\s+status)?|status(?:[_ ]code)?|grpc(?:\s+status)?(?:[_ ]code)?|'
                  r'rpc\.grpc\.status_code|http\.response\.status_code)\s*[:=]?\s*(\d{1,3})\b', re.I)
STATE_WORD = re.compile(r'\b(' + '|'.join(STATES) + r')\b', re.I)


@dataclass(frozen=True)
class Claim:
    kind: str
    text: str
    verdict: str            # observed | consistent | contradicted | unsupported | unverified
    critical: bool
    reason: str
    fact_ids: tuple = ()
    evidence_ids: tuple = ()


@dataclass(frozen=True)
class ClaimValidation:
    status: str             # validated | validated_with_warnings | rejected | escalated | technical_error
    incident_id: str
    diagnosis_status: str
    claims: tuple
    warnings: tuple
    escalation_recommended: bool
    supporting_evidence_ids: tuple
    contract: str = CONTRACT

    @property
    def rejected(self):
        return tuple(c for c in self.claims if c.critical and c.verdict in ('contradicted', 'unsupported'))


def _unit(name):
    return UNITS.get((name or '').lower())


def _norm(text):
    return re.sub(r'[^a-z0-9]', '', text.lower())


def _numbers(facts):
    """(value, unit, fact) for every numeric value a fact actually carries."""
    out = []
    for f in facts:
        unit = _unit(f.unit)
        if f.type == 'alert':
            unit = _unit(METRICS.get(f.details.get('metric'), ('',))[0])
            out.append((f.details.get('threshold'), unit, f))
        if f.type == 'metric_series':
            out += [(f.details.get('min'), unit, f), (f.details.get('max'), unit, f)]
        out.append((f.value, unit, f))
    return [(v, u, f) for v, u, f in out if isinstance(v, (int, float)) and not isinstance(v, bool)]


def _same(a, b):
    return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-9)


def _claim(kind, text, verdict, reason, facts=(), critical=True):
    return Claim(kind, text, verdict, critical, reason, tuple(f.fact_id for f in facts),
                 tuple(dict.fromkeys(e for f in facts for e in f.evidence_ids)))


def _check_numbers(text, facts, cited):
    claims, known = [], _numbers(facts)
    for match in NUMBER.finditer(text):
        value, unit = float(match.group(1)), _unit(match.group(2))
        same = [f for v, u, f in known if u == unit and _same(v, value)]
        other = [(u, f) for v, u, f in known if u != unit and _same(v, value)]
        if same:
            in_cited = [f for f in same if f.fact_id in cited]
            claims.append(_claim('metric_value', match.group(0), 'observed', 'value and unit match a cited fact',
                                 in_cited, critical=False) if in_cited else
                          _claim('metric_value', match.group(0), 'unverified', 'matches an uncited fact only',
                                 same, critical=False))
        elif other:
            claims.append(_claim('metric_value', match.group(0), 'contradicted',
                                 f'value observed with unit {other[0][0]}, not {unit}', [f for _, f in other]))
        elif any(u == unit for _, u, _ in known):
            claims.append(_claim('metric_value', match.group(0), 'unsupported', 'no fact carries this value'))
        else:
            claims.append(_claim('metric_value', match.group(0), 'unverified',
                                 f'no fact uses unit {unit}; values are never converted between units', critical=False))
    return claims


def _check_timestamps(text, facts, window):
    claims = []
    start, end = timestamp(window['start']), timestamp(window['end'])
    for match in ISO.finditer(text):
        raw = match.group(0)
        try:
            when = timestamp(raw if re.search(r'(Z|[+-]\d{2}:\d{2})$', raw) else raw + 'Z')
        except ValueError:
            claims.append(_claim('timestamp', raw, 'unverified', 'timestamp could not be parsed', critical=False))
            continue
        hits = [f for f in facts if f.timestamp and timestamp(f.timestamp) == when]
        if hits:
            claims.append(_claim('timestamp', raw, 'observed', 'matches a fact timestamp', hits, critical=False))
        elif start <= when <= end:
            claims.append(_claim('timestamp', raw, 'unverified', 'inside the incident window but not a fact time',
                                 critical=False))
        else:
            claims.append(_claim('timestamp', raw, 'contradicted', 'outside the incident window and not observed'))
    return claims


def _check_quotes(text, facts, cited):
    claims = []
    for match in QUOTE.finditer(text):
        quote = match.group(1) or match.group(2)
        hits = [f for f in facts if quote in f.description or (isinstance(f.value, str) and quote in f.value)]
        cited_hits = [f for f in hits if f.fact_id in cited]
        if cited_hits:
            claims.append(_claim('quotation', quote, 'observed', 'verbatim in a cited fact', cited_hits, critical=False))
        elif hits:
            claims.append(_claim('quotation', quote, 'unverified', 'verbatim only in an uncited fact', hits, critical=False))
        else:
            claims.append(_claim('quotation', quote, 'unsupported', 'text does not appear in any fact'))
    return claims


def _check_codes(text, facts):
    observed = {}
    for f in facts:
        values = []
        if f.type == 'span':
            values = [f.details.get('status_code')] + [v for k, v in f.details.get('attributes', {}).items()
                                                       if k.endswith('status_code')]
        if f.type == 'log_entry' and isinstance(f.value, str):
            values = re.findall(r'\b\d{3}\b', f.value)
        for v in values:
            observed.setdefault(str(v), []).append(f)
    return [_claim('status_code', m.group(0), 'observed', 'code appears in a span or log fact', observed[m.group(1)],
                   critical=False) if m.group(1) in observed else
            _claim('status_code', m.group(0), 'unsupported', 'no span or log fact carries this code')
            for m in CODE.finditer(text)]


def _check_states(text, facts):
    claims = []
    for word in dict.fromkeys(w.lower() for w in STATE_WORD.findall(text)):
        hits = [f for f in facts if (f.type == 'container_state' and str(f.value).lower() == word)
                or (f.type == 'container_event' and str(f.value).lower() in STATES[word])]
        seen = sorted({str(f.value) for f in facts if f.type == 'container_state'})
        claims.append(_claim('container_state', word, 'observed', 'state or lifecycle event observed', hits,
                             critical=False) if hits else
                      _claim('container_state', word, 'unsupported',
                             'no container state or event shows this' + (f' (observed: {", ".join(seen)})' if seen else '')))
    return claims


def _component(diagnosis, support):
    component = diagnosis.affected_component
    key = _norm(component or '')
    if not key:
        return []
    observations = [f for f in support if f.type not in ('alert', 'log_trace_link', 'evidence_gap')]
    direct = [f for f in observations if f.service == component]
    dependency = [f for f in observations if f.type == 'span' and
                  key in _norm(f.details.get('name', '') + ' ' + str(f.details.get('attributes', {}).get('server.address', '')))]
    if direct:
        return [_claim('component', component, 'observed', 'a supporting observation comes from this component', direct)]
    if dependency:
        return [_claim('component', component, 'consistent', 'a supporting span calls this component', dependency)]
    if observations and all(f.type == 'metric_series' for f in observations):
        reason = 'supporting metrics come from other services; no dependency evidence links them'
    elif not observations and any(f.type == 'log_trace_link' for f in support):
        reason = 'only a shared trace ID links the evidence; that is not causal evidence'
    else:
        reason = 'supporting facts only co-occur in time with this component; no dependency evidence'
    return [_claim('component', component, 'unsupported', reason, support)]


def validate_claims(diagnosis, facts, run):
    """Return findings separately; the Diagnosis is never modified."""
    by_id = {f.fact_id: f for f in facts}
    claims, warnings = [], []
    if diagnosis.status == 'error':
        return ClaimValidation('technical_error', diagnosis.incident_id, diagnosis.status, (),
                               ('Diagnosis failed technically; nothing to validate. Retry rather than escalate.',),
                               False, ())
    for label, ids in (('supporting', diagnosis.supporting_fact_ids), ('contradicting', diagnosis.contradicting_fact_ids)):
        for ref in ids:
            if ref not in by_id:
                kind = 'evidence id used as fact id' if ref in run.evidence else 'unknown fact id'
                claims.append(Claim('reference', ref, 'unsupported', True, f'{label}: {kind}'))
    support = [by_id[i] for i in diagnosis.supporting_fact_ids if i in by_id]
    derived = tuple(dict.fromkeys(e for f in support for e in f.evidence_ids))
    if tuple(diagnosis.supporting_evidence_ids) != derived:
        claims.append(Claim('provenance', ', '.join(diagnosis.supporting_evidence_ids), 'contradicted', True,
                            'supporting_evidence_ids are not those of the cited facts', (), derived))
    for f in support:
        if f.type == 'evidence_gap':
            claims.append(_claim('evidence', f.fact_id, 'unsupported', 'cites evidence that returned no data', [f]))
        for ref in f.evidence_ids:
            item = run.evidence.get(ref)
            if item is None:
                warnings.append(f'{f.fact_id}: evidence {ref} is not in this run (detector store)')
            elif item.category == 'usable_with_limits':
                warnings.extend(f'{f.fact_id}: partial evidence {ref}: {w}' for w in item.warnings or ('limited',))
            elif not item.usable:
                claims.append(_claim('evidence', f.fact_id, 'unsupported', f'evidence {ref} is {item.status}', [f]))
    states = {}
    for f in facts:
        if f.type == 'container_state':
            states.setdefault(f.service, []).append(f)
    for f in support:
        others = [o for o in states.get(f.service, []) if o.value != f.value and f.type == 'container_state'
                  and o.fact_id not in diagnosis.contradicting_fact_ids]
        if others:
            warnings.append(f'{f.fact_id}: conflicting container state {others[0].value} not acknowledged as contradicting')
    if diagnosis.status == 'diagnosed':
        claims += _component(diagnosis, support)
        observations = [f for f in support if f.type not in ('alert', 'evidence_gap')]
        if observations and all(f.type in ('metric_series', 'log_trace_link') for f in observations):
            warnings.append('Support is metric or trace-link only; no span, log or container evidence of the cause')
        claims.append(Claim('root_cause', diagnosis.root_cause_hypothesis or '', 'unverified', False,
                            'causal relationships cannot be established deterministically',
                            tuple(diagnosis.supporting_fact_ids), derived))
    cited = set(diagnosis.supporting_fact_ids) | set(diagnosis.contradicting_fact_ids)
    for field_name in ('root_cause_hypothesis', 'confidence_rationale'):
        text = getattr(diagnosis, field_name) or ''
        for claim in (_check_numbers(text, facts, cited) + _check_timestamps(text, facts, run.incident['window'])
                      + _check_quotes(text, facts, cited) + _check_codes(text, facts) + _check_states(text, facts)):
            claims.append(claim)
    rejected = any(c.critical and c.verdict in ('contradicted', 'unsupported') for c in claims)
    weak = any(w.startswith('Support is metric') for w in warnings)
    if diagnosis.status == 'escalated':
        status = 'escalated'
    elif rejected:
        status = 'rejected'
    else:
        status = 'validated_with_warnings' if warnings or any(c.verdict == 'unverified' and c.kind != 'root_cause'
                                                             for c in claims) else 'validated'
    return ClaimValidation(status, diagnosis.incident_id, diagnosis.status, tuple(claims), tuple(warnings),
                           diagnosis.status == 'escalated' or rejected or weak, derived)
