"""
OTLP Kafka Consumer -> VastDB Ingestion

Consumes OpenTelemetry data from Kafka topics and writes to VastDB tables:
- logs_otel_analytic
- metrics_otel_analytic
- traces_otel_analytic
- span_events_otel_analytic
- span_links_otel_analytic

Usage:
    export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
    export VASTDB_ENDPOINT=http://vastdb:8080
    export VASTDB_ACCESS_KEY=your_access_key
    export VASTDB_SECRET_KEY=your_secret_key
    export VASTDB_BUCKET=observability
    export VASTDB_SCHEMA=otel
    
    python otel_kafka_vastdb_ingest.py
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field

import pyarrow as pa
import vastdb
from kafka import KafkaConsumer


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class Config:
    """Configuration for OTLP Kafka to VastDB ingestion."""
    
    # Kafka settings
    kafka_bootstrap_servers: str = field(
        default_factory=lambda: os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    )
    kafka_group_id: str = field(
        default_factory=lambda: os.getenv("KAFKA_GROUP_ID", "otel-vastdb-consumer")
    )
    kafka_auto_offset_reset: str = "earliest"
    kafka_enable_auto_commit: bool = True
    
    # Kafka topics
    logs_topic: str = field(default_factory=lambda: os.getenv("KAFKA_LOGS_TOPIC", "otel-logs"))
    traces_topic: str = field(default_factory=lambda: os.getenv("KAFKA_TRACES_TOPIC", "otel-traces"))
    metrics_topic: str = field(default_factory=lambda: os.getenv("KAFKA_METRICS_TOPIC", "otel-metrics"))
    
    # VastDB connection
    vastdb_endpoint: str = field(default_factory=lambda: os.getenv("VASTDB_ENDPOINT"))
    vastdb_access_key: str = field(default_factory=lambda: os.getenv("VASTDB_ACCESS_KEY"))
    vastdb_secret_key: str = field(default_factory=lambda: os.getenv("VASTDB_SECRET_KEY"))
    vastdb_bucket: str = field(default_factory=lambda: os.getenv("VASTDB_BUCKET", "observability"))
    vastdb_schema: str = field(default_factory=lambda: os.getenv("VASTDB_SCHEMA", "otel"))
    
    # VastDB table names
    logs_table: str = "logs_otel_analytic"
    metrics_table: str = "metrics_otel_analytic"
    traces_table: str = "traces_otel_analytic"
    span_events_table: str = "span_events_otel_analytic"
    span_links_table: str = "span_links_otel_analytic"
    
    # Batching configuration
    batch_size: int = field(default_factory=lambda: int(os.getenv("BATCH_SIZE", "1000")))
    batch_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("BATCH_TIMEOUT_SECONDS", "5.0"))
    )
    
    def validate(self):
        """Validate required configuration."""
        missing = []
        if not self.vastdb_endpoint:
            missing.append("VASTDB_ENDPOINT")
        if not self.vastdb_access_key:
            missing.append("VASTDB_ACCESS_KEY")
        if not self.vastdb_secret_key:
            missing.append("VASTDB_SECRET_KEY")
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


# =============================================================================
# PyArrow Schema Definitions
# =============================================================================

LOGS_SCHEMA = pa.schema([
    ("timestamp", pa.timestamp("ns", tz="UTC")),
    ("service_name", pa.string()),
    ("severity_number", pa.int32()),
    ("severity_text", pa.string()),
    ("body_text", pa.string()),
    ("trace_id", pa.string()),
    ("span_id", pa.string()),
    ("attributes_json", pa.string()),
])

METRICS_SCHEMA = pa.schema([
    ("timestamp", pa.timestamp("ns", tz="UTC")),
    ("service_name", pa.string()),
    ("metric_name", pa.string()),
    ("metric_unit", pa.string()),
    ("value_double", pa.float64()),
    ("attributes_flat", pa.string()),
])

TRACES_SCHEMA = pa.schema([
    ("trace_id", pa.string()),
    ("span_id", pa.string()),
    ("parent_span_id", pa.string()),
    ("start_time", pa.timestamp("ns", tz="UTC")),
    ("duration_ns", pa.int64()),
    ("service_name", pa.string()),
    ("span_name", pa.string()),
    ("span_kind", pa.string()),
    ("status_code", pa.string()),
    ("http_status", pa.int32()),
    ("db_system", pa.string()),
])

SPAN_EVENTS_SCHEMA = pa.schema([
    ("timestamp", pa.timestamp("ns", tz="UTC")),
    ("trace_id", pa.string()),
    ("span_id", pa.string()),
    ("service_name", pa.string()),
    ("span_name", pa.string()),
    ("event_name", pa.string()),
    ("event_attributes_json", pa.string()),
    ("exception_type", pa.string()),
    ("exception_message", pa.string()),
    ("exception_stacktrace", pa.string()),
    ("gen_ai_system", pa.string()),
    ("gen_ai_operation", pa.string()),
    ("gen_ai_request_model", pa.string()),
    ("gen_ai_usage_prompt_tokens", pa.int32()),
    ("gen_ai_usage_completion_tokens", pa.int32()),
])

SPAN_LINKS_SCHEMA = pa.schema([
    ("trace_id", pa.string()),
    ("span_id", pa.string()),
    ("service_name", pa.string()),
    ("span_name", pa.string()),
    ("linked_trace_id", pa.string()),
    ("linked_span_id", pa.string()),
    ("linked_trace_state", pa.string()),
    ("link_attributes_json", pa.string()),
])


# =============================================================================
# OTLP Constants and Mappings
# =============================================================================

SPAN_KIND_MAP = {
    0: "UNSPECIFIED",
    1: "INTERNAL",
    2: "SERVER",
    3: "CLIENT",
    4: "PRODUCER",
    5: "CONSUMER",
}

STATUS_CODE_MAP = {
    0: "UNSET",
    1: "OK",
    2: "ERROR",
}


# =============================================================================
# Type Conversion Utilities (handles OTLP JSON string encoding)
# =============================================================================

def safe_int(value: Any) -> Optional[int]:
    """
    Safely convert value to int or return None.
    Handles strings (common in OTLP JSON for large numbers).
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None
    if isinstance(value, float):
        return int(value)
    return None


