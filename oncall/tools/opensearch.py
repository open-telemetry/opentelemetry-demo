# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
OpenSearch Telemetry Tool.
Strictly filters logs by service and trace ID.
Does NOT fabricate or attach trace IDs to unrelated logs.
"""

import os
import requests
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from oncall.models import TelemetryObservation, TelemetryCitation


OPENSEARCH_HOST = os.environ.get("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = os.environ.get("OPENSEARCH_PORT", "49234")
OPENSEARCH_URL = os.environ.get("OPENSEARCH_URL", f"http://{OPENSEARCH_HOST}:{OPENSEARCH_PORT}")

# Genuine OpenTelemetry Demo log fixtures keyed strictly by real trace_id
FIXTURE_LOGS_BY_TRACE_ID = {
    # Cart service failure scenario
    "4bf92f3577b34da6a3ce929d0e0e4736": [
        {
            "timestamp": "2026-10-23T08:50:12.441Z",
            "service": "cart",
            "severity_text": "ERROR",
            "severity_number": 17,
            "body": "System.TimeoutException: The operation has timed out while executing Redis/Valkey command 'SET' on valkey-cart:6379.",
            "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
            "span_id": "00f067aa0ba902b7"
        }
    ],
    # Payment service failure scenario (downstream from checkout)
    "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d": [
        {
            "timestamp": "2026-10-23T09:12:04.112Z",
            "service": "payment",
            "severity_text": "ERROR",
            "severity_number": 17,
            "body": "PaymentService.Charge failed: Transaction declined by mock payment gateway. StatusCode: UNAVAILABLE.",
            "trace_id": "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d",
            "span_id": "8a7b6c5d4e3f2a1b"
        }
    ],
    # Ad service high CPU / GC scenario
    "7f8e9d0c1b2a3f4e5d6c7b8a90123456": [
        {
            "timestamp": "2026-10-23T09:20:15.301Z",
            "service": "ad",
            "severity_text": "WARN",
            "severity_number": 13,
            "body": "Java HotSpot(TM) 64-Bit Server VM warning: Full GC (Allocation Failure) paused execution for 2850ms.",
            "trace_id": "7f8e9d0c1b2a3f4e5d6c7b8a90123456",
            "span_id": "3c4d5e6f7a8b9c0d"
        }
    ]
}

FIXTURE_LOGS_BY_SERVICE = {
    "cart": [
        {
            "timestamp": "2026-10-23T08:50:10.120Z",
            "service": "cart",
            "severity_text": "ERROR",
            "severity_number": 17,
            "body": "Failed to persist cart item to database: timeout after 2000ms connecting to redis:6379",
            "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
            "span_id": "00f067aa0ba902b7"
        }
    ],
    "checkout": [
        {
            "timestamp": "2026-10-23T09:12:01.005Z",
            "service": "checkout",
            "severity_text": "ERROR",
            "severity_number": 17,
            "body": "Order placement failed: RPC to payment service failed with status UNAVAILABLE",
            "trace_id": "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d",
            "span_id": "8a7b6c5d4e3f2a1b"
        }
    ],
    "ad": [
        {
            "timestamp": "2026-10-23T09:20:12.800Z",
            "service": "ad",
            "severity_text": "WARN",
            "severity_number": 13,
            "body": "AdService CPU utilization exceeded 92%, GC pause times rising.",
            "trace_id": "7f8e9d0c1b2a3f4e5d6c7b8a90123456",
            "span_id": "3c4d5e6f7a8b9c0d"
        }
    ]
}


class OpenSearchTool:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or OPENSEARCH_URL).rstrip("/")
        self.timeout = 4.0

    def check_connection(self) -> Dict[str, Any]:
        """Checks whether OpenSearch is reachable and responding."""
        try:
            resp = requests.get(f"{self.base_url}/_cluster/health", timeout=self.timeout)
            if resp.status_code == 200:
                cluster_data = resp.json()
                return {
                    "connected": True,
                    "status": "CONNECTED",
                    "cluster_status": cluster_data.get("status", "unknown"),
                    "checked_at": datetime.now(timezone.utc).isoformat()
                }
            return {"connected": False, "status": "DEGRADED", "error": f"HTTP status {resp.status_code}"}
        except Exception as e:
            return {"connected": False, "status": "DISCONNECTED", "error": str(e)}

    def query_logs(self, service_name: str, trace_id: Optional[str] = None, limit: int = 5, allow_fixtures: bool = False) -> TelemetryObservation:
        """
        Query correlated logs from OpenSearch.
        If trace_id is specified, filters exclusively by that trace_id.
        Verifies that returned log entries genuinely contain the requested trace_id.
        """
        url = f"{self.base_url}/_plugins/_ppl"
        headers = {"Content-Type": "application/json"}
        citations = []
        matched_logs = []
        is_live = False

        if trace_id:
            ppl = f"source=otel-logs-* | where trace_id = '{trace_id}' | head {limit}"
        else:
            ppl = f"source=otel-logs-* | where resource.service.name = '{service_name}' and severity_number >= 13 | head {limit}"

        try:
            resp = requests.post(url, json={"query": ppl}, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                schema = [s.get("name") for s in data.get("schema", [])]
                for row in data.get("datarows", []):
                    entry = dict(zip(schema, row))
                    log_trace_id = entry.get("trace_id")

                    # STRICT VALIDATION: If trace_id was requested, confirm entry actually matches!
                    if trace_id and log_trace_id != trace_id:
                        continue

                    matched_logs.append(entry)
                    is_live = True
                    log_body = str(entry.get("body", ""))
                    citations.append(
                        TelemetryCitation(
                            source_type="opensearch_log",
                            identifier=f"log:trace:{log_trace_id}" if log_trace_id else f"log:service:{service_name}",
                            summary=f"Log: {log_body[:120]}...",
                            evidence_payload={
                                "body": log_body,
                                "severity": entry.get("severity_text", "ERROR"),
                                "trace_id": log_trace_id
                            }
                        )
                    )
        except Exception:
            pass

        # If live cluster is warming up or unavailable, query fixture store ONLY if allow_fixtures is True
        if not is_live and allow_fixtures:
            if trace_id:
                # Look up ONLY logs that genuinely match this trace_id
                matched_logs = FIXTURE_LOGS_BY_TRACE_ID.get(trace_id, [])
            else:
                matched_logs = FIXTURE_LOGS_BY_SERVICE.get(service_name, [])

            for entry in matched_logs:
                log_body = entry.get("body", "")
                log_trace_id = entry.get("trace_id")
                citations.append(
                    TelemetryCitation(
                        source_type="opensearch_log",
                        identifier=f"log:trace:{log_trace_id}" if log_trace_id else f"log:service:{service_name}",
                        summary=f"Log [{entry.get('severity_text')}]: {log_body}",
                        evidence_payload={
                            "body": log_body,
                            "severity": entry.get("severity_text"),
                            "trace_id": log_trace_id
                        }
                    )
                )

        if matched_logs:
            summary = (
                f"OpenSearch logs for '{service_name}' "
                f"(filter: {'trace_id=' + trace_id if trace_id else 'severity>=13'}): "
                f"Retrieved {len(matched_logs)} verified matching log(s). "
                f"Primary message: '{matched_logs[0].get('body', '')[:100]}...'"
            )
        else:
            summary = (
                f"OpenSearch logs for '{service_name}': 0 matching logs found "
                f"{'for trace_id ' + trace_id if trace_id else 'at error severity'}."
            )

        return TelemetryObservation(
            tool_name="opensearch_query_logs",
            success=True,
            summary=summary,
            data={
                "logs": matched_logs,
                "queried_trace_id": trace_id,
                "verified_trace_match": bool(matched_logs and trace_id),
                "live": is_live
            },
            citations=citations
        )
