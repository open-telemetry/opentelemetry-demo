"""No network, Docker, inference or practice mutations: all inputs are synthetic."""
from contextlib import nullcontext
from copy import deepcopy
from datetime import timedelta
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from incident_tools.eyes.core import Store
from incident_tools.eyes.runtime import DEFAULTS
from incident_tools.eyes.tests.test_eyes import FakeTools, AdaptiveModel
from incident_tools.eyes_acceptance.configuration import initialize, readiness, PLACEHOLDER
from incident_tools.eyes_acceptance.practice import Docker, Practice, reset, watchdog, write_json
from incident_tools.eyes_acceptance.workflow import EvidenceModel, execute, assess, sketch


class FixtureModel(AdaptiveModel):
    public_configuration = {"route": "fixture", "providers": {"fixture": {"model": "fixture-model"}}}

    def decide(self, messages, remaining):
        choice, identity = super().decide(messages, remaining)
        identity["backend"] = "fixture"
        if choice["action"] == "tool" and len(self.calls) > 1:
            choice["based_on_evidence_ids"] = [json.loads(messages[-1]["content"])["evidence_id"]]
        return choice, identity


class FixturePractice:
    def __init__(self, tools):
        self.tools, self.starts, self.resets = tools, 0, 0
        self.started_at = None
        self.fail_reset = False

    def start(self):
        self.starts += 1
        self.started_at = self.tools.now.timestamp()
        self.tools.value = 1500

    def reset(self):
        self.resets += 1
        if self.fail_reset:
            raise RuntimeError("fixture reset failure")
        self.tools.value = 500
        return {"status": "reset_verified", "paused_at": self.started_at, "reset_at": self.tools.now.timestamp()}