def safe_float(value: Any) -> Optional[float]:
    """
    Safely convert value to float or return None.
    Handles strings (common in OTLP JSON).
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None
    return None


def safe_nanos_to_int(nanos: Any) -> int:
    """
    Convert nanosecond timestamp to int.
    OTLP JSON encodes large integers as strings to preserve precision.
    """
    if nanos is None:
        return 0
    if isinstance(nanos, int):
        return nanos
    if isinstance(nanos, str):
        if not nanos:
            return 0
        try:
            return int(nanos)
        except ValueError:
            return 0
    if isinstance(nanos, float):
        return int(nanos)
    return 0


def nanos_to_datetime(nanos: Any) -> Optional[datetime]:
    """
    Convert Unix nanoseconds to timezone-aware datetime.
    Handles both int and string representations.
    """
    nanos_int = safe_nanos_to_int(nanos)
    if nanos_int == 0:
        return None
    return datetime.fromtimestamp(nanos_int / 1e9, tz=timezone.utc)


# =============================================================================
# OTLP Parsing Utilities
# =============================================================================

def extract_anyvalue(value: Dict) -> Any:
    """
    Extract value from OTLP AnyValue.
    
    AnyValue can be: stringValue, intValue, doubleValue, boolValue,
                     bytesValue, arrayValue, kvlistValue
    """
    if not value:
        return None
    
    # Simple types - handle potential string encoding
    if "stringValue" in value:
        return value["stringValue"]
    if "intValue" in value:
        return safe_int(value["intValue"])
    if "doubleValue" in value:
        return safe_float(value["doubleValue"])
    if "boolValue" in value:
        return value["boolValue"]
    if "bytesValue" in value:
        return value["bytesValue"]
    
    # Array type
    if "arrayValue" in value:
        return [extract_anyvalue(v) for v in value["arrayValue"].get("values", [])]
    
    # Key-value list type
    if "kvlistValue" in value:
        return {
            kv["key"]: extract_anyvalue(kv.get("value", {}))
            for kv in value["kvlistValue"].get("values", [])
        }
    
    return None


def attributes_to_dict(attrs: List[Dict]) -> Dict[str, Any]:
    """Convert OTLP attributes list to Python dict."""
    if not attrs:
        return {}
    return {attr["key"]: extract_anyvalue(attr.get("value", {})) for attr in attrs}


def get_service_name(resource: Dict) -> str:
    """Extract service.name from resource attributes."""
    attrs = attributes_to_dict(resource.get("attributes", []))
    return attrs.get("service.name", "unknown")


def attributes_to_flat_string(attrs: Dict[str, Any]) -> str:
    """
    Convert attributes dict to flat key=value string for metrics.
    
    Example: {"method": "POST", "route": "/api"} -> "method=POST,route=/api"
    """
    if not attrs:
        return ""
    
    parts = []
    for k, v in sorted(attrs.items()):
        if isinstance(v, (dict, list)):
            v = json.dumps(v, separators=(',', ':'))
        parts.append(f"{k}={v}")
    return ",".join(parts)


def safe_json_dumps(obj: Any) -> str:
    """Safely serialize object to JSON string."""
    if not obj:
        return "{}"
    try:
        return json.dumps(obj, separators=(',', ':'), default=str)
    except (TypeError, ValueError):
        return "{}"


# =============================================================================
# OTLP Parsers
# =============================================================================

def parse_otlp_logs(message: Dict) -> List[Dict]:
    """
    Parse OTLP ExportLogsServiceRequest to logs_otel_analytic schema.
    
    OTLP Structure: resourceLogs[] -> scopeLogs[] -> logRecords[]
    """
    records = []
    
    for resource_log in message.get("resourceLogs", []):
        resource = resource_log.get("resource", {})
        service_name = get_service_name(resource)
        resource_attrs = attributes_to_dict(resource.get("attributes", []))
        
        for scope_log in resource_log.get("scopeLogs", []):
            scope = scope_log.get("scope", {})
            scope_attrs = {}
            if scope.get("name"):
                scope_attrs["otel.scope.name"] = scope["name"]
            if scope.get("version"):
                scope_attrs["otel.scope.version"] = scope["version"]
            
            for log_record in scope_log.get("logRecords", []):
                log_attrs = attributes_to_dict(log_record.get("attributes", []))
                
                # Merge all attributes
                all_attrs = {**resource_attrs, **scope_attrs, **log_attrs}
                all_attrs.pop("service.name", None)
                
                # Extract body
                body = log_record.get("body", {})
                if "stringValue" in body:
                    body_text = body["stringValue"]
                elif body:
                    extracted = extract_anyvalue(body)
                    body_text = json.dumps(extracted) if extracted else ""
                else:
                    body_text = ""
                
                record = {
                    "timestamp": nanos_to_datetime(log_record.get("timeUnixNano")),
                    "service_name": service_name,
                    "severity_number": safe_int(log_record.get("severityNumber")) or 0,
                    "severity_text": log_record.get("severityText", ""),
                    "body_text": body_text,
                    "trace_id": log_record.get("traceId", ""),
                    "span_id": log_record.get("spanId", ""),
                    "attributes_json": safe_json_dumps(all_attrs),
                }
                
                records.append(record)
    
    return records


def parse_otlp_metrics(message: Dict) -> List[Dict]:
    """
    Parse OTLP ExportMetricsServiceRequest to metrics_otel_analytic schema.

    OTLP Structure: resourceMetrics[] -> scopeMetrics[] -> metrics[] -> dataPoints[]
    """
    records = []

    for resource_metric in message.get("resourceMetrics", []):
        resource = resource_metric.get("resource", {})
        service_name = get_service_name(resource)
        # Extract resource attributes (includes host.name, host.id, etc.)
        resource_attrs = attributes_to_dict(resource.get("attributes", []))

        for scope_metric in resource_metric.get("scopeMetrics", []):
            for metric in scope_metric.get("metrics", []):
                metric_name = metric.get("name", "")
                metric_unit = metric.get("unit", "")

                # Handle Gauge
                if "gauge" in metric:
                    for dp in metric["gauge"].get("dataPoints", []):
                        records.append(_create_metric_record(
                            dp, service_name, metric_name, metric_unit, resource_attrs
                        ))

                # Handle Sum
                elif "sum" in metric:
                    for dp in metric["sum"].get("dataPoints", []):
                        records.append(_create_metric_record(
                            dp, service_name, metric_name, metric_unit, resource_attrs
                        ))

                # Handle Histogram
                elif "histogram" in metric:
                    for dp in metric["histogram"].get("dataPoints", []):
                        records.extend(_create_histogram_records(
                            dp, service_name, metric_name, metric_unit, resource_attrs
                        ))

                # Handle ExponentialHistogram
                elif "exponentialHistogram" in metric:
                    for dp in metric["exponentialHistogram"].get("dataPoints", []):
                        records.extend(_create_histogram_records(
                            dp, service_name, metric_name, metric_unit, resource_attrs
                        ))

                # Handle Summary
                elif "summary" in metric:
                    for dp in metric["summary"].get("dataPoints", []):
                        records.extend(_create_summary_records(
                            dp, service_name, metric_name, metric_unit, resource_attrs
                        ))

    return records


def _create_metric_record(
    dp: Dict,
    service_name: str,
    metric_name: str,
    metric_unit: str,
    resource_attrs: Dict = None
) -> Dict:
    """Create a metric record from a Gauge/Sum data point."""
    dp_attrs = attributes_to_dict(dp.get("attributes", []))
    # Merge resource attributes with datapoint attributes (dp attrs take precedence)
    all_attrs = {**(resource_attrs or {}), **dp_attrs}

    # Get value - handle string encoding
    value = safe_float(dp.get("asDouble"))
    if value is None:
        value = safe_float(dp.get("asInt"))
    if value is None:
        value = 0.0

    return {
        "timestamp": nanos_to_datetime(dp.get("timeUnixNano")),
        "service_name": service_name,
        "metric_name": metric_name,
        "metric_unit": metric_unit,
        "value_double": value,
        "attributes_flat": attributes_to_flat_string(all_attrs),
    }


def _create_histogram_records(
    dp: Dict,
    service_name: str,
    metric_name: str,
    metric_unit: str,
    resource_attrs: Dict = None
) -> List[Dict]:
    """Create metric records from a Histogram data point."""
    records = []
    dp_attrs = attributes_to_dict(dp.get("attributes", []))
    # Merge resource attributes with datapoint attributes
    all_attrs = {**(resource_attrs or {}), **dp_attrs}
    timestamp = nanos_to_datetime(dp.get("timeUnixNano"))
    attrs_flat = attributes_to_flat_string(all_attrs)
    
    # Count
    count = safe_float(dp.get("count"))
    if count is not None:
        records.append({
            "timestamp": timestamp,
            "service_name": service_name,
            "metric_name": f"{metric_name}.count",
            "metric_unit": "1",
            "value_double": count,
            "attributes_flat": attrs_flat,
        })
    
    # Sum
    sum_val = safe_float(dp.get("sum"))
    if sum_val is not None:
        records.append({
            "timestamp": timestamp,
            "service_name": service_name,
            "metric_name": f"{metric_name}.sum",
            "metric_unit": metric_unit,
            "value_double": sum_val,
            "attributes_flat": attrs_flat,
        })
    
    # Min
    min_val = safe_float(dp.get("min"))
    if min_val is not None:
        records.append({
            "timestamp": timestamp,
            "service_name": service_name,
            "metric_name": f"{metric_name}.min",
            "metric_unit": metric_unit,
            "value_double": min_val,
            "attributes_flat": attrs_flat,
        })
    
    # Max
    max_val = safe_float(dp.get("max"))
    if max_val is not None:
        records.append({
            "timestamp": timestamp,
            "service_name": service_name,
            "metric_name": f"{metric_name}.max",
            "metric_unit": metric_unit,
            "value_double": max_val,
            "attributes_flat": attrs_flat,
        })
    
    return records


def _create_summary_records(
    dp: Dict,
    service_name: str,
    metric_name: str,
    metric_unit: str,
    resource_attrs: Dict = None
) -> List[Dict]:
    """Create metric records from a Summary data point."""
    records = []
    dp_attrs = attributes_to_dict(dp.get("attributes", []))
    # Merge resource attributes with datapoint attributes
    all_attrs = {**(resource_attrs or {}), **dp_attrs}
    timestamp = nanos_to_datetime(dp.get("timeUnixNano"))
    attrs_flat = attributes_to_flat_string(all_attrs)
    
    # Count
    count = safe_float(dp.get("count"))
    if count is not None:
        records.append({
            "timestamp": timestamp,
            "service_name": service_name,
            "metric_name": f"{metric_name}.count",
            "metric_unit": "1",
            "value_double": count,
            "attributes_flat": attrs_flat,
        })
    
    # Sum
    sum_val = safe_float(dp.get("sum"))
    if sum_val is not None:
        records.append({
            "timestamp": timestamp,
            "service_name": service_name,
            "metric_name": f"{metric_name}.sum",
            "metric_unit": metric_unit,
            "value_double": sum_val,
            "attributes_flat": attrs_flat,
        })
    
    # Quantiles
    for qv in dp.get("quantileValues", []):
        quantile = safe_float(qv.get("quantile"))
        value = safe_float(qv.get("value"))
        if quantile is not None and value is not None:
            percentile = int(quantile * 100)
            records.append({
                "timestamp": timestamp,
                "service_name": service_name,
                "metric_name": f"{metric_name}.p{percentile}",
                "metric_unit": metric_unit,
                "value_double": value,
                "attributes_flat": attrs_flat,
            })
    
    return records


def parse_otlp_traces(message: Dict) -> Dict[str, List[Dict]]:
    """
    Parse OTLP ExportTraceServiceRequest to traces, events, and links tables.
    
    OTLP Structure: resourceSpans[] -> scopeSpans[] -> spans[]
    """
    spans = []
    events = []
    links = []
    
    for resource_span in message.get("resourceSpans", []):
        resource = resource_span.get("resource", {})
        service_name = get_service_name(resource)
        
        for scope_span in resource_span.get("scopeSpans", []):
            for span in scope_span.get("spans", []):
                span_attrs = attributes_to_dict(span.get("attributes", []))
                
                trace_id = span.get("traceId", "")
                span_id = span.get("spanId", "")
                span_name = span.get("name", "")
                
                # Calculate duration - use safe conversion for string timestamps
                start_ns = safe_nanos_to_int(span.get("startTimeUnixNano"))
                end_ns = safe_nanos_to_int(span.get("endTimeUnixNano"))
                duration_ns = end_ns - start_ns if start_ns and end_ns else 0
                
                # Map span kind
                kind_int = safe_int(span.get("kind")) or 0
                span_kind = SPAN_KIND_MAP.get(kind_int, "UNSPECIFIED")
                
                # Map status code
                status = span.get("status", {})
                status_code_int = safe_int(status.get("code")) or 0
                status_code = STATUS_CODE_MAP.get(status_code_int, "UNSET")
                
                # Promoted attributes
                http_status = (
                    span_attrs.get("http.status_code") or 
                    span_attrs.get("http.response.status_code")
                )
                db_system = span_attrs.get("db.system")
                
                # --- Span record ---
                spans.append({
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": span.get("parentSpanId", ""),
                    "start_time": nanos_to_datetime(start_ns),
                    "duration_ns": duration_ns,
                    "service_name": service_name,
                    "span_name": span_name,
                    "span_kind": span_kind,
                    "status_code": status_code,
                    "http_status": safe_int(http_status),
                    "db_system": db_system or "",
                })
                
                # --- Event records ---
                for event in span.get("events", []):
                    event_attrs = attributes_to_dict(event.get("attributes", []))
                    event_name = event.get("name", "")
                    
                    events.append({
                        "timestamp": nanos_to_datetime(event.get("timeUnixNano")),
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "service_name": service_name,
                        "span_name": span_name,
                        "event_name": event_name,
                        "event_attributes_json": safe_json_dumps(event_attrs),
                        # Promoted exception fields
                        "exception_type": str(event_attrs.get("exception.type", "") or ""),
                        "exception_message": str(event_attrs.get("exception.message", "") or ""),
                        "exception_stacktrace": str(event_attrs.get("exception.stacktrace", "") or ""),
                        # Promoted GenAI fields
                        "gen_ai_system": str(event_attrs.get("gen_ai.system", "") or ""),
                        "gen_ai_operation": str(event_attrs.get("gen_ai.operation.name", "") or ""),
                        "gen_ai_request_model": str(event_attrs.get("gen_ai.request.model", "") or ""),
                        "gen_ai_usage_prompt_tokens": safe_int(
                            event_attrs.get("gen_ai.usage.prompt_tokens")
                        ),
                        "gen_ai_usage_completion_tokens": safe_int(
                            event_attrs.get("gen_ai.usage.completion_tokens")
                        ),
                    })
                
                # --- Link records ---
                for link in span.get("links", []):
                    link_attrs = attributes_to_dict(link.get("attributes", []))
                    
                    links.append({
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "service_name": service_name,
                        "span_name": span_name,
                        "linked_trace_id": link.get("traceId", ""),
                        "linked_span_id": link.get("spanId", ""),
                        "linked_trace_state": link.get("traceState", ""),
                        "link_attributes_json": safe_json_dumps(link_attrs),
                    })
    
    return {
        "spans": spans,
        "events": events,
        "links": links,
    }


# =============================================================================
# VastDB Writer
# =============================================================================

class VastDBWriter:
    """Handles writing OTLP data to VastDB tables."""
    
    def __init__(self, config: Config):
        self.config = config
        self.session = vastdb.connect(
            endpoint=config.vastdb_endpoint,
            access=config.vastdb_access_key,
            secret=config.vastdb_secret_key
        )
        self._ensure_tables()
        print(f"[VastDB] Connected to {config.vastdb_endpoint}")
    
    def _ensure_tables(self):
        """Create schema and tables if they don't exist."""
        with self.session.transaction() as tx:
            bucket = tx.bucket(self.config.vastdb_bucket)
            
            schema = bucket.schema(self.config.vastdb_schema, fail_if_missing=False)
            if not schema:
                schema = bucket.create_schema(self.config.vastdb_schema)
                print(f"[VastDB] Created schema: {self.config.vastdb_schema}")
            
            tables = [
                (self.config.logs_table, LOGS_SCHEMA),
                (self.config.metrics_table, METRICS_SCHEMA),
                (self.config.traces_table, TRACES_SCHEMA),
                (self.config.span_events_table, SPAN_EVENTS_SCHEMA),
                (self.config.span_links_table, SPAN_LINKS_SCHEMA),
            ]
            
            for table_name, arrow_schema in tables:
                table = schema.table(table_name, fail_if_missing=False)
                if not table:
                    schema.create_table(table_name, arrow_schema)
                    print(f"[VastDB] Created table: {table_name}")
    
    def write_logs(self, records: List[Dict]):
        self._write_records(self.config.logs_table, records, LOGS_SCHEMA)
    
    def write_metrics(self, records: List[Dict]):
        self._write_records(self.config.metrics_table, records, METRICS_SCHEMA)
    
    def write_traces(self, records: List[Dict]):
        self._write_records(self.config.traces_table, records, TRACES_SCHEMA)
    
    def write_span_events(self, records: List[Dict]):
        self._write_records(self.config.span_events_table, records, SPAN_EVENTS_SCHEMA)
    
    def write_span_links(self, records: List[Dict]):
        self._write_records(self.config.span_links_table, records, SPAN_LINKS_SCHEMA)
    
    def _write_records(self, table_name: str, records: List[Dict], schema: pa.Schema):
        """Write records to a VastDB table."""
        if not records:
            return
        
        arrays = []
        for field in schema:
            values = [r.get(field.name) for r in records]
            arrays.append(pa.array(values, type=field.type))
        
        pa_table = pa.Table.from_arrays(arrays, schema=schema)
        
        with self.session.transaction() as tx:
            bucket = tx.bucket(self.config.vastdb_bucket)
            db_schema = bucket.schema(self.config.vastdb_schema)
            table = db_schema.table(table_name)
            table.insert(pa_table)
        
        print(f"[VastDB] Wrote {len(records)} records to {table_name}")


