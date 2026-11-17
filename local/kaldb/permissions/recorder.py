"""Observe real KalDB requests; keep test control on its own private interface."""

from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import socket
import threading
import urllib.error
import urllib.request
import uuid

lock = threading.Lock()
calls = 0
recent = deque(maxlen=20)
UPSTREAM = os.environ.get("KALDB_URL", "http://kaldb:8081")
HOP = {"host", "connection", "content-length", "transfer-encoding", "accept-encoding"}


class Forward(BaseHTTPRequestHandler):
    """Record attempts, then forward to the actual KalDB query service."""

    def log_message(self, *args):
        pass

    def forward(self):
        global calls
        length = int(self.headers.get("Content-Length", 0))
        if length > 2 * 1024 * 1024:
            self.send_error(413)
            return
        body = self.rfile.read(length)
        request_id = str(uuid.uuid4())
        with lock:
            calls += 1
            entry = {"id": request_id, "method": self.command, "status": None}
            recent.append(entry)
        headers = {key: value for key, value in self.headers.items() if key.lower() not in HOP}
        headers["Accept-Encoding"] = "identity"
        headers["X-Request-ID"] = request_id
        request = urllib.request.Request(UPSTREAM + self.path, data=body if body else None,
                                         headers=headers, method=self.command)
        try:
            response = urllib.request.urlopen(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        except (urllib.error.URLError, TimeoutError):
            entry["status"] = 502
            self.send_error(502, "KalDB upstream unavailable")
            return
        with response:
            payload = response.read()
            entry["status"] = response.status
            self.send_response(response.status)
            self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Request-ID", request_id)
            self.end_headers()
            self.wfile.write(payload)

    do_GET = do_POST = do_HEAD = forward


class Control(BaseHTTPRequestHandler):
    """Expose sanitized counters only to the private verification network."""

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path != "/__test__/calls":
            self.send_error(404)
            return
        with lock:
            payload = json.dumps({"count": calls, "recent": list(recent)}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    address = socket.gethostbyname("recorder-control")
    threading.Thread(target=ThreadingHTTPServer((address, 8089), Control).serve_forever, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 8080), Forward).serve_forever()
