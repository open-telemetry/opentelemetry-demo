"""Synthetic probe failures; no real model key or network is used."""
import io
import json
import os
from pathlib import Path
import socket
import ssl
import tempfile
import unittest
from unittest.mock import patch
from urllib import error

from incident_tools.eyes_acceptance.configuration import initialize
from incident_tools.eyes_acceptance.diagnose import diagnose, main, response_metadata

SECRET = "synthetic-probe-key-never-log-this"


class Response(io.BytesIO):
    status = 200


def completion(content='{"ready":true}', finish="stop"):
    return Response(json.dumps({"choices": [{"message": {"content": content}, "finish_reason": finish}]}).encode())


class DiagnoseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = initialize(Path(self.tmp.name) / "operator", "gemini-3.8-flash")
        self.environment = patch.dict(os.environ, {"GEMINI_API_KEY": SECRET})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.tmp.cleanup()

    def run_probe(self, response=None, failure=None):
        with patch("urllib.request.OpenerDirector.open", side_effect=failure,
                   return_value=response) as opened:
            result = diagnose(self.config)
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertFalse(result["telemetry_queried"])
        self.assertFalse(result["practice_fault_executed"])
        return result, opened

    def test_exact_probe_and_model_success_no_extra_retry(self):
        result, opened = self.run_probe(completion())
        self.assertTrue(result["probe_succeeded"])
        self.assertEqual(result["attempts"][0]["http_status"], 200)
        self.assertTrue(result["attempts"][0]["content_json_valid"])
        self.assertTrue(result["gemini_endpoint_matches"])
        self.assertEqual(result["request_budget_seconds"], 65)
        self.assertEqual(opened.call_count, 1)
        payload = json.loads(opened.call_args.args[0].data)
        self.assertEqual(payload["model"], "gemini-3.8-flash")
        self.assertEqual(payload["messages"][0]["content"], 'Return exactly the JSON object {"ready":true}. No markdown.')
        self.assertEqual(result["model_configuration"]["providers"]["cloud"]["retries"], 0)
        self.assertEqual(result["model_probe"]["model"], "gemini-3.8-flash")

    def test_http_failures_report_status_without_body_or_exception(self):
        for status in (400, 401, 403, 404, 429, 500):
            body = io.BytesIO(SECRET.encode())
            failure = error.HTTPError("https://example.invalid/" + SECRET, status, SECRET, {}, body)
            result, opened = self.run_probe(failure=failure)
            self.assertEqual(result["category"], "http_error")
            self.assertEqual(result["attempts"][0]["http_status"], status)
            self.assertEqual(opened.call_count, 1)
            self.assertTrue(body.closed)

    def test_network_failures_are_classified_without_exception_text(self):
        failures = [
            (error.URLError(TimeoutError(SECRET)), "timeout"),
            (TimeoutError(SECRET), "timeout"),
            (error.URLError(ssl.SSLCertVerificationError(1, SECRET)), "tls_certificate_verification_failed"),
            (error.URLError(ssl.SSLError(1, SECRET)), "tls_error"),
            (error.URLError(socket.gaierror(-2, SECRET)), "dns_error"),
            (error.URLError(ConnectionRefusedError(SECRET)), "connection_refused"),
            (error.URLError(SECRET), "network_error"),
        ]
        for failure, expected in failures:
            result, opened = self.run_probe(failure=failure)
            self.assertEqual(result["category"], expected)
            self.assertEqual(result["attempts"][0]["phase"], "connection_or_headers")
            self.assertEqual(opened.call_count, 1)

    def test_valid_http_but_non_json_model_content(self):
        result, _ = self.run_probe(completion("Not JSON " + SECRET))
        self.assertEqual(result["category"], "content_not_json")
        self.assertEqual(result["attempts"][0]["http_status"], 200)
        self.assertFalse(result["probe_succeeded"])

    def test_finish_reason_length_reveals_truncated_output(self):
        result, _ = self.run_probe(completion('{"ready":', "length"))
        self.assertEqual(result["category"], "content_not_json")
        self.assertEqual(result["attempts"][0]["finish_reason"], "length")

    def test_bad_http_json_and_schema_are_distinguished(self):
        result, _ = self.run_probe(Response(("<html>" + SECRET).encode()))
        self.assertEqual(result["category"], "response_json_invalid")
        result, _ = self.run_probe(Response(json.dumps({"error": {"message": SECRET}}).encode()))
        self.assertEqual(result["category"], "response_schema_invalid")

    def test_wrong_json_value_is_not_a_successful_probe(self):
        result, _ = self.run_probe(completion('{"ready":false}'))
        self.assertEqual(result["category"], "unexpected_probe_content")
        self.assertFalse(result["probe_succeeded"])

    def test_body_read_timeout_is_identified(self):
        class BrokenResponse(Response):
            def read(self, size):
                raise TimeoutError(SECRET)
        result, _ = self.run_probe(BrokenResponse())
        self.assertEqual(result["category"], "timeout")
        self.assertEqual(result["attempts"][0]["phase"], "response_body")

    def test_missing_key_never_makes_request(self):
        with patch.dict(os.environ, {}, clear=True):
            result, opened = self.run_probe(completion())
        self.assertEqual(result["category"], "configuration_error")
        self.assertEqual(opened.call_count, 0)

    def test_whitespace_key_flag_never_prints_key(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": " " + SECRET + " "}):
            result, _ = self.run_probe(failure=error.URLError("authentication " + SECRET))
        self.assertTrue(result["environment_key_has_outer_whitespace"])

    def test_wrong_endpoint_is_visible_without_printing_url_credentials(self):
        file = Path(self.config)
        file.write_text(file.read_text().replace('/v1beta/openai"', '/v1beta"'), encoding="utf-8")
        result, _ = self.run_probe(failure=error.URLError(SECRET))
        self.assertFalse(result["gemini_endpoint_matches"])

    def test_oversized_response_is_classified(self):
        result, _ = self.run_probe(Response(b"x" * 262145))
        self.assertEqual(result["category"], "response_too_large")

    def test_provider_metadata_and_response_content_are_not_logged(self):
        metadata = response_metadata(json.dumps({"choices": [{"message": {
            "content": json.dumps({"secret": SECRET}), "extra_content": {"private": SECRET}},
            "finish_reason": SECRET}]}).encode(), "openai-compatible")
        self.assertNotIn(SECRET, json.dumps(metadata))
        self.assertEqual(metadata["finish_reason"], "other")

    def test_cli_failure_is_safe_and_has_nonzero_exit(self):
        with patch("urllib.request.OpenerDirector.open", side_effect=error.URLError(SECRET)), patch(
                "sys.stdout", new_callable=io.StringIO) as output:
            code = main(["--config", self.config])
        self.assertEqual(code, 2)
        self.assertNotIn(SECRET, output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["category"], "network_error")


if __name__ == "__main__":
    unittest.main()
