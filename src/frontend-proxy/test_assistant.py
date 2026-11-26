# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Exercise the rendered proxy configuration with Docker and PyYAML."""

from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template
from tempfile import TemporaryDirectory
from threading import Thread
import json
import os
import re
import socket
import subprocess
import time
import unittest

import yaml


DIRECTORY = Path(__file__).resolve().parent


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def request(port, path, method="POST"):
    connection = HTTPConnection("127.0.0.1", port, timeout=25)
    try:
        connection.request(
            method, path, body='{"message":"Show products"}',
            headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        return response.status, response.read().decode()
    finally:
        connection.close()


class Frontend(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        time.sleep(16)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"reply":"Delayed answer."}')
        except (BrokenPipeError, ConnectionResetError):
            pass  # Envoy closes requests that reach the default route deadline.

    def log_message(self, *_):
        pass


class AssistantProxyTest(unittest.TestCase):
    def test_slow_assistant_answers_survive_the_default_route_timeout(self):
        frontend = ThreadingHTTPServer(("127.0.0.1", 0), Frontend)
        thread = Thread(target=frontend.serve_forever, daemon=True)
        thread.start()
        container = f"frontend-proxy-assistant-test-{os.getpid()}"
        try:
            with TemporaryDirectory() as scratch:
                template = (DIRECTORY / "envoy.tmpl.yaml").read_text()
                variables = {}
                for name in re.findall(r"\$\{(\w+)\}", template):
                    variables[name] = "9" if "PORT" in name else "127.0.0.1"
                proxy_port = free_port()
                variables.update(
                    ENVOY_PORT=str(proxy_port),
                    ENVOY_ADMIN_PORT=str(free_port()),
                    FRONTEND_PORT=str(frontend.server_port),
                    OTEL_SERVICE_NAME="frontend-proxy-test",
                    OTEL_SERVICE_NAMESPACE="test")
                config = Path(scratch) / "envoy.json"
                config.write_text(json.dumps(yaml.safe_load(Template(template).substitute(variables))))
                image = re.search(r"^FROM (\S+)", (DIRECTORY / "Dockerfile").read_text(), re.M)[1]
                subprocess.run(
                    ["docker", "run", "--detach", "--rm", "--name", container,
                        "--network", "host", "--mount",
                        f"type=bind,source={config},target=/etc/envoy/test.json,readonly",
                        image, "-c", "/etc/envoy/test.json", "--concurrency", "1",
                        "--disable-hot-restart", "--log-level", "error"],
                    check=True, capture_output=True, timeout=180)
                try:
                    deadline = time.monotonic() + 20
                    while True:
                        try:
                            if request(proxy_port, "/ready", "GET")[0] == 200:
                                break
                        except OSError:
                            pass
                        if time.monotonic() > deadline:
                            self.fail("Envoy did not become ready")
                        time.sleep(0.1)

                    paths = [
                        "/api/assistant", "/api/assistant?test=1",
                        "/api/products", "/api/assistant-other"]
                    with ThreadPoolExecutor(max_workers=4) as pool:
                        results = dict(zip(paths, pool.map(lambda path: request(proxy_port, path), paths)))
                    print(json.dumps(results), flush=True)
                    for path in paths[:2]:
                        status, body = results[path]
                        self.assertEqual(status, 200, f"{path}: {body}")
                        self.assertEqual(json.loads(body), {"reply": "Delayed answer."})
                    for path in paths[2:]:
                        self.assertEqual(results[path], (504, "upstream request timeout"))
                finally:
                    subprocess.run(
                        ["docker", "rm", "--force", container],
                        check=True, capture_output=True, timeout=15)
        finally:
            frontend.shutdown()
            frontend.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