# =============================================================================
# Kafka Consumer
# =============================================================================

class OTelKafkaConsumer:
    """Consumes OTLP data from Kafka and writes to VastDB."""
    
    def __init__(self, config: Config):
        self.config = config
        self.writer = VastDBWriter(config)
        
        self.consumer = KafkaConsumer(
            config.logs_topic,
            config.traces_topic,
            config.metrics_topic,
            bootstrap_servers=config.kafka_bootstrap_servers,
            group_id=config.kafka_group_id,
            auto_offset_reset=config.kafka_auto_offset_reset,
            enable_auto_commit=config.kafka_enable_auto_commit,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        )
        
        self.buffers: Dict[str, List[Dict]] = {
            "logs": [],
            "metrics": [],
            "traces": [],
            "span_events": [],
            "span_links": [],
        }
        self.last_flush = time.time()
        
        print(f"[Kafka] Consuming from: {config.logs_topic}, "
              f"{config.traces_topic}, {config.metrics_topic}")
    
    def run(self):
        """Main consumer loop."""
        print("[Consumer] Starting main loop...")
        
        try:
            for message in self.consumer:
                self._process_message(message)
                self._maybe_flush()
        except KeyboardInterrupt:
            print("\n[Consumer] Shutting down...")
            self._flush_all()
        finally:
            self.consumer.close()
            print("[Consumer] Closed")
    
    def _process_message(self, message):
        """Parse Kafka message and add to buffer."""
        topic = message.topic
        
        try:
            if topic == self.config.logs_topic:
                records = parse_otlp_logs(message.value)
                self.buffers["logs"].extend(records)
            
            elif topic == self.config.traces_topic:
                parsed = parse_otlp_traces(message.value)
                self.buffers["traces"].extend(parsed["spans"])
                self.buffers["span_events"].extend(parsed["events"])
                self.buffers["span_links"].extend(parsed["links"])
            
            elif topic == self.config.metrics_topic:
                records = parse_otlp_metrics(message.value)
                self.buffers["metrics"].extend(records)
        
        except Exception as e:
            print(f"[Consumer] Error processing {topic}: {type(e).__name__}: {e}")
    
    def _maybe_flush(self):
        """Flush buffers if thresholds reached."""
        now = time.time()
        time_exceeded = (now - self.last_flush) >= self.config.batch_timeout_seconds
        
        for signal_type, buffer in self.buffers.items():
            if len(buffer) >= self.config.batch_size or (buffer and time_exceeded):
                self._flush_buffer(signal_type)
        
        if time_exceeded:
            self.last_flush = now
    
    def _flush_buffer(self, signal_type: str):
        """Flush a buffer to VastDB."""
        records = self.buffers[signal_type]
        if not records:
            return
        
        try:
            if signal_type == "logs":
                self.writer.write_logs(records)
            elif signal_type == "metrics":
                self.writer.write_metrics(records)
            elif signal_type == "traces":
                self.writer.write_traces(records)
            elif signal_type == "span_events":
                self.writer.write_span_events(records)
            elif signal_type == "span_links":
                self.writer.write_span_links(records)
            
            self.buffers[signal_type] = []
        except Exception as e:
            print(f"[Consumer] Error writing {signal_type}: {type(e).__name__}: {e}")
    
    def _flush_all(self):
        """Flush all buffers."""
        print("[Consumer] Flushing all buffers...")
        for signal_type in self.buffers:
            self._flush_buffer(signal_type)


# =============================================================================
# Main
# =============================================================================

def main():
    print("=" * 60)
    print("OTLP Kafka -> VastDB Ingestion")
    print("=" * 60)
    
    config = Config()
    try:
        config.validate()
    except ValueError as e:
        print(f"[Error] {e}")
        return 1
    
    print(f"\nKafka: {config.kafka_bootstrap_servers}")
    print(f"Topics: {config.logs_topic}, {config.traces_topic}, {config.metrics_topic}")
    print(f"VastDB: {config.vastdb_endpoint}/{config.vastdb_bucket}/{config.vastdb_schema}")
    print(f"Batch: size={config.batch_size}, timeout={config.batch_timeout_seconds}s\n")
    
    consumer = OTelKafkaConsumer(config)
    consumer.run()
    
    return 0


if __name__ == "__main__":
    exit(main())
