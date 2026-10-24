"""Deterministic incident report from Stage 1-3 results.

PROVISIONAL internal contract (brain.incident_report.draft.v0). The organiser JSON schema
(ProblemStatement.md: "provided JSON schema") has not been supplied; map to it when it arrives.
The builder copies statuses and findings verbatim; it never upgrades, downgrades or rewrites them.
"""
from dataclasses import asdict, dataclass, is_dataclass

CONTRACT = 'brain.incident_report.draft.v0'
DIAGNOSIS_STATUSES = ('diagnosed', 'escalated', 'error')
VALIDATION_STATUSES = ('validated', 'validated_with_warnings', 'rejected', 'escalated', 'technical_error')
HYPOTHESIS_LABEL = 'Hypothesis only; not a confirmed root cause.'
HEADLINES = {
    ('error', 'technical_error'): 'Technical failure: no diagnosis was produced.',
    ('escalated', 'escalated'): 'Escalated: the evidence does not support a defensible hypothesis.',
    ('diagnosed', 'rejected'): 'Hypothesis REJECTED by claim validation; do not act on it.',
    ('diagnosed', 'validated_with_warnings'): 'Unconfirmed hypothesis; claim validation raised warnings.',
    ('diagnosed', 'validated'): 'Unconfirmed hypothesis; its checkable claims matched the evidence.',
}
MODEL_KEYS = ('provider', 'model', 'slot', 'backend', 'route')


class ReportInputError(ValueError):
    """The Stage 1-3 inputs do not describe the same incident or diagnosis."""


@dataclass(frozen=True)
class IncidentReport:
    contract: str
    official_schema: str
    headline: str
    incident: dict
    diagnosis_status: str
    validation_status: str
    hypothesis: dict | None
    supporting_fact_ids: tuple
    contradicting_fact_ids: tuple
    supporting_evidence_ids: tuple
    alternative_hypotheses: tuple
    rejected_claims: tuple
    unverified_claims: tuple
    validation_warnings: tuple
    evidence_summary: tuple
    evidence_status: tuple
    evidence_gaps: tuple
    conflicts: tuple
    detector_evidence: tuple
    missing_evidence: tuple
    limitations: tuple
    recommended_next_steps: tuple
    escalation_recommended: bool
    human_review_required: bool
    model: dict
    diagnosis_problems: tuple
    unsupported_observations: int


def _fact(f):
    return {'fact_id': f.fact_id, 'type': f.type, 'description': f.description, 'evidence_ids': list(f.evidence_ids),
            'service': f.service, 'timestamp': f.timestamp, 'limitations': list(f.limitations)}


def _claim(c):
    return {'kind': c.kind, 'text': c.text, 'verdict': c.verdict, 'reason': c.reason,
            'fact_ids': list(c.fact_ids), 'evidence_ids': list(c.evidence_ids)}


def build_report(run, facts, diagnosis, validation):
    incident_id = run.incident.get('id')
    if diagnosis.incident_id != incident_id or validation.incident_id != incident_id:
        raise ReportInputError('run, diagnosis and validation refer to different incidents')
    if validation.diagnosis_status != diagnosis.status:
        raise ReportInputError('validation was produced for a different diagnosis status')
    key = (diagnosis.status, validation.status)
    if key not in HEADLINES:
        raise ReportInputError('unsupported diagnosis/validation status combination')
    by_id = {f.fact_id: f for f in facts}
    cited = list(dict.fromkeys(diagnosis.supporting_fact_ids + diagnosis.contradicting_fact_ids))
    missing = [i for i in cited if i not in by_id]
    if missing:
        raise ReportInputError('diagnosis cites fact ids that were not supplied')
    states = {}
    for f in facts:
        if f.type == 'container_state':
            states.setdefault(f.service, {}).setdefault(str(f.value), []).append(f.fact_id)
    hypothesis = None
    if diagnosis.status != 'error':
        hypothesis = {'label': HYPOTHESIS_LABEL, 'text': diagnosis.root_cause_hypothesis,
                      'affected_component': diagnosis.affected_component, 'confidence': diagnosis.confidence,
                      'proposed_confidence': diagnosis.proposed_confidence,
                      'confidence_rationale': diagnosis.confidence_rationale,
                      'confidence_policy': 'Provisional evidence-breadth cap; not a calibrated probability.'}
    limitations = list(run.limitations)
    for i in cited:
        limitations += [f'{i}: {text}' for text in by_id[i].limitations]
    return IncidentReport(
        CONTRACT, 'outstanding: organiser JSON schema not yet supplied', HEADLINES[key],
        {'id': incident_id, 'service': run.incident.get('service'), 'window': run.incident.get('window'),
         'detected_at': run.incident.get('detected_at'), 'origin': run.origin},
        diagnosis.status, validation.status, hypothesis,
        tuple(diagnosis.supporting_fact_ids), tuple(diagnosis.contradicting_fact_ids),
        tuple(validation.supporting_evidence_ids), tuple(diagnosis.alternative_hypotheses),
        tuple(_claim(c) for c in validation.rejected),
        tuple(_claim(c) for c in validation.claims if c.verdict == 'unverified'),
        tuple(validation.warnings), tuple(_fact(by_id[i]) for i in cited),
        tuple({'evidence_id': e.evidence_id, 'tool': e.tool, 'service': e.service, 'status': e.status,
               'category': e.category, 'warnings': list(e.warnings)} for e in run.evidence.values()),
        tuple(_fact(f) for f in facts if f.type == 'evidence_gap'),
        tuple({'service': s, 'kind': 'container_state', 'fact_ids_by_value': v}
              for s, v in sorted(states.items(), key=lambda x: str(x[0])) if len(v) > 1),
        tuple({'fact_id': f.fact_id, 'evidence_ids': list(f.evidence_ids),
               'evidence_in_run': f.details.get('evidence_in_run')} for f in facts if f.type == 'alert'),
        tuple(diagnosis.missing_evidence), tuple(dict.fromkeys(limitations)), tuple(diagnosis.recommended_next_steps),
        validation.escalation_recommended, True,
        {k: diagnosis.model[k] for k in MODEL_KEYS if k in diagnosis.model},
        tuple(diagnosis.problems), len(run.unsupported))