def fixture_run(directory, configure=None, detect_only=False):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    tools, model = FakeTools(), FixtureModel()
    tools.value = 500
    practice = FixturePractice(tools)
    settings = {**DEFAULTS, "services": ["checkout"], "warmup_seconds": 1,
                "thresholds": {"latency_p95_ms": 1000}}
    if configure:
        configure(tools, model, practice)
    store = Store(directory / "evidence")
    def sleep(seconds):
        tools.now += timedelta(seconds=seconds)
    try:
        result = execute(tools, settings, store, model, practice, directory,
                         duration=90, baseline_seconds=45, detect_only=detect_only,
                         clock=lambda: tools.now, sleep=sleep)
        incidents = deepcopy(store.incidents())
    finally:
        store.db.close()
    return result, tools, model, practice, incidents


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_complete_fixture_detects_once_and_records_explicit_dependency(self):
        result, tools, model, practice, incidents = fixture_run(self.path)
        checks = result["checks"]
        self.assertFalse(result["automated_checks_passed"])
        self.assertFalse(result["live_acceptance_complete"])
        self.assertFalse(checks["real_backend_evidence"])
        self.assertTrue(all(v for k, v in checks.items() if k != "real_backend_evidence"), checks)
        self.assertEqual((practice.starts, practice.resets, len(incidents)), (1, 1, 1))
        self.assertEqual(len(model.calls), 3)
        self.assertNotIn("operator-injected-cause", json.dumps(model.calls))
        self.assertNotIn("practice.json", json.dumps(model.calls))
        report = json.loads((self.path / "report/checkpoint1_execution_log.json").read_text())
        self.assertTrue(report["decisions"][1]["decision"]["based_on_evidence_ids"])
        ET.parse(self.path / "report/checkpoint1_architecture.svg")
        for alert in incidents[0]["alerts"]:
            for field in ("evidence_id", "coverage_evidence_id", "freshness_evidence_id"):
                self.assertTrue((self.path / "evidence" / (alert[field] + ".json")).is_file())

    def test_missing_stale_and_low_volume_baselines_never_inject(self):
        for field, value in (("metric_status", "no_data"), ("source_age", 300), ("rate", 0.001)):
            with self.subTest(field=field):
                result, _, model, practice, _ = fixture_run(
                    self.path / field, lambda t, m, p: setattr(t, field, value))
                self.assertEqual(result["failure"], "BASELINE_NOT_ESTABLISHED")
                self.assertEqual(practice.starts, 0)
                self.assertEqual(model.calls, [])

    def test_existing_breach_never_injects(self):
        result, _, _, practice, _ = fixture_run(self.path, lambda t, m, p: setattr(t, "value", 1500))
        self.assertEqual(result["failure"], "BASELINE_ALREADY_BREACHING")
        self.assertEqual(practice.starts, 0)

    def test_no_breach_still_resets_without_manually_creating_incident(self):
        def configure(t, m, p):
            p.start = lambda: None
        result, _, model, practice, incidents = fixture_run(self.path, configure)
        self.assertEqual(result["failure"], "NO_SUSTAINED_BREACH_DETECTED")
        self.assertEqual(practice.resets, 1)
        self.assertEqual(incidents, [])
        self.assertEqual(model.calls, [])

    def test_reset_failure_blocks_investigation_and_success(self):
        result, _, model, practice, _ = fixture_run(self.path, lambda t, m, p: setattr(p, "fail_reset", True))
        self.assertEqual(result["failure"], "RESET_NOT_VERIFIED")
        self.assertFalse(result["checks"]["practice_reset_verified"])
        self.assertEqual(model.calls, [])

    def test_interrupt_during_injection_still_resets(self):
        def configure(t, m, p):
            def interrupted():
                raise KeyboardInterrupt()
            p.start = interrupted
        result, _, _, practice, _ = fixture_run(self.path, configure)
        self.assertEqual(result["failure"], "KeyboardInterrupt")
        self.assertEqual(practice.resets, 1)

    def test_detection_only_never_calls_model_or_claims_f03(self):
        result, _, model, practice, incidents = fixture_run(self.path, detect_only=True)
        self.assertEqual(len(incidents), 1)
        self.assertEqual(practice.resets, 1)
        self.assertEqual(model.calls, [])
        self.assertFalse(result["checks"]["investigation_finished"])

    def test_provider_failure_preserves_incident_and_reset(self):
        def configure(t, m, p):
            m.decide = lambda *args: (_ for _ in ()).throw(RuntimeError("synthetic-secret-not-for-report"))
        result, _, _, practice, incidents = fixture_run(self.path, configure)
        self.assertEqual(practice.resets, 1)
        self.assertEqual(incidents[0]["investigation"], "incomplete")
        self.assertFalse(result["checks"]["investigation_finished"])
        self.assertNotIn("synthetic-secret-not-for-report", (self.path / "report/checkpoint1_execution_log.json").read_text())

    def test_dependency_must_reference_actual_prior_observations(self):
        class Model:
            public_configuration = {}
            def decide(self, messages, remaining):
                return {"action": "tool", "based_on_evidence_ids": self.refs}, {}
        model = Model()
        wrapper = EvidenceModel(model)
        messages = [{"role": "system", "content": ""}, {"role": "user", "content": "{}"},
                    {"role": "user", "content": json.dumps({"evidence_id": "real", "status": "ok", "observations": [1]})}]
        for refs in ([], ["invented"], "real"):
            model.refs = refs
            with self.assertRaises(ValueError):
                wrapper.decide(messages, 10)
        model.refs = ["real"]
        self.assertEqual(wrapper.decide(messages, 10)[0]["based_on_evidence_ids"], ["real"])

    def test_two_calls_without_explicit_reference_cannot_pass(self):
        fixture_run(self.path)
        run = json.loads((self.path / "report/checkpoint1_execution_log.json").read_text())
        run["decisions"][1]["decision"].pop("based_on_evidence_ids")
        result = assess(run, [], [], {"status": "reset_verified"}, "fixture")
        self.assertFalse(result["checks"]["two_successful_queries_with_explicit_dependency"])


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "operator"

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_is_predictable_valid_and_never_overwrites(self):
        file = initialize(self.path, opensearch="http://localhost:19200")
        result, tools, settings, router = readiness(file)
        self.assertEqual(settings["services"], ["checkout"])
        self.assertEqual(tools.config.endpoint("opensearch"), "http://localhost:19200")
        self.assertIn("SET_CLOUD_MODEL_ID", result["model_issues"])
        self.assertIsNone(router)
        before = Path(file).read_bytes()
        with self.assertRaises(FileExistsError):
            initialize(self.path)
        self.assertEqual(Path(file).read_bytes(), before)

    def test_missing_key_is_actionable_without_network_calls(self):
        file = initialize(self.path, "operator-selected-model")
        with patch.dict("os.environ", {}, clear=True), patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("network")):
            result, _, _, _ = readiness(file)
        self.assertEqual(result["model_issues"], ["MISSING_CLOUD_ENVIRONMENT_KEY"])
        self.assertFalse(result["live_probes_executed"])
        self.assertIsNone(result["model_probe"])

    def test_configured_key_is_never_serialized(self):
        file = initialize(self.path, "operator-selected-model")
        with patch.dict("os.environ", {"GEMINI_API_KEY": "synthetic-only-secret"}):
            result, tools, _, router = readiness(file)
        self.assertTrue(result["model_configuration_usable"])
        self.assertNotIn("synthetic-only-secret", json.dumps(result))
        self.assertNotIn("synthetic-only-secret", Path(file).read_text())
        self.assertEqual(tools.config.clean("synthetic-only-secret"), "[REDACTED]")
        self.assertIsNotNone(router)

    def test_explicit_model_probe_records_provider_identity(self):
        file = initialize(self.path, "operator-selected-model")
        body = io.BytesIO(json.dumps({"choices": [{"message": {"content": '{"ready":true}'}}]}).encode())
        with patch.dict("os.environ", {"GEMINI_API_KEY": "synthetic-only-secret"}), patch(
                "urllib.request.OpenerDirector.open", return_value=body) as opened:
            result, _, _, _ = readiness(file, probe_model=True)
        self.assertEqual(opened.call_count, 1)
        self.assertEqual(result["model_probe"]["model"], "operator-selected-model")
        self.assertNotIn("synthetic-only-secret", json.dumps(result))

    def test_live_probe_failures_block_readiness(self):
        file = initialize(self.path, "operator-selected-model")
        with patch("incident_tools.f02.ObservabilityTools.call", return_value={
                "status": "no_data", "observations": []}):
            result, _, _, _ = readiness(file, live=True)
        self.assertFalse(result["configuration_usable"])
        self.assertIn("NO_USABLE_SEARCH_TRACES", result["issues"])


