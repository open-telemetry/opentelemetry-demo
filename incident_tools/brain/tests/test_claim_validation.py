"""Brain stage 3 tests. Offline, SYNTHETIC data from real F02 code over fake transports."""
from dataclasses import replace
import unittest

from incident_tools.brain import diagnose
from incident_tools.brain.claim_validation import validate_claims
from test_brain import FakeDocker, call, logs_response, run_dict, tools
from test_diagnosis import FakeRouter, answer, setup


def verdicts(result, kind):
    return [c.verdict for c in result.claims if c.kind == kind]


class ClaimValidationTests(unittest.TestCase):
    def setUp(self):
        self.run, self.facts, self.ids = setup()
        self.support = self.ids['span'] + self.ids['log_entry']
        self.base = diagnose(self.run, self.facts, FakeRouter(answer(
            affected_component='shipping', supporting_fact_ids=self.support,
            root_cause_hypothesis='Checkout calls to shipping GetQuote fail with grpc status 4 after 4000 ms',
            confidence_rationale='The checkout log says "context deadline exceeded" at 2026-01-02T10:04:00Z')))
        self.assertEqual(self.base.status, 'diagnosed')

    def check(self, **changes):
        return validate_claims(replace(self.base, **changes), self.facts, self.run)

    def test_valid_diagnosis_with_grounded_claims(self):
        result = validate_claims(self.base, self.facts, self.run)
        self.assertEqual(result.status, 'validated')
        self.assertFalse(result.escalation_recommended)
        self.assertEqual(verdicts(result, 'component'), ['consistent'])
        for kind in ('metric_value', 'quotation', 'timestamp', 'status_code'):
            self.assertEqual(verdicts(result, kind), ['observed'], kind)
        self.assertEqual(verdicts(result, 'root_cause'), ['unverified'])
        self.assertEqual(result.supporting_evidence_ids, self.base.supporting_evidence_ids)

    def test_diagnosis_is_never_modified(self):
        before = replace(self.base)
        validate_claims(self.base, self.facts, self.run)
        self.assertEqual(self.base, before)

    def test_unknown_and_evidence_ids_as_fact_ids_are_rejected(self):
        evidence_id = next(iter(self.run.evidence))
        for ref, reason in (('fact-0000000000000000', 'unknown fact id'), (evidence_id, 'evidence id used as fact id')):
            with self.subTest(ref=ref):
                result = self.check(supporting_fact_ids=self.base.supporting_fact_ids + (ref,))
                self.assertEqual(result.status, 'rejected')
                self.assertIn(reason, [c.reason for c in result.rejected][0])
        self.assertEqual(self.check(contradicting_fact_ids=('fact-x',)).status, 'rejected')

    def test_tampered_provenance_is_rejected(self):
        result = self.check(supporting_evidence_ids=('f02-invented',))
        self.assertEqual(verdicts(result, 'provenance'), ['contradicted'])
        self.assertEqual(result.status, 'rejected')

    def test_invented_value_and_wrong_unit(self):
        invented = self.check(root_cause_hypothesis='GetQuote takes 2500 ms')
        self.assertEqual(verdicts(invented, 'metric_value'), ['unsupported'])
        self.assertEqual(invented.status, 'rejected')
        wrong = self.check(root_cause_hypothesis='GetQuote takes 4000 s')
        self.assertEqual(verdicts(wrong, 'metric_value'), ['contradicted'])
        converted = self.check(root_cause_hypothesis='GetQuote takes 4 seconds')
        self.assertEqual(verdicts(converted, 'metric_value'), ['unverified'])
        self.assertNotEqual(converted.status, 'rejected')

    def test_alert_threshold_carries_the_metric_unit(self):
        rationale = 'p95 1500 ms exceeds the 1000 ms threshold'
        uncited = self.check(root_cause_hypothesis='', confidence_rationale=rationale)
        self.assertEqual(verdicts(uncited, 'metric_value'), ['unverified', 'unverified'])
        alert = tuple(self.ids['alert'])
        cited = self.check(root_cause_hypothesis='', confidence_rationale=rationale,
                           supporting_fact_ids=self.base.supporting_fact_ids + alert,
                           supporting_evidence_ids=tuple(dict.fromkeys(self.base.supporting_evidence_ids + tuple(
                               e for f in self.facts if f.fact_id in alert for e in f.evidence_ids))))
        self.assertEqual(verdicts(cited, 'metric_value'), ['observed', 'observed'])

    def test_unsupported_component(self):
        result = self.check(affected_component='payment')
        self.assertEqual(verdicts(result, 'component'), ['unsupported'])
        self.assertTrue(result.escalation_recommended)

    def test_timestamps_inside_outside_and_observed(self):
        outside = self.check(confidence_rationale='errors began at 2026-01-02T11:00:00Z')
        self.assertEqual(verdicts(outside, 'timestamp'), ['contradicted'])
        inside = self.check(confidence_rationale='errors began at 2026-01-02T10:02:00Z')
        self.assertEqual(verdicts(inside, 'timestamp'), ['unverified'])
        self.assertEqual(inside.status, 'validated_with_warnings')

    def test_fabricated_quotation(self):
        result = self.check(confidence_rationale='The log says "connection refused by shipping"')
        self.assertEqual(verdicts(result, 'quotation'), ['unsupported'])
        self.assertEqual(result.status, 'rejected')

    def test_unsupported_error_code(self):
        result = self.check(root_cause_hypothesis='shipping returns HTTP 503')
        self.assertEqual(verdicts(result, 'status_code'), ['unsupported'])
        self.assertEqual(result.status, 'rejected')

    def test_conflicting_and_unobserved_container_states(self):
        data = run_dict([call(tools(docker=FakeDocker('exited')), 'container_health'),
                         call(tools(), 'container_health'), call(tools(), 'search_traces')])
        run, facts, ids = setup(data)
        running = next(f.fact_id for f in facts if f.type == 'container_state' and f.value == 'running')
        diagnosis = diagnose(run, facts, FakeRouter(answer(
            affected_component='checkout', supporting_fact_ids=[running] + ids['span'],
            root_cause_hypothesis='The checkout container is paused')))
        result = validate_claims(diagnosis, facts, run)
        self.assertTrue(any('conflicting container state exited' in w for w in result.warnings))
        self.assertEqual(verdicts(result, 'container_state'), ['unsupported'])
        exited = validate_claims(replace(diagnosis, root_cause_hypothesis='checkout exited'), facts, run)
        self.assertEqual(verdicts(exited, 'container_state'), ['observed'])

    def test_shared_trace_is_not_causal_evidence(self):
        result = self.check(supporting_fact_ids=tuple(self.ids['log_trace_link']), supporting_evidence_ids=tuple(
            e for f in self.facts if f.type == 'log_trace_link' for e in f.evidence_ids))
        component = [c for c in result.claims if c.kind == 'component'][0]
        self.assertEqual(component.verdict, 'unsupported')
        self.assertIn('shared trace', component.reason)

    def test_temporal_overlap_is_not_dependency_evidence(self):
        logs = tuple(self.ids['log_entry'])
        result = self.check(supporting_fact_ids=logs, supporting_evidence_ids=tuple(
            e for f in self.facts if f.fact_id in logs for e in f.evidence_ids))
        component = [c for c in result.claims if c.kind == 'component'][0]
        self.assertEqual(component.verdict, 'unsupported')
        self.assertIn('co-occur', component.reason)

    def test_metric_only_causal_claim_stays_unverified_and_escalates(self):
        metrics = tuple(self.ids['metric_series'])
        result = self.check(affected_component='checkout', supporting_fact_ids=metrics, supporting_evidence_ids=tuple(
            e for f in self.facts if f.fact_id in metrics for e in f.evidence_ids),
            root_cause_hypothesis='High latency is caused by a slow dependency')
        self.assertEqual(verdicts(result, 'component'), ['observed'])
        self.assertEqual(verdicts(result, 'root_cause'), ['unverified'])
        self.assertTrue(result.escalation_recommended)
        self.assertEqual(result.status, 'validated_with_warnings')

    def test_gap_partial_and_failed_evidence(self):
        gaps = tuple(self.ids['evidence_gap'])
        result = self.check(supporting_fact_ids=self.base.supporting_fact_ids + gaps, supporting_evidence_ids=tuple(
            dict.fromkeys(self.base.supporting_evidence_ids + tuple(e for f in self.facts if f.fact_id in gaps
                                                                    for e in f.evidence_ids))))
        self.assertIn('unsupported', verdicts(result, 'evidence'))
        self.assertEqual(result.status, 'rejected')
        partial = call(tools({'opensearch': logs_response(total=500)}), 'search_logs', limit=1)
        run, facts, ids = setup(run_dict([partial, call(tools(), 'search_traces')]))
        diagnosis = diagnose(run, facts, FakeRouter(answer(affected_component='shipping',
                                                           supporting_fact_ids=ids['log_entry'] + ids['span'])))
        checked = validate_claims(diagnosis, facts, run)
        self.assertTrue(any('Log limit reached' in w for w in checked.warnings))
        self.assertEqual(checked.status, 'validated_with_warnings')

    def test_escalated_and_error_outcomes_stay_distinct(self):
        escalated = diagnose(self.run, self.facts, FakeRouter(answer(status='escalated', confidence='low',
                                                                     affected_component=None, root_cause_hypothesis=None)))
        result = validate_claims(escalated, self.facts, self.run)
        self.assertEqual((result.status, result.escalation_recommended), ('escalated', True))
        error = diagnose(self.run, self.facts, FakeRouter(error=RuntimeError('down')))
        failed = validate_claims(error, self.facts, self.run)
        self.assertEqual((failed.status, failed.escalation_recommended, failed.claims), ('technical_error', False, ()))

    def test_uncheckable_claims_remain_unverified_not_false(self):
        result = self.check(root_cause_hypothesis='Shipping is overwhelmed by queued work',
                            confidence_rationale='Error rate is 5 percent')
        self.assertEqual(verdicts(result, 'metric_value'), ['unverified'])
        self.assertEqual(verdicts(result, 'root_cause'), ['unverified'])
        self.assertNotEqual(result.status, 'rejected')


if __name__ == '__main__':
    unittest.main()
