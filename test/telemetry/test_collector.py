# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import socket

from conftest import poll_until


def test_collector_healthy(collector_host, collector_port):
    """Verify the OTel Collector is accepting connections on its gRPC port."""

    def check():
        try:
            sock = socket.create_connection((collector_host, collector_port), timeout=5)
            sock.close()
            return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    poll_until(check, f"OTel Collector accepting connections on {collector_host}:{collector_port}")
