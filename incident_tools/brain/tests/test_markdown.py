"""Brain stage 5 tests. Offline, SYNTHETIC data from real F02 code over fake transports."""
from dataclasses import asdict
import json
import re
import unittest

from incident_tools.brain.markdown import esc, render_markdown
from incident_tools.brain.report import to_dict
from test_brain import FakeDocker, call, logs_response, run_dict, tools
from test_diagnosis import FakeRouter, answer
from test_report import pipeline


def section(markdown, title):
    match = re.search(r'^## ' + re.escape(title) + r'\n(.*?)(?=^## |\Z)', markdown, re.M | re.S)
    return match.group(1) if match else None


def without_label(markdown):
    return markdown.lower().replace('not a confirmed root cause', '')


class MarkdownTests(unittest.TestCase):
    def test_validated_hypothesis_is_never_called_confirmed(self):
        report = pipeline()[-1]
        md = render_markdown(report)
        self.assertIn('Diagnosis status: `diagnosed`', md)
        self.assertIn('Claim-validation status: `validated`', md)
        self.assertIn('not a confirmed root cause', md)
        self.assertNotIn('confirmed root cause', without_label(md))
        self.assertNotIn('REJECTED claims', md)
        self.assertIn('Human review required: **yes**', md)
        self.assertIn('Official schema: outstanding', md)
        for fact_id in report.supporting_fact_ids:
            self.assertIn(f'`{fact_id}`', section(md, 'References'))

    def test_warnings_rejections_and_flags_are_visible(self):
        warned = render_markdown(pipeline(confidence_rationale='errors began at 2026-01-02T10:02:00Z')[-1])
        self.assertIn('validated\\_with\\_warnings', warned.replace('`validated_with_warnings`', 'validated\\_with\\_warnings'))
        self.assertIn('inside the incident window but not a fact time', section(warned, 'Unverified claims'))
        rejected_report = pipeline(root_cause_hypothesis='shipping returns HTTP 503')[-1]
        md = render_markdown(rejected_report)
        self.assertLess(md.index('## REJECTED claims'), md.index('## Hypothesis'))
        self.assertIn('no span or log fact carries this code', section(md, 'REJECTED claims'))
        self.assertIn('Escalation recommended: **yes**', md)

    def test_escalated_and_technical_error(self):
        escalated = render_markdown(pipeline(router=FakeRouter(answer(
            status='escalated', confidence='low', affected_component=None, root_cause_hypothesis=None)))[-1])
        self.assertIn('Diagnosis status: `escalated`', escalated)
        self.assertIn('Hypothesis: _not available_', escalated)
        error = render_markdown(pipeline(router=FakeRouter(error=RuntimeError('provider said sk-secret')))[-1])
        self.assertIn('Claim-validation status: `technical_error`', error)
        self.assertIn('No hypothesis: the diagnosis failed technically', error)
        self.assertNotIn('Affected component', error)
        self.assertNotIn('sk-secret', error)
        self.assertIn('Escalation recommended: **no**', error)

    def test_missing_metadata_is_shown_not_invented(self):
        data = run_dict([call(tools(), 'search_traces'), call(tools(), 'search_logs')])
        del data['incident']['detected_at']
        data['origin'] = None
        md = render_markdown(pipeline(data)[-1])
        self.assertIn('- Detected at: _not available_', md)
        self.assertIn('- Origin: _not available_', md)

    def test_partial_unavailable_and_conflicting_evidence(self):
        partial = call(tools({'opensearch': logs_response(total=500)}), 'search_logs', limit=1)
        data = run_dict([partial, call(tools(), 'search_traces'), call(tools(docker=FakeDocker('exited')), 'container_health'),
                         call(tools(), 'container_health'), call(tools(), 'deployment_history')])
        md = render_markdown(pipeline(data)[-1])
        self.assertIn('Log limit reached', section(md, 'Validation warnings'))
        self.assertIn('`unavailable`', section(md, 'Evidence status'))
        self.assertIn('Absence of data is not evidence of health or failure', md)
        self.assertNotIn(f'_not available_', section(md, 'Evidence gaps').split('\n', 3)[-1][:20])
        conflicts = section(md, 'Conflicting observations')
        self.assertIn('exited', conflicts)
        self.assertIn('running', conflicts)
        self.assertIn('held in the detector store, not in this run', section(md, 'Detector alert evidence'))

    def test_empty_lists_render_explicitly(self):
        md = render_markdown(pipeline()[-1])
        self.assertIn('- _not available_', section(md, 'Alternative hypotheses'))
        self.assertIn('- _not available_', section(md, 'Conflicting observations'))

    def test_hostile_telemetry_is_escaped(self):
        hostile = logs_response()
        hostile['hits']['hits'][0]['_source']['body'] = '**bold** <script>alert(1)</script>\n# Heading | [x](http://evil) `code`'
        data = run_dict([call(tools({'opensearch': hostile}), 'search_logs'), call(tools(), 'search_traces')])
        md = render_markdown(pipeline(data)[-1])
        summary = section(md, 'Evidence summary (cited facts)')
        self.assertNotIn('<script>', md)
        self.assertIn('&lt;script', summary)
        self.assertIn('\\*\\*bold\\*\\*', summary)
        self.assertIn('\\[x\\]\\(http://evil\\)', summary)
        self.assertNotIn('\n# Heading', md)
        self.assertEqual(esc('a\nb'), 'a b')

    def test_deterministic_and_json_equivalent(self):
        first, second = pipeline()[-1], pipeline()[-1]
        self.assertEqual(render_markdown(first), render_markdown(second))
        self.assertEqual(render_markdown(first), render_markdown(json.loads(json.dumps(to_dict(first)))))
        before = asdict(first)
        render_markdown(first)
        self.assertEqual(asdict(first), before)
        with self.assertRaises(ValueError):
            render_markdown({'headline': 'x'})

    def test_no_raw_telemetry_or_credentials(self):
        md = render_markdown(pipeline()[-1])
        for forbidden in ('resourceSpans', 'Authorization', 'Bearer', 'api_key', 'provenance', 'query_sha256'):
            self.assertNotIn(forbidden, md)
        self.assertIn('model: `fake-model`', section(md, 'Model'))

    def test_model_prose_claiming_confirmation_stays_under_the_hypothesis_label(self):
        md = render_markdown(pipeline(root_cause_hypothesis='This is the confirmed root cause')[-1])
        hypothesis = section(md, 'Hypothesis')
        self.assertIn('not a confirmed root cause', hypothesis)
        self.assertLess(hypothesis.index('not a confirmed root cause'), hypothesis.index('This is the confirmed root cause'))
        unverified = section(md, 'Unverified claims')
        self.assertIn('This is the confirmed root cause: causal relationships cannot be established', unverified)
        outside = md.replace(hypothesis, '').replace(unverified, '')
        self.assertNotIn('confirmed root cause', without_label(outside))


if __name__ == '__main__':
    unittest.main()
