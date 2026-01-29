#!/usr/bin/env python3
"""
Kafka Sizing Estimator for OpenTelemetry Data

Analyzes observability data to estimate Kafka throughput requirements.
Provides estimates for:
- Messages per hour by service and signal type (logs, metrics, traces)
- Estimated message sizes
- Total throughput in MB/hour

Usage:
    python scripts/kafka_sizing.py [--hours 24]
"""

import os
import sys
import argparse
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from trino.dbapi import connect as trino_connect
    from trino.auth import BasicAuthentication
except ImportError:
    print("Error: trino package not installed. Run: pip install trino")
    sys.exit(1)

# Configuration from environment
TRINO_HOST = os.getenv("TRINO_HOST")
TRINO_PORT = int(os.getenv("TRINO_PORT", "443"))
TRINO_USER = os.getenv("TRINO_USER", "admin")
TRINO_PASSWORD = os.getenv("TRINO_PASSWORD")
TRINO_CATALOG = os.getenv("TRINO_CATALOG", "vast")
TRINO_SCHEMA = os.getenv("TRINO_SCHEMA", "otel")
TRINO_HTTP_SCHEME = os.getenv("TRINO_HTTP_SCHEME", "https")


def get_connection():
    """Create Trino connection."""
    auth = BasicAuthentication(TRINO_USER, TRINO_PASSWORD) if TRINO_PASSWORD else None
    return trino_connect(
        host=TRINO_HOST,
        port=TRINO_PORT,
        user=TRINO_USER,
        catalog=TRINO_CATALOG,
        schema=TRINO_SCHEMA,
        http_scheme=TRINO_HTTP_SCHEME,
        auth=auth,
        verify=False
    )


def execute_query(cursor, sql):
    """Execute a query and return results."""
    try:
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        print(f"Query error: {e}")
        return []


def format_number(n):
    """Format large numbers with K/M suffixes."""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(int(n))


def format_bytes(b):
    """Format bytes with KB/MB/GB suffixes."""
    if b >= 1_073_741_824:
        return f"{b/1_073_741_824:.2f} GB"
    elif b >= 1_048_576:
        return f"{b/1_048_576:.2f} MB"
    elif b >= 1_024:
        return f"{b/1_024:.2f} KB"
    return f"{int(b)} B"


def analyze_traces(cursor, hours):
    """Analyze trace/span throughput."""
    print("\n" + "="*60)
    print("📊 TRACES (otel-traces topic)")
    print("="*60)

    # Get span counts by service
    query = f"""
    SELECT
        service_name,
        COUNT(*) as span_count,
        COUNT(DISTINCT trace_id) as trace_count,
        AVG(LENGTH(COALESCE(span_name, ''))) as avg_span_name_len,
        COUNT(*) / {hours}.0 as spans_per_hour
    FROM spans_otel_analytic
    WHERE timestamp > NOW() - INTERVAL '{hours}' HOUR
      AND service_name IS NOT NULL AND service_name != ''
    GROUP BY service_name
    ORDER BY span_count DESC
    """

    results = execute_query(cursor, query)

    if not results:
        print("No trace data found.")
        return 0, 0

    total_spans = sum(r['span_count'] for r in results)
    total_traces = sum(r['trace_count'] for r in results)

    # Estimate average span size (based on typical OTLP proto encoding)
    # Base: ~100 bytes + span_name + attributes (~200 bytes avg)
    AVG_SPAN_SIZE = 350  # bytes

    print(f"\n{'Service':<30} {'Spans':<12} {'Traces':<12} {'Spans/hr':<12}")
    print("-" * 66)

    for r in results[:15]:  # Top 15
        print(f"{r['service_name'][:29]:<30} {format_number(r['span_count']):<12} "
              f"{format_number(r['trace_count']):<12} {format_number(r['spans_per_hour']):<12}")

    if len(results) > 15:
        print(f"... and {len(results) - 15} more services")

    spans_per_hour = total_spans / hours
    bytes_per_hour = spans_per_hour * AVG_SPAN_SIZE

    print(f"\n{'TOTAL':<30} {format_number(total_spans):<12} {format_number(total_traces):<12} {format_number(spans_per_hour):<12}")
    print(f"\nEstimated throughput: {format_bytes(bytes_per_hour)}/hour ({format_bytes(bytes_per_hour/3600)}/sec)")
    print(f"Estimated avg message size: {AVG_SPAN_SIZE} bytes/span")

    return spans_per_hour, bytes_per_hour


