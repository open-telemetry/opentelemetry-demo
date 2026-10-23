"""OpenSearch 2 client for querying structured application and error logs."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import requests

from .base import TelemetryClient
from .exceptions import TelemetryError


class OpenSearchClient(TelemetryClient):
    """Client for OpenSearch log store in the OpenTelemetry Demo ecosystem."""

    def __init__(
        self,
        base_url: str = "http://localhost:9200",
        timeout_seconds: float = 10.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        super().__init__(base_url=base_url, timeout_seconds=timeout_seconds, session=session)

    def health_check(self) -> bool:
        """Check if OpenSearch is healthy."""
        try:
            resp = self.session.get(
                f"{self.base_url}/_cluster/health",
                timeout=min(self.timeout_seconds, 3.0),
            )
            if resp.ok:
                status = resp.json().get("status", "")
                return status in ("green", "yellow")
            # Fallback to root endpoint
            resp = self.session.get(self.base_url, timeout=min(self.timeout_seconds, 3.0))
            return resp.ok
        except Exception:
            return False

    def search(
        self,
        index: str = "otel-logs*",
        query_dsl: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a standard Elasticsearch/OpenSearch JSON query DSL search."""
        dsl = query_dsl or {"query": {"match_all": {}}, "size": 20}
        endpoint = f"/{index.lstrip('/')}/_search"
        return self._request(
            method="POST",
            endpoint=endpoint,
            json_data=dsl,
            headers={"Content-Type": "application/json"},
        )

    def search_ppl(self, ppl_query: str) -> Dict[str, Any]:
        """Execute query using the OpenSearch PPL plugin."""
        return self._request(
            method="POST",
            endpoint="/_plugins/_ppl",
            json_data={"query": ppl_query},
            headers={"Content-Type": "application/json"},
        )

    def get_error_logs(
        self,
        service_name: str,
        lookback_seconds: int = 300,
        max_results: int = 50,
    ) -> List[str]:
        """Retrieve formatted error logs for a service within a lookback window."""
        lookback_expr = f"now-{lookback_seconds}s"
        query_dsl = {
            "size": max_results,
            "sort": [{"observedTimestamp": {"order": "desc", "unmapped_type": "keyword"}}],
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": service_name,
                                "fields": [
                                    "resource.attributes.service.name",
                                    "resource.service.name",
                                    "service_name",
                                ],
                            }
                        }
                    ],
                    "filter": [
                        {
                            "range": {
                                "observedTimestamp": {
                                    "gte": lookback_expr,
                                }
                            }
                        }
                    ],
                    "should": [
                        {"term": {"severityText": "ERROR"}},
                        {"term": {"severityText": "FATAL"}},
                        {"term": {"severityText": "CRITICAL"}},
                        {"wildcard": {"body": "*error*"}},
                        {"wildcard": {"body": "*fail*"}},
                        {"wildcard": {"body": "*exception*"}},
                    ],
                    "minimum_should_match": 1,
                }
            },
        }

        try:
            res = self.search(index="otel-logs*", query_dsl=query_dsl)
            hits = res.get("hits", {}).get("hits", [])
            log_lines: List[str] = []
            for hit in hits:
                source = hit.get("_source", {})
                line = self._format_log_entry(source, service_name)
                if line:
                    log_lines.append(line)
            return log_lines
        except TelemetryError:
            # Fallback: try PPL plugin endpoint (used by upstream demo tests)
            ppl = (
                f"source=otel-logs-* | where resource.service.name = '{service_name}' "
                f"| sort - observedTimestamp | head {max_results}"
            )
            try:
                ppl_res = self.search_ppl(ppl)
                datarows = ppl_res.get("datarows", [])
                schema = ppl_res.get("schema", [])
                col_names = [col.get("name") for col in schema]
                ppl_lines: List[str] = []
                for row in datarows:
                    row_dict = dict(zip(col_names, row))
                    line = self._format_log_entry(row_dict, service_name)
                    if line:
                        ppl_lines.append(line)
                return ppl_lines
            except TelemetryError:
                # Propagate original or PPL exception
                raise

    def query(self, query_string: str, **kwargs: Any) -> Dict[str, Any]:
        """Search logs matching query string."""
        index = kwargs.get("index", "otel-logs*")
        dsl = {
            "query": {"query_string": {"query": query_string}},
            "size": kwargs.get("size", 20),
        }
        return self.search(index=index, query_dsl=dsl)

    @staticmethod
    def _format_log_entry(source: Dict[str, Any], fallback_service: str) -> Optional[str]:
        """Format an OpenSearch log document into a human-readable string with trace context."""
        timestamp = source.get("observedTimestamp") or source.get("@timestamp") or "UNKNOWN_TIME"
        severity = source.get("severityText") or source.get("level") or "INFO"
        body = source.get("body") or source.get("message") or ""

        if isinstance(body, dict):
            body_str = str(body.get("stringValue") or body)
        else:
            body_str = str(body).strip()

        if not body_str:
            return None

        trace_id = source.get("traceId")
        trace_suffix = f" [traceId={trace_id}]" if trace_id else ""
        return f"[{timestamp}] [{severity}] {fallback_service}: {body_str}{trace_suffix}"
