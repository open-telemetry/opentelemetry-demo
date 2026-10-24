"""Deterministic Markdown view of a Stage 4 IncidentReport. Renders only what the report contains."""
from dataclasses import asdict, is_dataclass
import json
import re

from .report import IncidentReport

NONE = '_not available_'
SAFE_ID = re.compile(r'^[A-Za-z0-9._:/-]+$')


def esc(value):
    """Telemetry-derived text is untrusted: flatten lines and neutralise Markdown/HTML syntax."""
    if value is None:
        return NONE
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    text = re.sub(r'\s+', ' ', text).strip()
    # Escape every Markdown-significant character, then HTML-encode angle brackets and ampersands.
    text = re.sub(r'([\\`*_{}\[\]()#+\-.!|~>])', r'\\\1', text)
    return text.replace('&', '&amp;').replace('<', '&lt;') or NONE


def ref(value):
    return f'`{value}`' if isinstance(value, str) and SAFE_ID.match(value) else esc(value)


def refs(values):
    return ', '.join(ref(v) for v in values) if values else NONE


def bullets(items, fmt):
    return [f'- {fmt(item)}' for item in items] if items else [f'- {NONE}']


def render_markdown(report):
    data = asdict(report) if is_dataclass(report) else report
    missing = set(IncidentReport.__dataclass_fields__) - set(data)
    if missing:
        raise ValueError('report is missing fields: ' + ', '.join(sorted(missing)))
    inc, hyp = data['incident'] or {}, data['hypothesis']
    window = inc.get('window') or {}
    out = [f"# Incident report: {ref(inc.get('id'))}", '', f"**{esc(data['headline'])}**", '',
           f"> Contract {ref(data['contract'])}. Official schema: {esc(data['official_schema'])}.", '',
           '## Incident', '',
           f"- Service: {ref(inc.get('service'))}",
           f"- Window: {ref(window.get('start'))} to {ref(window.get('end'))}",
           f"- Detected at: {ref(inc.get('detected_at'))}",
           f"- Origin: {ref(inc.get('origin'))}", '',
           '## Status', '',
           f"- Diagnosis status: {ref(data['diagnosis_status'])}",
           f"- Claim-validation status: {ref(data['validation_status'])}",
           f"- Escalation recommended: **{'yes' if data['escalation_recommended'] else 'no'}**",
           f"- Human review required: **{'yes' if data['human_review_required'] else 'no'}**", '']
    if data['rejected_claims']:
        out += ['## REJECTED claims', '', '> Claim validation rejected the following. Do not act on this hypothesis.', '']
        out += bullets(data['rejected_claims'], lambda c: f"{esc(c['kind'])} {esc(c['text'])}: {esc(c['verdict'])}, "
                       f"{esc(c['reason'])} (facts {refs(c['fact_ids'])}; evidence {refs(c['evidence_ids'])})")
        out.append('')
    out += ['## Hypothesis', '']
    if hyp is None:
        out += ['No hypothesis: the diagnosis failed technically. Nothing below is a diagnosis.', '']
    else:
        out += [f"_{esc(hyp.get('label'))}_", '',
                f"- Hypothesis: {esc(hyp.get('text'))}",
                f"- Affected component: {ref(hyp.get('affected_component'))}",
                f"- Confidence: {ref(hyp.get('confidence'))} (model proposed {ref(hyp.get('proposed_confidence'))})",
                f"- Confidence rationale: {esc(hyp.get('confidence_rationale'))}",
                f"- Confidence policy: {esc(hyp.get('confidence_policy'))}", '']
    out += ['## References', '',
            f"- Supporting facts: {refs(data['supporting_fact_ids'])}",
            f"- Contradicting facts: {refs(data['contradicting_fact_ids'])}",
            f"- Supporting evidence: {refs(data['supporting_evidence_ids'])}", '',
            '## Alternative hypotheses', '']
    out += bullets(data['alternative_hypotheses'],
                   lambda a: f"{esc(a.get('hypothesis'))} (facts {refs(a.get('supporting_fact_ids', []))})")
    out += ['', '## Unverified claims', '']
    out += bullets(data['unverified_claims'], lambda c: f"{esc(c['kind'])} {esc(c['text'])}: {esc(c['reason'])}")
    out += ['', '## Validation warnings', '']
    out += bullets(data['validation_warnings'], esc)
    out += ['', '## Evidence summary (cited facts)', '']
    out += bullets(data['evidence_summary'], lambda f: f"{ref(f['fact_id'])} {esc(f['type'])}: {esc(f['description'])} "
                   f"(evidence {refs(f['evidence_ids'])}; time {ref(f.get('timestamp'))})"
                   + (f"; limitations: {'; '.join(esc(x) for x in f['limitations'])}" if f.get('limitations') else ''))
    out += ['', '## Evidence status', '']
    out += bullets(data['evidence_status'], lambda e: f"{ref(e['evidence_id'])} {ref(e.get('tool'))} for "
                   f"{ref(e.get('service'))}: {ref(e['status'])} ({ref(e['category'])})"
                   + (f"; warnings: {'; '.join(esc(w) for w in e['warnings'])}" if e.get('warnings') else ''))
    out += ['', '## Evidence gaps', '', '_Absence of data is not evidence of health or failure._', '']
    out += bullets(data['evidence_gaps'], lambda f: f"{ref(f['fact_id'])}: {esc(f['description'])}")
    out += ['', '## Conflicting observations', '']
    out += bullets(data['conflicts'], lambda c: f"{ref(c['service'])} {esc(c['kind'])}: " + '; '.join(
        f"{esc(value)} in {refs(ids)}" for value, ids in sorted(c['fact_ids_by_value'].items())))
    out += ['', '## Detector alert evidence', '']
    out += bullets(data['detector_evidence'], lambda d: f"{ref(d['fact_id'])} evidence {refs(d['evidence_ids'])}: "
                   + ('present in this run' if d.get('evidence_in_run') else 'held in the detector store, not in this run'))
    out += ['', '## Missing evidence', '']
    out += bullets(data['missing_evidence'], esc)
    out += ['', '## Limitations', '']
    out += bullets(data['limitations'], esc)
    out += ['', '## Recommended next steps (investigative only; nothing was executed)', '']
    out += bullets(data['recommended_next_steps'], esc)
    model = data['model'] or {}
    out += ['', '## Model', '', f"- {', '.join(f'{k}: {ref(v)}' for k, v in sorted(model.items())) or NONE}",
            '', '## Diagnosis problems', '']
    out += bullets(data['diagnosis_problems'], esc)
    out += ['', f"Unsupported observations recorded by the loader: {int(data['unsupported_observations'])}", '']
    return '\n'.join(out)