def analyze_metrics(cursor, hours):
    """Analyze metrics throughput."""
    print("\n" + "="*60)
    print("📈 METRICS (otel-metrics topic)")
    print("="*60)

    # Get metric counts by service
    query = f"""
    SELECT
        service_name,
        COUNT(*) as datapoint_count,
        COUNT(DISTINCT metric_name) as unique_metrics,
        COUNT(*) / {hours}.0 as datapoints_per_hour
    FROM metrics_otel_analytic
    WHERE timestamp > NOW() - INTERVAL '{hours}' HOUR
      AND service_name IS NOT NULL AND service_name != ''
    GROUP BY service_name
    ORDER BY datapoint_count DESC
    """

    results = execute_query(cursor, query)

    if not results:
        print("No metrics data found.")
        return 0, 0

    total_datapoints = sum(r['datapoint_count'] for r in results)

    # Estimate average metric datapoint size
    # Base: ~50 bytes + metric_name (~30 bytes) + attributes (~100 bytes)
    AVG_METRIC_SIZE = 180  # bytes

    print(f"\n{'Service':<30} {'Datapoints':<12} {'Metrics':<12} {'Points/hr':<12}")
    print("-" * 66)

    for r in results[:15]:
        svc = r['service_name'] or 'unknown'
        print(f"{svc[:29]:<30} {format_number(r['datapoint_count']):<12} "
              f"{format_number(r['unique_metrics']):<12} {format_number(r['datapoints_per_hour']):<12}")

    if len(results) > 15:
        print(f"... and {len(results) - 15} more services")

    datapoints_per_hour = total_datapoints / hours
    bytes_per_hour = datapoints_per_hour * AVG_METRIC_SIZE

    print(f"\n{'TOTAL':<30} {format_number(total_datapoints):<12} {'-':<12} {format_number(datapoints_per_hour):<12}")
    print(f"\nEstimated throughput: {format_bytes(bytes_per_hour)}/hour ({format_bytes(bytes_per_hour/3600)}/sec)")
    print(f"Estimated avg message size: {AVG_METRIC_SIZE} bytes/datapoint")

    return datapoints_per_hour, bytes_per_hour


def analyze_logs(cursor, hours):
    """Analyze logs throughput."""
    print("\n" + "="*60)
    print("📝 LOGS (otel-logs topic)")
    print("="*60)

    # Get log counts by service with body size estimate
    query = f"""
    SELECT
        service_name,
        COUNT(*) as log_count,
        AVG(LENGTH(COALESCE(body_text, ''))) as avg_body_len,
        COUNT(*) / {hours}.0 as logs_per_hour
    FROM logs_otel_analytic
    WHERE timestamp > NOW() - INTERVAL '{hours}' HOUR
      AND service_name IS NOT NULL AND service_name != ''
    GROUP BY service_name
    ORDER BY log_count DESC
    """

    results = execute_query(cursor, query)

    if not results:
        print("No logs data found.")
        return 0, 0

    total_logs = sum(r['log_count'] for r in results)
    avg_body_len = sum(r['avg_body_len'] * r['log_count'] for r in results) / total_logs if total_logs > 0 else 100

    # Estimate average log size
    # Base: ~80 bytes + body_text + attributes (~50 bytes)
    AVG_LOG_SIZE = 130 + avg_body_len  # bytes

    print(f"\n{'Service':<30} {'Logs':<12} {'Avg Body':<12} {'Logs/hr':<12}")
    print("-" * 66)

    for r in results[:15]:
        svc = r['service_name'] or 'unknown'
        print(f"{svc[:29]:<30} {format_number(r['log_count']):<12} "
              f"{int(r['avg_body_len'])} bytes{'':<4} {format_number(r['logs_per_hour']):<12}")

    if len(results) > 15:
        print(f"... and {len(results) - 15} more services")

    logs_per_hour = total_logs / hours
    bytes_per_hour = logs_per_hour * AVG_LOG_SIZE

    print(f"\n{'TOTAL':<30} {format_number(total_logs):<12} {int(avg_body_len)} bytes{'':<4} {format_number(logs_per_hour):<12}")
    print(f"\nEstimated throughput: {format_bytes(bytes_per_hour)}/hour ({format_bytes(bytes_per_hour/3600)}/sec)")
    print(f"Estimated avg message size: {int(AVG_LOG_SIZE)} bytes/log")

    return logs_per_hour, bytes_per_hour


