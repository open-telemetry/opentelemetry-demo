"""Virtual-clock regressions for slow inference; no real waiting or provider calls."""
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from incident_tools.eyes.runtime import Router, load
from incident_tools.eyes_acceptance.configuration import initialize, model_probe_budget, readiness
from incident_tools.eyes_acceptance.diagnose import diagnose


class ProbeTimeoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = Path(initialize(Path(self.tmp.name) / "operator", "fixture-cloud-model"))
        self.environment = patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-timeout-test-token"})
        self.environment.start()
        self.now, self.timeouts, self.sleeps = 0.0, [], []

    def tearDown(self):
        self.environment.stop()
        self.tmp.cleanup()

    def configure(self, timeout=60, retries=1, rpm=12):
        cfg = self.file.read_text()
        cfg = cfg.replace("timeout_seconds = 60", "timeout_seconds = " + str(timeout))
        cfg = cfg.replace("retries = 1", "retries = " + str(retries))
        cfg = cfg.replace("requests_per_minute = 12", "requests_per_minute = " + str(rpm))
        self.file.write_text(cfg, encoding="utf-8")

    def probe(self, delays, diagnostic=False):
        delays = iter(delays)
        def opened(req, timeout):
            self.timeouts.append(timeout)
            delay = next(delays)
            if delay is None or delay > timeout:
                self.now += timeout
                raise TimeoutError("synthetic timeout; no network")
            self.now += delay
            return io.BytesIO(json.dumps({"choices": [{"message": {"content": '{"ready":true}'}}]}).encode())
        def sleep(seconds):
            self.sleeps.append(seconds)
            self.now += seconds
        with patch("incident_tools.eyes.runtime.time.monotonic", side_effect=lambda: self.now), patch(
                "incident_tools.eyes.runtime.time.sleep", side_effect=sleep), patch(
                "urllib.request.OpenerDirector.open", side_effect=opened):
            if diagnostic:
                return diagnose(self.file)
            return readiness(self.file, probe_model=True)[0]

    def test_35_second_response_fits_new_default(self):
        cfg, _, _, _ = load(self.file)
        self.assertEqual(cfg["models"]["cloud"]["timeout_seconds"], 60)
        result = self.probe([35])
        self.assertTrue(result["model_configuration_usable"])
        self.assertEqual(result["model_probe"]["model"], "fixture-cloud-model")
        self.assertEqual(result["model_probe_budget_seconds"], 130)
        self.assertEqual(self.timeouts, [60])
        self.assertEqual(self.now, 35)

    def test_90_second_timeout_is_not_clipped_by_old_45_second_budget(self):
        self.configure(timeout=90, retries=0)
        result = self.probe([80])
        self.assertIsNotNone(result["model_probe"])
        self.assertEqual(result["model_probe_budget_seconds"], 95)
        self.assertEqual(self.timeouts, [90])

    def test_retry_receives_full_configured_timeout(self):
        result = self.probe([None, 35])
        self.assertIsNotNone(result["model_probe"])
        self.assertEqual(self.timeouts, [60, 60])
        self.assertEqual(result["model_probe_budget_seconds"], 130)
        self.assertEqual(self.now, 95)

    def test_budget_covers_rate_limit_wait_between_attempts(self):
        self.configure(timeout=1, retries=1, rpm=1)
        def opened(req, timeout):
            self.timeouts.append(timeout)
            if len(self.timeouts) == 1:
                raise TimeoutError("immediate fixture failure")
            self.now += 0.5
            return io.BytesIO(json.dumps({"choices": [{"message": {"content": '{"ready":true}'}}]}).encode())
        def sleep(seconds):
            self.sleeps.append(seconds)
            self.now += seconds
        with patch("incident_tools.eyes.runtime.time.monotonic", side_effect=lambda: self.now), patch(
                "incident_tools.eyes.runtime.time.sleep", side_effect=sleep), patch(
                "urllib.request.OpenerDirector.open", side_effect=opened):
            result = readiness(self.file, probe_model=True)[0]
        self.assertIsNotNone(result["model_probe"])
        self.assertEqual(result["model_probe_budget_seconds"], 67)
        self.assertEqual(self.sleeps, [60])
        self.assertEqual(self.timeouts, [1, 1])

    def test_fallback_budget_keeps_cloud_attempt_after_local_timeouts(self):
        cfg = self.file.read_text().replace('route = "cloud-only"', 'route = "local-first"')
        cfg += '''
[models.local]
enabled = true
backend = "ollama"
endpoint = "http://localhost:11434"
model = "fixture-local-model"
timeout_seconds = 30
retries = 1
requests_per_minute = 6
'''
        self.file.write_text(cfg, encoding="utf-8")
        result = self.probe([None, None, 35])
        self.assertEqual(result["model_probe"]["slot"], "cloud")
        self.assertEqual(result["model_probe_budget_seconds"], 200)
        self.assertEqual(self.timeouts, [30, 30, 60])

    def test_existing_operator_timeout_is_respected_and_not_overwritten(self):
        self.configure(timeout=30)
        before = self.file.read_bytes()
        result = self.probe([35, 35])
        self.assertEqual(result["model_issues"], ["MODEL_PROBE_FAILED"])
        self.assertEqual(self.timeouts, [30, 30])
        self.assertEqual(self.file.read_bytes(), before)

    def test_no_probe_has_no_budget_and_no_inference(self):
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("Unexpected inference")):
            result = readiness(self.file)[0]
        self.assertIsNone(result["model_probe_budget_seconds"])
        self.assertIsNone(result["model_probe"])

    def test_diagnostic_uses_single_attempt_budget_and_allows_slow_response(self):
        result = self.probe([35], diagnostic=True)
        self.assertTrue(result["probe_succeeded"])
        self.assertEqual(result["request_budget_seconds"], 65)
        self.assertEqual(self.timeouts, [60])

    def test_largest_valid_router_configuration_stays_finite(self):
        cfg, _, _, _ = load(self.file)
        models = deepcopy(cfg["models"])
        models["route"] = "local-first"
        models["cloud"].update(timeout_seconds=120, retries=2, requests_per_minute=1)
        models["local"] = {**models["cloud"], "backend": "ollama", "endpoint": "http://localhost:11434"}
        router = Router(models)
        self.assertEqual(model_probe_budget(router), 965)


if __name__ == "__main__":
    unittest.main()
