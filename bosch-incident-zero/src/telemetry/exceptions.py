"""Telemetry exception definitions for Bosch Incident Zero."""
from __future__ import annotations

from typing import Any, Optional


class TelemetryError(Exception):
    """Base exception for all telemetry backend client errors."""
    pass


class TelemetryConnectionError(TelemetryError):
    """Raised when network connection to the telemetry backend fails."""
    pass


class TelemetryTimeoutError(TelemetryError):
    """Raised when a request to a telemetry backend times out."""
    pass


class TelemetryResponseError(TelemetryError):
    """Raised when a telemetry backend returns an HTTP or protocol-level error."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class TelemetryDataError(TelemetryError):
    """Raised when telemetry backend response cannot be parsed or lacks expected structure."""
    pass