def print_summary(hours, traces_rate, traces_bytes, metrics_rate, metrics_bytes, logs_rate, logs_bytes):
    """Print overall summary."""
    print("\n" + "="*60)
    print("📋 KAFKA SIZING SUMMARY")
    print("="*60)

    total_msgs_per_hour = traces_rate + metrics_rate + logs_rate
    total_bytes_per_hour = traces_bytes + metrics_bytes + logs_bytes

    print(f"\nAnalysis period: {hours} hours")
    print(f"\n{'Topic':<20} {'Messages/hr':<15} {'Throughput/hr':<15} {'Throughput/sec':<15}")
    print("-" * 65)
    print(f"{'otel-traces':<20} {format_number(traces_rate):<15} {format_bytes(traces_bytes):<15} {format_bytes(traces_bytes/3600):<15}")
    print(f"{'otel-metrics':<20} {format_number(metrics_rate):<15} {format_bytes(metrics_bytes):<15} {format_bytes(metrics_bytes/3600):<15}")
    print(f"{'otel-logs':<20} {format_number(logs_rate):<15} {format_bytes(logs_bytes):<15} {format_bytes(logs_bytes/3600):<15}")
    print("-" * 65)
    print(f"{'TOTAL':<20} {format_number(total_msgs_per_hour):<15} {format_bytes(total_bytes_per_hour):<15} {format_bytes(total_bytes_per_hour/3600):<15}")

    print("\n📐 KAFKA CONFIGURATION RECOMMENDATIONS:")
    print("-" * 40)

    # Calculate recommended settings
    msgs_per_sec = total_msgs_per_hour / 3600
    bytes_per_sec = total_bytes_per_hour / 3600

    # Add 50% headroom
    recommended_throughput = bytes_per_sec * 1.5

    print(f"  Minimum throughput capacity: {format_bytes(recommended_throughput)}/sec (with 50% headroom)")
    print(f"  Estimated daily volume: {format_bytes(total_bytes_per_hour * 24)}")
    print(f"  Estimated weekly volume: {format_bytes(total_bytes_per_hour * 24 * 7)}")

    # Partition recommendations based on throughput
    if bytes_per_sec > 10_000_000:  # >10 MB/s
        partitions = "6-12 partitions per topic"
    elif bytes_per_sec > 1_000_000:  # >1 MB/s
        partitions = "3-6 partitions per topic"
    else:
        partitions = "1-3 partitions per topic"

    print(f"  Suggested partitions: {partitions}")

    # Retention recommendation
    print(f"\n  Retention settings (example for 7-day retention):")
    print(f"    retention.ms: 604800000 (7 days)")
    print(f"    retention.bytes: {int(total_bytes_per_hour * 24 * 7 * 1.2)} ({format_bytes(total_bytes_per_hour * 24 * 7 * 1.2)})")


def main():
    parser = argparse.ArgumentParser(description='Kafka sizing estimator for OpenTelemetry data')
    parser.add_argument('--hours', type=int, default=24, help='Hours of data to analyze (default: 24)')
    args = parser.parse_args()

    if not TRINO_HOST:
        print("Error: TRINO_HOST environment variable not set")
        sys.exit(1)

    print(f"\n🔍 Kafka Sizing Analysis")
    print(f"   Analyzing {args.hours} hours of data from {TRINO_HOST}")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        traces_rate, traces_bytes = analyze_traces(cursor, args.hours)
        metrics_rate, metrics_bytes = analyze_metrics(cursor, args.hours)
        logs_rate, logs_bytes = analyze_logs(cursor, args.hours)

        print_summary(args.hours, traces_rate, traces_bytes, metrics_rate, metrics_bytes, logs_rate, logs_bytes)

    finally:
        cursor.close()
        conn.close()

    print("\n✅ Analysis complete\n")


if __name__ == '__main__':
    main()
