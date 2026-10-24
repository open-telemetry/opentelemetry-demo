"""Brain stage 4 tests. Offline, SYNTHETIC data from real F02 code over fake transports."""
from dataclasses import replace
import json
import unittest

from incident_tools.brain import diagnose
from incident_tools.brain.claim_validation import validate_claims
from incident_tools.brain.report import HYPOTHESIS_LABEL, ReportInputError, build_report, to_dict, validate_report
from test_brain import FakeDocker, call, logs_response, run_dict, tools
from test_diagnosis import FakeRouter, answer, setup


def pipeline(data=None, router=None, **overrides):
    run, facts, ids = setup(data)
    support = ids.get('span', []) + ids.get('log_entry', [])
    diagnosis = diagnose(run, facts, router or FakeRouter(answer(**{
        'affected_component': 'shipping', 'supporting_fact_ids': support,
        'root_cause_hypothesis': 'Checkout calls to shipping GetQuote fail after 4000 ms', **overrides})))
    validation = validate_claims(diagnosis, facts, run)
    return run, facts, diagnosis, validation, build_report(run, facts, diagnosis, validation)


class ReportTests(unittest.TestCase):
    def assertValid(self, run, facts, diagnosis, validation, report):
        checked = validate_report(report, run, facts, diagnosis, validation)
        self.assertEqual(checked.status, 'valid', checked.problems)
        return checked

    def test_validated_diagnosis_is_still_labelled_a_hypothesis(self):
        run, facts, diagnosis, validation, report = pipeline()
        self.assertEqual((report.diagnosis_status, report.validation_status), ('diagnosed', 'validated'))
        self.assertEqual(report.hypothesis['label'], HYPOTHESIS_LABEL)
        self.assertNotIn('confirmed root cause', report.headline.replace('not a confirmed root cause', ''))
        self.assertTrue(report.human_review_required)
        self.assertEqual(report.supporting_evidence_ids, diagnosis.supporting_evidence_ids)
        self.assertEqual({s['fact_id'] for s in report.evidence_summary}, set(diagnosis.supporting_fact_ids))
        self.assertTrue(report.official_schema.startswith('outstanding'))
        self.assertValid(run, facts, diagnosis, validation, report)

    def test_warnings_and_rejections_are_preserved_and_prominent(self):
        args = pipeline(root_cause_hypothesis='shipping returns HTTP 503')
        report = args[-1]
        self.assertEqual(report.validation_status, 'rejected')
        self.assertIn('REJECTED', report.headline)
        self.assertEqual(report.rejected_claims[0]['reason'], 'no span or log fact carries this code')
        self.assertTrue(report.escalation_recommended)
        self.assertValid(*args)
        warned = pipeline(confidence_rationale='errors began at 2026-01-02T10:02:00Z')
        self.assertEqual(warned[-1].validation_status, 'validated_with_warnings')
        self.assertEqual(sorted(c['kind'] for c in warned[-1].unverified_claims), ['root_cause', 'timestamp'])
        self.assertValid(*warned)

    def test_escalated_and_error_outcomes(self):
        escalated = pipeline(router=FakeRouter(answer(status='escalated', confidence='low', affected_component=None,
                                                       root_cause_hypothesis=None)))
        report = escalated[-1]
        self.assertEqual((report.diagnosis_status, report.validation_status), ('escalated', 'escalated'))
        self.assertTrue(report.headline.startswith('Escalated'))
        self.assertIsNone(report.hypothesis['text'])
        self.assertValid(*escalated)
        failed = pipeline(router=FakeRouter(error=RuntimeError('provider down')))
        report = failed[-1]
        self.assertEqual((report.diagnosis_status, report.validation_status), ('error', 'technical_error'))
        self.assertIsNone(report.hypothesis)
        self.assertEqual(report.supporting_fact_ids, ())
        self.assertFalse(report.escalation_recommended)
        self.assertValid(*failed)

    def test_missing_partial_and_conflicting_evidence_stay_visible(self):
        partial = call(tools({'opensearch': logs_response(total=500)}), 'search_logs', limit=1)
        data = run_dict([partial, call(tools(), 'search_traces'), call(tools(docker=FakeDocker('exited')), 'container_health'),
                         call(tools(), 'container_health'), call(tools(), 'deployment_history')])
        run, facts, diagnosis, validation, report = pipeline(data)
        self.assertTrue(any('Log limit reached' in w for w in report.validation_warnings))
        self.assertEqual(report.evidence_gaps[0]['limitations'], ['Absence of data is not evidence of health or failure'])
        self.assertEqual(set(report.conflicts[0]['fact_ids_by_value']), {'exited', 'running'})
        self.assertIn('unavailable', {e['status'] for e in report.evidence_status})
        self.assertFalse(report.detector_evidence[0]['evidence_in_run'])
        checked = self.assertValid(run, facts, diagnosis, validation, report)
        self.assertTrue(checked.unverified)

    def test_missing_incident_metadata_is_explicit_not_invented(self):
        data = run_dict([call(tools(), 'search_traces'), call(tools(), 'search_logs')])
        del data['incident']['detected_at']
        data['origin'] = None
        run, facts, diagnosis, validation, report = pipeline(data)
        self.assertIsNone(report.incident['detected_at'])
        self.assertIsNone(report.incident['origin'])
        self.assertValid(run, facts, diagnosis, validation, report)

    def test_inconsistent_inputs_and_unknown_fact_references_are_refused(self):
        run, facts, diagnosis, validation, _ = pipeline()
        with self.assertRaises(ReportInputError):
            build_report(run, facts, replace(diagnosis, incident_id='incident-other'), validation)
        with self.assertRaises(ReportInputError):
            build_report(run, facts, replace(diagnosis, supporting_fact_ids=('fact-unknown',)), validation)
        with self.assertRaises(ReportInputError):
            build_report(run, facts, diagnosis, replace(validation, diagnosis_status='escalated'))

    def test_tampered_reports_are_invalid(self):
        run, facts, diagnosis, validation, report = pipeline(root_cause_hypothesis='shipping returns HTTP 503')
        base = to_dict(report)
        cases = {
            'fact reference': {'supporting_fact_ids': ['fact-0000000000000000']},
            'evidence reference': {'supporting_evidence_ids': ['f02-invented']},
            'status upgrade': {'validation_status': 'validated'},
            'dropped rejection': {'rejected_claims': []},
            'dropped warnings': {'validation_warnings': ['other']},
            'escalation flip': {'escalation_recommended': False},
            'hypothesis label': {'hypothesis': {**base['hypothesis'], 'label': 'Confirmed root cause'}},
            'confidence rewrite': {'hypothesis': {**base['hypothesis'], 'confidence': 'low'}},
            'dropped gaps': {'evidence_gaps': []},
            'incident id': {'incident': {**base['incident'], 'id': 'incident-other'}},
            'fabricated default': {'incident': {**base['incident'], 'detected_at': '2026-01-01T00:00:00Z'}},
            'unexpected field': {'confirmed': True},
        }
        for label, change in cases.items():
            with self.subTest(label):
                checked = validate_report({**base, **change}, run, facts, diagnosis, validation)
                self.assertEqual(checked.status, 'invalid')
        error_args = pipeline(router=FakeRouter(error=RuntimeError('down')))
        forged = {**to_dict(error_args[-1]), 'hypothesis': {'label': HYPOTHESIS_LABEL, 'text': 'invented cause'}}
        self.assertEqual(validate_report(forged, *error_args[:4]).status, 'invalid')

    def test_deterministic_json_round_trip(self):
        first, second = pipeline()[-1], pipeline()[-1]
        self.assertEqual(json.dumps(to_dict(first), sort_keys=True), json.dumps(to_dict(second), sort_keys=True))
        run, facts, diagnosis, validation, report = pipeline()
        loaded = json.loads(json.dumps(to_dict(report)))
        self.assertEqual(validate_report(loaded, run, facts, diagnosis, validation).status, 'valid')

    def test_report_does_not_copy_raw_telemetry(self):
        run, facts, diagnosis, validation, report = pipeline()
        text = json.dumps(to_dict(report))
        self.assertNotIn('resourceSpans', text)
        self.assertNotIn('provenance', text)
        self.assertEqual(report.model, {'model': 'fake-model', 'slot': 'fake', 'backend': 'fake'})


if __name__ == '__main__':
    unittest.main()
