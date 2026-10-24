# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Dual-mode transport: HTTP API (live) and direct file (offline)."""

import json
import urllib.error
import urllib.request
from pathlib import Path

from . import flags

_DEFAULT_API_URL = "http://localhost:8080/feature/api"
_CONNECT_TIMEOUT = 1.5  # seconds


class HttpTransport:
    """Communicate with flagd-ui via its REST API."""

    def __init__(self, base_url=_DEFAULT_API_URL):
        self.base_url = base_url.rstrip("/")

    def read(self):
        url = f"{self.base_url}/read"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=_CONNECT_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return {"flags": body.get("flags", {})}

    def write(self, config):
        url = f"{self.base_url}/write"
        payload = json.dumps({"data": config}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()

    @staticmethod
    def is_available(base_url=_DEFAULT_API_URL):
        try:
            url = f"{base_url.rstrip('/')}/read"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=_CONNECT_TIMEOUT):
                return True
        except (urllib.error.URLError, OSError):
            return False


class FileTransport:
    """Read and write the flagd JSON file directly on disk."""

    def __init__(self, path=None):
        self.path = Path(path) if path else flags.DEFAULT_FLAG_FILE

    def read(self):
        return flags.load_config(self.path)

    def write(self, config):
        flags.save_config(config, self.path)


class FaultClient:
    """Unified client with auto-detection and forced mode support.

    Parameters
    ----------
    mode : str or None
        ``"api"`` forces HTTP, ``"local"`` forces file, ``None`` auto-detects.
    api_url : str
        Base URL for the flagd-ui REST API.
    file_path : str or Path or None
        Path to ``demo.flagd.json`` for direct file mode.
    """

    def __init__(self, mode=None, api_url=_DEFAULT_API_URL, file_path=None):
        self.mode = mode
        self.api_url = api_url
        self.file_path = file_path
        self._transport = None

    @property
    def transport_name(self):
        self._ensure_transport()
        return "api" if isinstance(self._transport, HttpTransport) else "local"

    def _ensure_transport(self):
        if self._transport is not None:
            return

        if self.mode == "api":
            self._transport = HttpTransport(self.api_url)
        elif self.mode == "local":
            self._transport = FileTransport(self.file_path)
        else:
            if HttpTransport.is_available(self.api_url):
                self._transport = HttpTransport(self.api_url)
            else:
                self._transport = FileTransport(self.file_path)

    def read(self):
        self._ensure_transport()
        return self._transport.read()

    def write(self, config):
        self._ensure_transport()
        self._transport.write(config)
