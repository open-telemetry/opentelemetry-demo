"""Resolve host URLs for demo containers whose ports Docker publishes at random."""
from __future__ import annotations

import subprocess
from typing import Optional


def docker_host_url(container: str, container_port: int, timeout_seconds: float = 5.0) -> Optional[str]:
    """Return http://localhost:<host_port> for a published container port, or None."""
    try:
        out = subprocess.run(
            ["docker", "port", container, str(container_port)],
            capture_output=True, text=True, timeout=timeout_seconds, check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        # Lines look like "0.0.0.0:60628" or "[::]:60628".
        port = line.rsplit(":", 1)[-1].strip()
        if port.isdigit():
            return f"http://localhost:{port}"
    return None
