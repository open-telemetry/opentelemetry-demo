"""Jaeger v2 telemetry client for retrieving distributed traces and error spans."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
import requests

from .base import TelemetryClient
from .exceptions import TelemetryError


class JaegerClient(TelemetryClient):
    """Client for Jaeger v2 API in the OpenTelemetry Demo ecosystem."""

    def __init__(
        self,
        base_url: str = "http://localhost:16686",
        timeout_seconds: float = 10.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        super().__init__(base_url=base_url, timeout_seconds=timeout_seconds, session=session)

    def health_check(self) -> bool:
        """Check if Jaeger endpoint is reachable and healthy."""
        try:
            # Check v3 services endpoint
            resp = self.session.get(
                f"{self.base_url}/jaeger/ui/api/v3/services",
                timeout=min(self.timeout_seconds, 3.0),
            )
            if resp.ok:
                return True
            # Fallback to root or v2 services
            resp = self.session.get(
                f"{self.base_url}/api/services",
                timeout=min(self.timeout_seconds, 3.0),
            )
            return resp.ok
        except Exception:
            return False

    def get_services(self) -> List[str]:
        """Fetch list of all service names known to Jaeger."""
        # Try v3 first (used by upstream demo)
        try:
            data = self._request("GET", "/jaeger/ui/api/v3/services")
            services = data.get("services")
            return services if services is not None else []
        except TelemetryError:
            # Fallback to standard Jaeger API
            data = self._request("GET", "/api/services")
            data_val = data.get("data")
            return data_val if isinstance(data_val, list) else []

    def get_traces(
        self,
        service_name: str,
        lookback_seconds: int = 300,
        num_traces: int = 20,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Query traces for a specific service in a time window."""
        now = end_time or datetime.now(timezone.utc)
        start = start_time or (now - timedelta(seconds=lookback_seconds))
        fmt = "%Y-%m-%dT%H:%M:%SZ"

        params = {
            "query.service_name": service_name,
            "query.num_traces": num_traces,
            "query.start_time_min": start.strftime(fmt),
            "query.start_time_max": now.strftime(fmt),
        }

        try:
            return self._request("GET", "/jaeger/ui/api/v3/traces", params=params)
        except TelemetryError:
            # Fallback for standard Jaeger API (start/end in epoch microseconds)
            start_us = int(start.timestamp() * 1_000_000)
            end_us = int(now.timestamp() * 1_000_000)
            fallback_params = {
                "service": service_name,
                "limit": num_traces,
                "start": start_us,
                "end": end_us,
            }
            return self._request("GET", "/api/traces", params=fallback_params)

    def get_error_trace_ids(
        self,
        service_name: str,
        lookback_seconds: int = 300,
        max_traces: int = 20,
    ) -> List[str]:
        """Extract unique trace IDs that contain error spans for the specified service."""
        raw = self.get_traces(
            service_name=service_name,
            lookback_seconds=lookback_seconds,
            num_traces=max_traces,
        )

        error_trace_ids: Set[str] = set()

        # Parse v3 format: raw["result"]["resourceSpans"]
        resource_spans = raw.get("result", {}).get("resourceSpans") or []
        for rs in resource_spans:
            rs_service = self._extract_v3_service_name(rs)
            for scope in rs.get("scopeSpans", []):
                for span in scope.get("spans", []):
                    trace_id = span.get("traceId")
                    if not trace_id:
                        continue
                    if self._is_v3_span_error(span) and (not rs_service or rs_service == service_name):
                        error_trace_ids.add(str(trace_id))

        # Parse standard Jaeger v1/v2 format: raw["data"]
        data_traces = raw.get("data") or []
        if isinstance(data_traces, list):
            for trace in data_traces:
                trace_id = trace.get("traceID")
                for span in trace.get("spans", []):
                    span_proc = trace.get("processes", {}).get(span.get("processID"), {})
                    svc = span_proc.get("serviceName", "")
                    if self._is_v1_span_error(span) and (not svc or svc == service_name):
                        if trace_id:
                            error_trace_ids.add(str(trace_id))

        return sorted(list(error_trace_ids))

    def query(self, query_string: str, **kwargs: Any) -> Dict[str, Any]:
        """Execute traces query by service name."""
        lookback = kwargs.get("lookback_seconds", 300)
        num_traces = kwargs.get("num_traces", 20)
        return self.get_traces(
            service_name=query_string,
            lookback_seconds=lookback,
            num_traces=num_traces,
        )

    @staticmethod
    def _extract_v3_service_name(resource_span: Dict[str, Any]) -> Optional[str]:
        resource = resource_span.get("resource", {})
        for attr in resource.get("attributes", []):
            if attr.get("key") == "service.name":
                val = attr.get("value", {})
                return val.get("stringValue")
        return None

    @staticmethod
    def _is_v3_span_error(span: Dict[str, Any]) -> bool:
        # OpenTelemetry status code 2 = ERROR
        status = span.get("status", {})
        code = status.get("code")
        if code in (2, "STATUS_CODE_ERROR", "2"):
            return True
        # Check attributes
        for attr in span.get("attributes", []):
            if attr.get("key") == "error":
                val = attr.get("value", {})
                if val.get("boolValue") is True or val.get("stringValue", "").lower() == "true":
                    return True
        return False

    @staticmethod
    def _is_v1_span_error(span: Dict[str, Any]) -> bool:
        for tag in span.get("tags", []):
            if tag.get("key") == "error" and tag.get("value") in (True, "true", 1):
                return True
        return False
