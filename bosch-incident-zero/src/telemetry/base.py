"""Base definitions and abstract interface for telemetry clients."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import requests

from .exceptions import (
    TelemetryConnectionError,
    TelemetryDataError,
    TelemetryResponseError,
    TelemetryTimeoutError,
)


class TelemetryClient(ABC):
    """Abstract interface for querying telemetry from observability backends."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 10.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Execute HTTP request with standardized exception translation."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            resp = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
                timeout=self.timeout_seconds,
            )
        except requests.exceptions.Timeout as e:
            raise TelemetryTimeoutError(
                f"Request to {url} timed out after {self.timeout_seconds}s"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise TelemetryConnectionError(
                f"Failed to connect to telemetry backend at {url}: {e}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise TelemetryConnectionError(f"HTTP request to {url} failed: {e}") from e

        if not resp.ok:
            raise TelemetryResponseError(
                f"Backend returned HTTP {resp.status_code} for {url}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

        try:
            return resp.json()
        except (ValueError, json.JSONDecodeError) as e:
            raise TelemetryDataError(
                f"Malformed JSON response from {url}: {resp.text[:200]}"
            ) from e

    @abstractmethod
    def health_check(self) -> bool:
        """Verify endpoint connectivity."""
        pass

    @abstractmethod
    def query(self, query_string: str, **kwargs: Any) -> Dict[str, Any]:
        """Execute a backend-specific query."""
        pass