def to_dict(report):
    return asdict(report)


@dataclass(frozen=True)
class ReportValidation:
    status: str            # valid | invalid
    problems: tuple
    unverified: tuple


def validate_report(report, run, facts, diagnosis, validation):
    """Check a report (IncidentReport or its JSON dict) against the inputs it was built from."""
    data = asdict(report) if is_dataclass(report) else report
    problems, unverified = [], []
    if not isinstance(data, dict):
        return ReportValidation('invalid', ('report is not an object',), ())
    fields = IncidentReport.__dataclass_fields__
    missing = [k for k in fields if k not in data]
    if missing or set(data) - set(fields):
        return ReportValidation('invalid', (f'fields missing: {missing}, unexpected: {sorted(set(data) - set(fields))}',), ())
    lists = ('supporting_fact_ids', 'contradicting_fact_ids', 'supporting_evidence_ids', 'rejected_claims',
             'unverified_claims', 'validation_warnings', 'evidence_summary', 'missing_evidence', 'limitations')
    for key in lists:
        if not isinstance(data[key], (list, tuple)):
            problems.append(key + ' must be a list')
    if not isinstance(data['escalation_recommended'], bool) or not isinstance(data['human_review_required'], bool):
        problems.append('escalation and review flags must be booleans')
    if problems:
        return ReportValidation('invalid', tuple(problems), ())
    if data['contract'] != CONTRACT:
        problems.append('unknown contract')
    if data['diagnosis_status'] not in DIAGNOSIS_STATUSES or data['validation_status'] not in VALIDATION_STATUSES:
        problems.append('status value not allowed')
    if data['diagnosis_status'] != diagnosis.status or data['validation_status'] != validation.status:
        problems.append('statuses differ from the diagnosis or validation result')
    if data['incident'].get('id') != run.incident.get('id') or diagnosis.incident_id != run.incident.get('id'):
        problems.append('incident id is inconsistent')
    for key, label in (('service', 'service'), ('window', 'window'), ('detected_at', 'detected_at')):
        if data['incident'].get(key) != run.incident.get(key):
            problems.append(f'incident {label} differs from the run')
    by_id = {f.fact_id: f for f in facts}
    cited = list(data['supporting_fact_ids']) + list(data['contradicting_fact_ids'])
    if any(i not in by_id for i in cited):
        problems.append('report cites fact ids that do not exist')
    if list(data['supporting_fact_ids']) != list(diagnosis.supporting_fact_ids):
        problems.append('supporting fact ids differ from the diagnosis')
    derived = list(dict.fromkeys(e for i in data['supporting_fact_ids'] if i in by_id for e in by_id[i].evidence_ids))
    if list(data['supporting_evidence_ids']) != derived:
        problems.append('supporting evidence ids are not those of the cited facts')
    if [c['text'] for c in data['rejected_claims']] != [c.text for c in validation.rejected] or \
            [c['reason'] for c in data['rejected_claims']] != [c.reason for c in validation.rejected]:
        problems.append('critical rejected claims were not preserved')
    if list(data['validation_warnings']) != list(validation.warnings):
        problems.append('validation warnings were not preserved')
    if data['escalation_recommended'] != validation.escalation_recommended:
        problems.append('escalation flag differs from the validation result')
    if data['headline'] != HEADLINES.get((diagnosis.status, validation.status)):
        problems.append('headline does not match the statuses')
    hypothesis = data['hypothesis']
    if diagnosis.status == 'error':
        if hypothesis is not None:
            problems.append('a technical error must not carry a hypothesis')
    elif not isinstance(hypothesis, dict) or hypothesis.get('label') != HYPOTHESIS_LABEL:
        problems.append('hypothesis must carry the not-confirmed label')
    elif hypothesis.get('text') != diagnosis.root_cause_hypothesis or \
            hypothesis.get('confidence') != diagnosis.confidence:
        problems.append('hypothesis text or confidence was rewritten')
    gaps = {f.fact_id for f in facts if f.type == 'evidence_gap'}
    if {g['fact_id'] for g in data['evidence_gaps']} != gaps:
        problems.append('evidence gaps were dropped or invented')
    for item in data['evidence_status']:
        source = run.evidence.get(item.get('evidence_id'))
        if source is None or item.get('status') != source.status or item.get('category') != source.category:
            problems.append('evidence status entry does not match the run')
    if any(d.get('evidence_in_run') is False for d in data['detector_evidence']):
        unverified.append('detector alert evidence is outside this run; its samples cannot be inspected here')
    return ReportValidation('invalid' if problems else 'valid', tuple(problems), tuple(unverified))