class FakeDocker(Docker):
    def __init__(self):
        self.endpoint = "unix:///var/run/docker.sock"
        self.state = {"id": "a" * 64, "running": True, "paused": False, "restarting": False,
                      "project": "opentelemetry-demo", "service": "shipping"}
        self.calls, self.fail_pause, self.fail_unpause = [], False, False

    def command(self, args, pin=True):
        self.calls.append(args)
        if args[0] == "ps":
            return "a" * 64
        if args[0] == "inspect":
            return "|".join(json.dumps(self.state[k]) for k in ("id", "running", "paused", "restarting", "project", "service"))
        if args[0] == "pause":
            self.state["paused"] = True
            if self.fail_pause:
                raise RuntimeError("ambiguous pause response")
        elif args[0] == "unpause":
            if self.fail_unpause:
                raise RuntimeError("reset unavailable")
            self.state["paused"] = False
        return ""


class PracticeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.journal = Path(self.tmp.name) / "practice.json"
        self.docker = FakeDocker()
        self.locker = patch("incident_tools.eyes_acceptance.practice.locked", lambda _: nullcontext())
        self.locker.start()

    def tearDown(self):
        self.locker.stop()
        self.tmp.cleanup()

    def armed(self, status="paused"):
        record = {"container": "a" * 64, "project": "opentelemetry-demo", "service": "shipping",
                  "endpoint": self.docker.endpoint, "status": status, "deadline": 0}
        write_json(self.journal, record)
        return record

    def spawn(self, *args, **kwargs):
        Path(str(self.journal) + ".ready").write_text("ready")
        class Child:
            def poll(self):
                return None
        return Child()

    def test_invalid_duration_never_contacts_docker(self):
        for seconds in (-1, 0, 601, True):
            with self.assertRaises(ValueError):
                Practice(self.journal, "opentelemetry-demo", seconds, self.docker)
        self.assertEqual(self.docker.calls, [])

    def test_prepaused_stopped_wrong_scope_rejected(self):
        for field, value in (("paused", True), ("running", False), ("project", "other"), ("service", "payment")):
            old = self.docker.state[field]
            self.docker.state[field] = value
            with self.assertRaises(ValueError):
                Practice(self.journal, "opentelemetry-demo", docker=self.docker)
            self.docker.state[field] = old
        self.assertFalse(any(c[0] in ("pause", "unpause") for c in self.docker.calls))

    def test_watchdog_prearmed_before_pause_and_exact_reset(self):
        practice = Practice(self.journal, "opentelemetry-demo", docker=self.docker)
        with patch("subprocess.Popen", side_effect=self.spawn) as spawned:
            practice.start()
        self.assertTrue(spawned.call_args.kwargs["start_new_session"])
        self.assertTrue(self.docker.state["paused"])
        record = practice.reset()
        self.assertEqual(record["status"], "reset_verified")
        self.assertIn(["unpause", "a" * 64], self.docker.calls)
        self.assertFalse(self.docker.state["paused"])

    def test_guard_failure_prevents_pause(self):
        practice = Practice(self.journal, "opentelemetry-demo", docker=self.docker)
        with patch("subprocess.Popen", side_effect=OSError("fixture spawn failure")):
            with self.assertRaises(OSError):
                practice.start()
        self.assertFalse(any(c[0] == "pause" for c in self.docker.calls))
        self.assertEqual(json.loads(self.journal.read_text())["status"], "cancelled_before_pause")

    def test_ambiguous_pause_result_is_reset(self):
        self.docker.fail_pause = True
        practice = Practice(self.journal, "opentelemetry-demo", docker=self.docker)
        with patch("subprocess.Popen", side_effect=self.spawn):
            with self.assertRaises(RuntimeError):
                practice.start()
        self.assertFalse(self.docker.state["paused"])
        self.assertEqual(json.loads(self.journal.read_text())["status"], "reset_verified")

    def test_replaced_container_is_not_unpaused(self):
        self.armed()
        self.docker.state.update(id="b" * 64, paused=True)
        with self.assertRaises(RuntimeError):
            reset(self.journal, self.docker)
        self.assertFalse(any(c[0] == "unpause" for c in self.docker.calls))
        self.assertEqual(json.loads(self.journal.read_text())["status"], "reset_failed")

    def test_reset_failure_is_not_success(self):
        self.armed()
        self.docker.state["paused"], self.docker.fail_unpause = True, True
        with self.assertRaises(RuntimeError):
            reset(self.journal, self.docker)
        self.assertEqual(json.loads(self.journal.read_text())["status"], "reset_failed")

    def test_watchdog_deadline_resets_without_parent(self):
        self.armed()
        self.docker.state["paused"] = True
        with patch("incident_tools.eyes_acceptance.practice.Docker", return_value=self.docker):
            self.assertEqual(watchdog(self.journal), 0)
        self.assertFalse(self.docker.state["paused"])
        self.assertEqual(json.loads(self.journal.read_text())["status"], "reset_verified")

    def test_watchdog_exhausted_retries_reports_failure(self):
        self.armed()
        self.docker.state["paused"], self.docker.fail_unpause = True, True
        with patch("incident_tools.eyes_acceptance.practice.Docker", return_value=self.docker), patch(
                "incident_tools.eyes_acceptance.practice.time.sleep"):
            self.assertEqual(watchdog(self.journal), 1)
        self.assertEqual(json.loads(self.journal.read_text())["status"], "reset_failed")


if __name__ == "__main__":
    unittest.main()
