#!/usr/bin/env python3
"""
Predictive Maintenance Alerts Service

Automated service that monitors telemetry data and generates predictive alerts
for potential issues before they become critical failures.

Features:
- Self-learning baselines from historical data
- Multiple anomaly detection methods (Z-score, IQR, Isolation Forest)
- Trend detection for gradual degradation
- Automatic alert generation and resolution
- No user input required - fully automated

Usage:
    export TRINO_HOST=trino.example.com
    export TRINO_PASSWORD=your_password
    python predictive_alerts.py

Environment Variables:
    TRINO_HOST          - Trino server hostname
    TRINO_PORT          - Trino server port (default: 443)
    TRINO_USER          - Trino username (default: admin)
    TRINO_PASSWORD      - Trino password
    TRINO_CATALOG       - Trino catalog (default: vast)
    TRINO_SCHEMA        - Trino schema (default: otel)

    DETECTION_INTERVAL  - Seconds between detection runs (default: 60)
    BASELINE_INTERVAL   - Seconds between baseline updates (default: 3600)
    BASELINE_WINDOW_HOURS - Hours of data for baseline computation (default: 24)
    ANOMALY_THRESHOLD   - Z-score threshold for anomaly (default: 3.0)
"""

import os
import sys
import time
import uuid
import signal
import warnings
import json
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from collections import deque
import statistics
import math

# Suppress warnings
warnings.filterwarnings("ignore")

# Optional: Anthropic for LLM-powered investigations
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("[INFO] anthropic not available - LLM investigations disabled")

try:
    from trino.dbapi import connect as trino_connect
    from trino.auth import BasicAuthentication
    TRINO_AVAILABLE = True
except ImportError:
    TRINO_AVAILABLE = False
    print("[ERROR] trino package not installed. Run: pip install trino")
    sys.exit(1)

# Optional: sklearn for advanced anomaly detection
try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("[INFO] sklearn not available - using statistical methods only")


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class Config:
    """Configuration for predictive alerts service."""

    # Trino connection
    trino_host: str = field(default_factory=lambda: os.getenv("TRINO_HOST"))
    trino_port: int = field(default_factory=lambda: int(os.getenv("TRINO_PORT", "443")))
    trino_user: str = field(default_factory=lambda: os.getenv("TRINO_USER", "admin"))
    trino_password: str = field(default_factory=lambda: os.getenv("TRINO_PASSWORD"))
    trino_catalog: str = field(default_factory=lambda: os.getenv("TRINO_CATALOG", "vast"))
    trino_schema: str = field(default_factory=lambda: os.getenv("TRINO_SCHEMA", "otel"))
    trino_http_scheme: str = field(default_factory=lambda: os.getenv("TRINO_HTTP_SCHEME", "https"))

    # Detection settings
    detection_interval: int = field(
        default_factory=lambda: int(os.getenv("DETECTION_INTERVAL", "60"))
    )
    baseline_interval: int = field(
        default_factory=lambda: int(os.getenv("BASELINE_INTERVAL", "3600"))
    )
    baseline_window_hours: int = field(
        default_factory=lambda: int(os.getenv("BASELINE_WINDOW_HOURS", "24"))
    )

    # Anomaly thresholds
    zscore_threshold: float = field(
        default_factory=lambda: float(os.getenv("ANOMALY_THRESHOLD", "3.0"))
    )
    error_rate_warning: float = field(
        default_factory=lambda: float(os.getenv("ERROR_RATE_WARNING", "0.05"))
    )
    error_rate_critical: float = field(
        default_factory=lambda: float(os.getenv("ERROR_RATE_CRITICAL", "0.20"))
    )

    # Alert settings
    min_samples_for_baseline: int = field(
        default_factory=lambda: int(os.getenv("MIN_SAMPLES_FOR_BASELINE", "10"))
    )
    alert_cooldown_minutes: int = field(
        default_factory=lambda: int(os.getenv("ALERT_COOLDOWN_MINUTES", "15"))
    )
    auto_resolve_minutes: int = field(
        default_factory=lambda: int(os.getenv("AUTO_RESOLVE_MINUTES", "30"))
    )

    # Root cause detection settings (flexible/learnable)
    root_cause_enabled: bool = field(
        default_factory=lambda: os.getenv("ROOT_CAUSE_ENABLED", "true").lower() == "true"
    )
    # Comma-separated list of root cause types to enable (empty = all enabled)
    # Options: db_latency, db_error, dependency_latency, dependency_error, exception_surge, new_exception
    root_cause_types: str = field(
        default_factory=lambda: os.getenv("ROOT_CAUSE_TYPES", "")
    )
    # Per-type threshold multipliers (relative to base zscore_threshold)
    # Format: "db_latency:0.8,db_error:0.6,dependency:1.0,exception:1.2"
    root_cause_threshold_multipliers: str = field(
        default_factory=lambda: os.getenv("ROOT_CAUSE_THRESHOLDS", "db_error:0.8,dependency_error:0.9")
    )
    # Adaptive learning: adjust thresholds based on alert resolution patterns
    adaptive_thresholds_enabled: bool = field(
        default_factory=lambda: os.getenv("ADAPTIVE_THRESHOLDS", "true").lower() == "true"
    )
    # How much to adjust threshold when alerts are frequently auto-resolved (likely false positives)
    adaptive_threshold_adjustment: float = field(
        default_factory=lambda: float(os.getenv("ADAPTIVE_THRESHOLD_ADJUSTMENT", "0.1"))
    )

    # LLM Investigation settings
    anthropic_api_key: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY")
    )
    investigation_model: str = field(
        default_factory=lambda: os.getenv("INVESTIGATION_MODEL", "claude-3-5-haiku-20241022")
    )
    investigation_max_tokens: int = field(
        default_factory=lambda: int(os.getenv("INVESTIGATION_MAX_TOKENS", "1000"))
    )
    max_investigations_per_hour: int = field(
        default_factory=lambda: int(os.getenv("MAX_INVESTIGATIONS_PER_HOUR", "5"))
    )
    investigation_service_cooldown_minutes: int = field(
        default_factory=lambda: int(os.getenv("INVESTIGATION_SERVICE_COOLDOWN_MINUTES", "30"))
    )
    investigate_critical_only: bool = field(
        default_factory=lambda: os.getenv("INVESTIGATE_CRITICAL_ONLY", "false").lower() == "true"
    )

    def validate(self):
        """Validate required configuration."""
        if not self.trino_host:
            raise ValueError("TRINO_HOST environment variable is required")


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(Enum):
    # Symptom-based alerts (existing)
    ERROR_SPIKE = "error_spike"
    LATENCY_DEGRADATION = "latency_degradation"
    THROUGHPUT_DROP = "throughput_drop"
    ANOMALY = "anomaly"
    TREND = "trend"
    SERVICE_DOWN = "service_down"

    # Root cause alerts (new) - proactive detection of underlying issues
    DB_CONNECTION_FAILURE = "db_connection_failure"    # Database connection issues
    DB_SLOW_QUERIES = "db_slow_queries"                # Database query performance degradation
    DEPENDENCY_FAILURE = "dependency_failure"          # Downstream service failures
    DEPENDENCY_LATENCY = "dependency_latency"          # Downstream service slow responses
    EXCEPTION_SURGE = "exception_surge"                # Unusual increase in exceptions
    NEW_EXCEPTION_TYPE = "new_exception_type"          # Previously unseen exception type


class AlertStatus(Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


# =============================================================================
# Adaptive Threshold Manager
# =============================================================================

class AdaptiveThresholdManager:
    """
    Manages learned thresholds that adapt based on alert patterns.

    Learning logic:
    - If alerts for a metric type are frequently auto-resolved quickly -> increase threshold (reduce sensitivity)
    - If alerts lead to investigations with confirmed root causes -> decrease threshold (increase sensitivity)
    """

    def __init__(self, config: Config):
        self.config = config
        self.base_threshold = config.zscore_threshold

        # Parse configured threshold multipliers
        self.multipliers: Dict[str, float] = self._parse_multipliers(config.root_cause_threshold_multipliers)

        # Learned adjustments (loaded from DB, modified over time)
        self.learned_adjustments: Dict[str, float] = {}

        # Parse enabled root cause types
        self.enabled_types: set = self._parse_enabled_types(config.root_cause_types)

    def _parse_multipliers(self, multiplier_str: str) -> Dict[str, float]:
        """Parse threshold multipliers from config string."""
        multipliers = {}
        if not multiplier_str:
            return multipliers

        for pair in multiplier_str.split(","):
            if ":" in pair:
                key, value = pair.strip().split(":", 1)
                try:
                    multipliers[key.strip()] = float(value.strip())
                except ValueError:
                    pass
        return multipliers

    def _parse_enabled_types(self, types_str: str) -> set:
        """Parse enabled root cause types from config string."""
        if not types_str:
            return set()  # Empty means all enabled
        return {t.strip() for t in types_str.split(",") if t.strip()}

    def is_root_cause_enabled(self, root_cause_type: str) -> bool:
        """Check if a specific root cause type is enabled."""
        if not self.config.root_cause_enabled:
            return False
        if not self.enabled_types:
            return True  # Empty set means all enabled
        return root_cause_type in self.enabled_types

    def get_threshold(self, metric_category: str) -> float:
        """
        Get the effective threshold for a metric category.

        Categories: db_latency, db_error, dependency_latency, dependency_error, exception_surge, new_exception
        """
        # Start with base threshold
        threshold = self.base_threshold

        # Apply configured multiplier if exists
        if metric_category in self.multipliers:
            threshold *= self.multipliers[metric_category]
        # Also check partial matches (e.g., "db" matches "db_latency")
        else:
            for key, mult in self.multipliers.items():
                if metric_category.startswith(key) or key in metric_category:
                    threshold *= mult
                    break

        # Apply learned adjustment
        if self.config.adaptive_thresholds_enabled and metric_category in self.learned_adjustments:
            threshold += self.learned_adjustments[metric_category]

        return max(1.0, threshold)  # Never go below 1.0

    def learn_from_alert_history(self, executor: 'TrinoExecutor'):
        """
        Analyze alert history to adjust thresholds.

        - High auto-resolve rate + short duration -> likely false positives -> increase threshold
        - Alerts with investigations showing confirmed issues -> keep or lower threshold
        """
        if not self.config.adaptive_thresholds_enabled:
            return

        # Analyze alerts from last 7 days
        sql = """
            SELECT
                alert_type,
                metric_type,
                COUNT(*) as total_alerts,
                SUM(CASE WHEN auto_resolved = true THEN 1 ELSE 0 END) as auto_resolved_count
            FROM alerts
            WHERE created_at > current_timestamp - interval '7' day
            GROUP BY alert_type, metric_type
            HAVING COUNT(*) >= 5
        """
        try:
            results = executor.execute(sql)
        except Exception as e:
            print(f"[Adaptive] Could not analyze alert history: {e}")
            return

        for row in results:
            alert_type = row.get("alert_type", "")
            metric_type = row.get("metric_type", "")
            total = row.get("total_alerts", 0)
            auto_resolved = row.get("auto_resolved_count", 0)

            if total < 5:
                continue

            auto_resolve_rate = auto_resolved / total if total > 0 else 0

            # Determine the metric category
            category = self._get_metric_category(alert_type, metric_type)
            if not category:
                continue

            # High auto-resolve rate (>70%) suggests false positives - increase threshold
            if auto_resolve_rate > 0.7:
                adjustment = self.config.adaptive_threshold_adjustment
                self.learned_adjustments[category] = self.learned_adjustments.get(category, 0) + adjustment
                print(f"[Adaptive] Increasing threshold for {category} (auto-resolve rate: {auto_resolve_rate:.0%})")

            # Low auto-resolve rate (<30%) with many alerts - might be too sensitive
            elif auto_resolve_rate < 0.3 and total > 20:
                # Check if these led to investigations with findings
                inv_sql = f"""
                    SELECT COUNT(*) as investigated
                    FROM alert_investigations
                    WHERE alert_type = '{alert_type}'
                    AND investigated_at > current_timestamp - interval '7' day
                    AND root_cause_summary IS NOT NULL AND root_cause_summary != ''
                """
                inv_result = executor.execute(inv_sql)
                investigated = inv_result[0].get("investigated", 0) if inv_result else 0

                # If most alerts weren't investigated or had findings, they're valuable
                if investigated > total * 0.3:
                    # Keep threshold as is or slightly lower
                    adjustment = -self.config.adaptive_threshold_adjustment * 0.5
                    self.learned_adjustments[category] = self.learned_adjustments.get(category, 0) + adjustment
                    print(f"[Adaptive] Decreasing threshold for {category} (valuable alerts)")

        # Cap adjustments to prevent runaway
        for category in self.learned_adjustments:
            self.learned_adjustments[category] = max(-1.0, min(1.0, self.learned_adjustments[category]))

    def _get_metric_category(self, alert_type: str, metric_type: str) -> str:
        """Map alert/metric type to a threshold category."""
        if "db_" in alert_type.lower() or metric_type.startswith("db_"):
            if "latency" in metric_type.lower():
                return "db_latency"
            elif "error" in metric_type.lower():
                return "db_error"
        elif "dependency" in alert_type.lower() or metric_type.startswith("dep_"):
            if "latency" in metric_type.lower():
                return "dependency_latency"
            elif "error" in metric_type.lower() or "rate" in metric_type.lower():
                return "dependency_error"
        elif "exception" in alert_type.lower():
            if "new_exception" in alert_type.lower():
                return "new_exception"
            return "exception_surge"
        return ""


# =============================================================================
# Trino Query Executor
# =============================================================================

class TrinoExecutor:
    """Executes SQL queries against VastDB via Trino."""

    def __init__(self, config: Config):
        self.config = config
        self._conn = None
        self._connect()

    def _connect(self):
        """Establish connection to Trino."""
        auth = None
        if self.config.trino_password:
            auth = BasicAuthentication(self.config.trino_user, self.config.trino_password)

        self._conn = trino_connect(
            host=self.config.trino_host,
            port=self.config.trino_port,
            user=self.config.trino_user,
            catalog=self.config.trino_catalog,
            schema=self.config.trino_schema,
            http_scheme=self.config.trino_http_scheme,
            auth=auth,
            verify=False,
        )
        print(f"[Trino] Connected to {self.config.trino_host}")

    def execute(self, sql: str, return_error: bool = False) -> List[Dict[str, Any]]:
        """Execute a query and return results as list of dicts.

        If return_error=True, returns [{"error": "message"}] on failure instead of [].
        """
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql)

            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
            return []
        except Exception as e:
            error_msg = str(e)
            print(f"[Trino] Query error: {error_msg}")
            # Try to reconnect on connection errors
            if "connection" in error_msg.lower():
                self._connect()
            if return_error:
                return [{"error": error_msg}]
            return []

    def execute_write(self, sql: str) -> bool:
        """Execute a write query (INSERT/UPDATE/DELETE)."""
        try:
            cursor = self._conn.cursor()
            cursor.execute(sql)
            return True
        except Exception as e:
            print(f"[Trino] Write error: {e}")
            return False


# =============================================================================
# Baseline Computer
# =============================================================================

class BaselineComputer:
    """Computes statistical baselines from historical data."""

    def __init__(self, executor: TrinoExecutor, config: Config):
        self.executor = executor
        self.config = config
        self.baselines: Dict[str, Dict[str, Dict]] = {}  # service -> metric_type -> baseline

    def compute_all_baselines(self) -> Dict[str, Dict[str, Dict]]:
        """Compute baselines for all services and metrics."""
        print("[Baseline] Computing baselines...")

        # Get list of active services
        services = self._get_active_services()
        print(f"[Baseline] Found {len(services)} active services")

        for service in services:
            self.baselines[service] = {}

            # Compute error rate baseline
            error_baseline = self._compute_error_rate_baseline(service)
            if error_baseline:
                self.baselines[service]["error_rate"] = error_baseline
                self._store_baseline(service, "error_rate", error_baseline)

            # Compute latency baselines
            for percentile in ["p50", "p95", "p99"]:
                latency_baseline = self._compute_latency_baseline(service, percentile)
                if latency_baseline:
                    metric_type = f"latency_{percentile}"
                    self.baselines[service][metric_type] = latency_baseline
                    self._store_baseline(service, metric_type, latency_baseline)

            # Compute throughput baseline
            throughput_baseline = self._compute_throughput_baseline(service)
            if throughput_baseline:
                self.baselines[service]["throughput"] = throughput_baseline
                self._store_baseline(service, "throughput", throughput_baseline)

            # === ROOT CAUSE BASELINES ===

            # Compute database query baselines for this service
            db_baselines = self._compute_db_query_baselines(service)
            for db_metric, baseline in db_baselines.items():
                self.baselines[service][db_metric] = baseline
                self._store_baseline(service, db_metric, baseline)

            # Compute exception rate baseline
            exception_baseline = self._compute_exception_rate_baseline(service)
            if exception_baseline:
                self.baselines[service]["exception_rate"] = exception_baseline
                self._store_baseline(service, "exception_rate", exception_baseline)

            # Compute dependency latency baselines
            dep_baselines = self._compute_dependency_baselines(service)
            for dep_metric, baseline in dep_baselines.items():
                self.baselines[service][dep_metric] = baseline
                self._store_baseline(service, dep_metric, baseline)

        # Store known exception types across all services
        self._compute_known_exception_types()

        print(f"[Baseline] Computed baselines for {len(self.baselines)} services")
        return self.baselines

    def _get_active_services(self) -> List[str]:
        """Get list of services that have recent data."""
        sql = f"""
            SELECT DISTINCT service_name
            FROM traces_otel_analytic
            WHERE start_time > current_timestamp - interval '{self.config.baseline_window_hours}' hour
            AND service_name IS NOT NULL
            AND service_name != ''
        """
        results = self.executor.execute(sql)
        return [r["service_name"] for r in results]

    def _compute_error_rate_baseline(self, service: str) -> Optional[Dict]:
        """Compute error rate baseline for a service."""
        sql = f"""
            SELECT
                date_trunc('hour', start_time) as hour,
                COUNT(*) as total,
                SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) as errors,
                CAST(SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as error_rate
            FROM traces_otel_analytic
            WHERE service_name = '{service}'
            AND start_time > current_timestamp - interval '{self.config.baseline_window_hours}' hour
            GROUP BY date_trunc('hour', start_time)
            HAVING COUNT(*) >= 10
            ORDER BY hour
        """
        results = self.executor.execute(sql)

        if len(results) < self.config.min_samples_for_baseline:
            return None

        error_rates = [r["error_rate"] for r in results if r["error_rate"] is not None]
        return self._compute_stats(error_rates)

    def _compute_latency_baseline(self, service: str, percentile: str) -> Optional[Dict]:
        """Compute latency baseline for a service."""
        pct_value = {"p50": 0.5, "p95": 0.95, "p99": 0.99}[percentile]

        sql = f"""
            SELECT
                date_trunc('hour', start_time) as hour,
                approx_percentile(duration_ns / 1e6, {pct_value}) as latency_ms
            FROM traces_otel_analytic
            WHERE service_name = '{service}'
            AND start_time > current_timestamp - interval '{self.config.baseline_window_hours}' hour
            AND duration_ns > 0
            GROUP BY date_trunc('hour', start_time)
            HAVING COUNT(*) >= 10
            ORDER BY hour
        """
        results = self.executor.execute(sql)

        if len(results) < self.config.min_samples_for_baseline:
            return None

        latencies = [r["latency_ms"] for r in results if r["latency_ms"] is not None]
        return self._compute_stats(latencies)

    def _compute_throughput_baseline(self, service: str) -> Optional[Dict]:
        """Compute throughput (requests per minute) baseline."""
        sql = f"""
            SELECT
                date_trunc('minute', start_time) as minute,
                COUNT(*) as requests
            FROM traces_otel_analytic
            WHERE service_name = '{service}'
            AND start_time > current_timestamp - interval '{self.config.baseline_window_hours}' hour
            AND span_kind = 'SERVER'
            GROUP BY date_trunc('minute', start_time)
            ORDER BY minute
        """
        results = self.executor.execute(sql)

        if len(results) < self.config.min_samples_for_baseline:
            return None

        throughputs = [r["requests"] for r in results if r["requests"] is not None]
        return self._compute_stats(throughputs)

    def _compute_stats(self, values: List[float]) -> Optional[Dict]:
        """Compute statistical measures from a list of values."""
        if not values or len(values) < 2:
            return None

        sorted_values = sorted(values)
        n = len(sorted_values)

        mean = statistics.mean(values)
        stddev = statistics.stdev(values) if len(values) > 1 else 0

        return {
            "mean": mean,
            "stddev": stddev,
            "min": min(values),
            "max": max(values),
            "p50": sorted_values[int(n * 0.5)],
            "p95": sorted_values[int(n * 0.95)] if n > 20 else sorted_values[-1],
            "p99": sorted_values[int(n * 0.99)] if n > 100 else sorted_values[-1],
            "sample_count": n,
        }

    def _store_baseline(self, service: str, metric_type: str, baseline: Dict):
        """Store baseline in database."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        sql = f"""
            INSERT INTO service_baselines (
                computed_at, service_name, metric_type,
                baseline_mean, baseline_stddev, baseline_min, baseline_max,
                baseline_p50, baseline_p95, baseline_p99,
                sample_count, window_hours
            ) VALUES (
                TIMESTAMP '{now}', '{service}', '{metric_type}',
                {baseline['mean']}, {baseline['stddev']}, {baseline['min']}, {baseline['max']},
                {baseline['p50']}, {baseline['p95']}, {baseline['p99']},
                {baseline['sample_count']}, {self.config.baseline_window_hours}
            )
        """
        self.executor.execute_write(sql)

    def get_baseline(self, service: str, metric_type: str) -> Optional[Dict]:
        """Get baseline for a service/metric, computing if needed."""
        if service in self.baselines and metric_type in self.baselines[service]:
            return self.baselines[service][metric_type]
        return None

    # =========================================================================
    # ROOT CAUSE BASELINE METHODS
    # =========================================================================

    def _compute_db_query_baselines(self, service: str) -> Dict[str, Dict]:
        """Compute database query latency and error rate baselines per db_system."""
        baselines = {}

        # Get database systems this service uses
        db_systems_sql = f"""
            SELECT DISTINCT db_system
            FROM traces_otel_analytic
            WHERE service_name = '{service}'
            AND db_system IS NOT NULL AND db_system != ''
            AND start_time > current_timestamp - interval '{self.config.baseline_window_hours}' hour
        """
        db_systems = self.executor.execute(db_systems_sql)

        for row in db_systems:
            db_system = row["db_system"]

            # Database query latency baseline
            latency_sql = f"""
                SELECT
                    date_trunc('hour', start_time) as hour,
                    approx_percentile(duration_ns / 1e6, 0.95) as latency_p95
                FROM traces_otel_analytic
                WHERE service_name = '{service}'
                AND db_system = '{db_system}'
                AND start_time > current_timestamp - interval '{self.config.baseline_window_hours}' hour
                AND duration_ns > 0
                GROUP BY date_trunc('hour', start_time)
                HAVING COUNT(*) >= 5
                ORDER BY hour
            """
            latency_results = self.executor.execute(latency_sql)

            if len(latency_results) >= self.config.min_samples_for_baseline:
                latencies = [r["latency_p95"] for r in latency_results if r["latency_p95"] is not None]
                if latencies:
                    stats = self._compute_stats(latencies)
                    if stats:
                        baselines[f"db_{db_system}_latency"] = stats

            # Database error rate baseline
            error_sql = f"""
                SELECT
                    date_trunc('hour', start_time) as hour,
                    COUNT(*) as total,
                    SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) as errors,
                    CAST(SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as error_rate
                FROM traces_otel_analytic
                WHERE service_name = '{service}'
                AND db_system = '{db_system}'
                AND start_time > current_timestamp - interval '{self.config.baseline_window_hours}' hour
                GROUP BY date_trunc('hour', start_time)
                HAVING COUNT(*) >= 5
                ORDER BY hour
            """
            error_results = self.executor.execute(error_sql)

            if len(error_results) >= self.config.min_samples_for_baseline:
                error_rates = [r["error_rate"] for r in error_results if r["error_rate"] is not None]
                if error_rates:
                    stats = self._compute_stats(error_rates)
                    if stats:
                        baselines[f"db_{db_system}_error_rate"] = stats

        return baselines

    def _compute_exception_rate_baseline(self, service: str) -> Optional[Dict]:
        """Compute exception rate baseline from span events."""
        sql = f"""
            SELECT
                date_trunc('hour', timestamp) as hour,
                COUNT(*) as exception_count
            FROM span_events_otel_analytic
            WHERE service_name = '{service}'
            AND exception_type IS NOT NULL AND exception_type != ''
            AND timestamp > current_timestamp - interval '{self.config.baseline_window_hours}' hour
            GROUP BY date_trunc('hour', timestamp)
            ORDER BY hour
        """
        results = self.executor.execute(sql)

        if len(results) < self.config.min_samples_for_baseline:
            return None

        counts = [r["exception_count"] for r in results if r["exception_count"] is not None]
        return self._compute_stats(counts) if counts else None

    def _compute_dependency_baselines(self, service: str) -> Dict[str, Dict]:
        """Compute latency and error rate baselines for downstream dependencies."""
        baselines = {}

        # Find downstream services this service calls
        deps_sql = f"""
            SELECT DISTINCT child.service_name as dependency
            FROM traces_otel_analytic parent
            JOIN traces_otel_analytic child
                ON parent.span_id = child.parent_span_id
                AND parent.trace_id = child.trace_id
            WHERE parent.service_name = '{service}'
            AND child.service_name != '{service}'
            AND child.service_name IS NOT NULL
            AND child.db_system IS NULL
            AND parent.start_time > current_timestamp - interval '{self.config.baseline_window_hours}' hour
        """
        deps = self.executor.execute(deps_sql)

        for row in deps:
            dep_service = row["dependency"]

            # Dependency call latency baseline
            latency_sql = f"""
                SELECT
                    date_trunc('hour', child.start_time) as hour,
                    approx_percentile(child.duration_ns / 1e6, 0.95) as latency_p95
                FROM traces_otel_analytic parent
                JOIN traces_otel_analytic child
                    ON parent.span_id = child.parent_span_id
                    AND parent.trace_id = child.trace_id
                WHERE parent.service_name = '{service}'
                AND child.service_name = '{dep_service}'
                AND parent.start_time > current_timestamp - interval '{self.config.baseline_window_hours}' hour
                AND child.duration_ns > 0
                GROUP BY date_trunc('hour', child.start_time)
                HAVING COUNT(*) >= 5
                ORDER BY hour
            """
            latency_results = self.executor.execute(latency_sql)

            if len(latency_results) >= self.config.min_samples_for_baseline:
                latencies = [r["latency_p95"] for r in latency_results if r["latency_p95"] is not None]
                if latencies:
                    stats = self._compute_stats(latencies)
                    if stats:
                        baselines[f"dep_{dep_service}_latency"] = stats

            # Dependency error rate baseline
            error_sql = f"""
                SELECT
                    date_trunc('hour', child.start_time) as hour,
                    COUNT(*) as total,
                    SUM(CASE WHEN child.status_code = 'ERROR' THEN 1 ELSE 0 END) as errors,
                    CAST(SUM(CASE WHEN child.status_code = 'ERROR' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as error_rate
                FROM traces_otel_analytic parent
                JOIN traces_otel_analytic child
                    ON parent.span_id = child.parent_span_id
                    AND parent.trace_id = child.trace_id
                WHERE parent.service_name = '{service}'
                AND child.service_name = '{dep_service}'
                AND parent.start_time > current_timestamp - interval '{self.config.baseline_window_hours}' hour
                GROUP BY date_trunc('hour', child.start_time)
                HAVING COUNT(*) >= 5
                ORDER BY hour
            """
            error_results = self.executor.execute(error_sql)

            if len(error_results) >= self.config.min_samples_for_baseline:
                error_rates = [r["error_rate"] for r in error_results if r["error_rate"] is not None]
                if error_rates:
                    stats = self._compute_stats(error_rates)
                    if stats:
                        baselines[f"dep_{dep_service}_error_rate"] = stats

        return baselines

    def _compute_known_exception_types(self):
        """Track known exception types per service for new exception detection."""
        sql = f"""
            SELECT service_name, exception_type, COUNT(*) as count
            FROM span_events_otel_analytic
            WHERE exception_type IS NOT NULL AND exception_type != ''
            AND timestamp > current_timestamp - interval '{self.config.baseline_window_hours}' hour
            GROUP BY service_name, exception_type
            HAVING COUNT(*) >= 3
        """
        results = self.executor.execute(sql)

        # Store known exception types per service
        self.known_exception_types: Dict[str, set] = {}
        for row in results:
            service = row["service_name"]
            exc_type = row["exception_type"]
            if service not in self.known_exception_types:
                self.known_exception_types[service] = set()
            self.known_exception_types[service].add(exc_type)

        total_types = sum(len(v) for v in self.known_exception_types.values())
        print(f"[Baseline] Tracked {total_types} known exception types across {len(self.known_exception_types)} services")

    def get_known_exception_types(self, service: str) -> set:
        """Get known exception types for a service."""
        return getattr(self, 'known_exception_types', {}).get(service, set())


# =============================================================================
# Anomaly Detector
# =============================================================================

class AnomalyDetector:
    """Detects anomalies using multiple methods."""

    def __init__(self, executor: TrinoExecutor, config: Config, baseline_computer: BaselineComputer):
        self.executor = executor
        self.config = config
        self.baseline_computer = baseline_computer

        # Adaptive threshold manager for root cause detection
        self.threshold_manager = AdaptiveThresholdManager(config)

        # Isolation Forest model (if sklearn available)
        self.isolation_forest = None
        if SKLEARN_AVAILABLE:
            self.isolation_forest = IsolationForest(
                contamination=0.1,
                random_state=42,
                n_estimators=100
            )

    def learn_thresholds(self):
        """Learn adaptive thresholds from alert history."""
        self.threshold_manager.learn_from_alert_history(self.executor)

    def detect_all(self) -> List[Dict]:
        """Run all anomaly detection methods and return detected anomalies."""
        anomalies = []

        # Get current metrics for all services
        services = list(self.baseline_computer.baselines.keys())

        for service in services:
            # === SYMPTOM-BASED DETECTION (existing) ===

            # Check error rate
            error_anomaly = self._detect_error_rate_anomaly(service)
            if error_anomaly:
                anomalies.append(error_anomaly)

            # Check latency
            latency_anomaly = self._detect_latency_anomaly(service)
            if latency_anomaly:
                anomalies.append(latency_anomaly)

            # Check throughput drop
            throughput_anomaly = self._detect_throughput_anomaly(service)
            if throughput_anomaly:
                anomalies.append(throughput_anomaly)

            # Check for service down
            down_anomaly = self._detect_service_down(service)
            if down_anomaly:
                anomalies.append(down_anomaly)

            # === ROOT CAUSE DETECTION (new - configurable) ===
            if self.config.root_cause_enabled:
                # Check database health issues
                if self.threshold_manager.is_root_cause_enabled("db_latency") or \
                   self.threshold_manager.is_root_cause_enabled("db_error"):
                    db_anomalies = self._detect_database_issues(service)
                    anomalies.extend(db_anomalies)

                # Check dependency health issues
                if self.threshold_manager.is_root_cause_enabled("dependency_latency") or \
                   self.threshold_manager.is_root_cause_enabled("dependency_error"):
                    dep_anomalies = self._detect_dependency_issues(service)
                    anomalies.extend(dep_anomalies)

                # Check exception patterns
                if self.threshold_manager.is_root_cause_enabled("exception_surge") or \
                   self.threshold_manager.is_root_cause_enabled("new_exception"):
                    exc_anomalies = self._detect_exception_issues(service)
                    anomalies.extend(exc_anomalies)

        return anomalies

    def _detect_error_rate_anomaly(self, service: str) -> Optional[Dict]:
        """Detect error rate spikes."""
        # Get current error rate (last 5 minutes)
        sql = f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) as errors,
                CAST(SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) AS DOUBLE) /
                    NULLIF(COUNT(*), 0) as error_rate
            FROM traces_otel_analytic
            WHERE service_name = '{service}'
            AND start_time > current_timestamp - interval '5' minute
        """
        results = self.executor.execute(sql)

        if not results or results[0]["total"] < 5:
            return None

        current_rate = results[0]["error_rate"] or 0
        baseline = self.baseline_computer.get_baseline(service, "error_rate")

        # Determine severity based on absolute thresholds and Z-score
        severity = None
        z_score = 0

        if baseline and baseline["stddev"] > 0:
            z_score = (current_rate - baseline["mean"]) / baseline["stddev"]

            if z_score > self.config.zscore_threshold:
                severity = Severity.WARNING
            if z_score > self.config.zscore_threshold * 1.5:
                severity = Severity.CRITICAL

        # Also check absolute thresholds
        if current_rate >= self.config.error_rate_critical:
            severity = Severity.CRITICAL
        elif current_rate >= self.config.error_rate_warning and severity is None:
            severity = Severity.WARNING

        if severity:
            self._store_anomaly_score(
                service, "error_rate", current_rate,
                baseline["mean"] if baseline else 0,
                baseline["mean"] if baseline else 0,
                baseline["stddev"] if baseline else 0,
                z_score, True, "zscore"
            )

            return {
                "service": service,
                "metric_type": "error_rate",
                "alert_type": AlertType.ERROR_SPIKE,
                "severity": severity,
                "current_value": current_rate,
                "baseline_value": baseline["mean"] if baseline else 0,
                "z_score": z_score,
                "message": f"Error rate {current_rate:.1%} exceeds baseline {baseline['mean']:.1%}" if baseline
                          else f"Error rate {current_rate:.1%} exceeds threshold"
            }

        return None

    def _detect_latency_anomaly(self, service: str) -> Optional[Dict]:
        """Detect latency degradation."""
        # Get current P95 latency
        sql = f"""
            SELECT
                approx_percentile(duration_ns / 1e6, 0.95) as latency_p95
            FROM traces_otel_analytic
            WHERE service_name = '{service}'
            AND start_time > current_timestamp - interval '5' minute
            AND duration_ns > 0
            HAVING COUNT(*) >= 5
        """
        results = self.executor.execute(sql)

        if not results or results[0]["latency_p95"] is None:
            return None

        current_latency = results[0]["latency_p95"]
        baseline = self.baseline_computer.get_baseline(service, "latency_p95")

        if not baseline or baseline["stddev"] == 0:
            return None

        z_score = (current_latency - baseline["mean"]) / baseline["stddev"]

        if z_score > self.config.zscore_threshold:
            severity = Severity.WARNING if z_score < self.config.zscore_threshold * 1.5 else Severity.CRITICAL

            self._store_anomaly_score(
                service, "latency_p95", current_latency,
                baseline["mean"], baseline["mean"], baseline["stddev"],
                z_score, True, "zscore"
            )

            return {
                "service": service,
                "metric_type": "latency_p95",
                "alert_type": AlertType.LATENCY_DEGRADATION,
                "severity": severity,
                "current_value": current_latency,
                "baseline_value": baseline["mean"],
                "z_score": z_score,
                "message": f"P95 latency {current_latency:.0f}ms exceeds baseline {baseline['mean']:.0f}ms (z={z_score:.1f})"
            }

        return None

    def _detect_throughput_anomaly(self, service: str) -> Optional[Dict]:
        """Detect throughput drops (potential upstream issues)."""
        # Get current throughput (requests per minute)
        sql = f"""
            SELECT COUNT(*) as requests
            FROM traces_otel_analytic
            WHERE service_name = '{service}'
            AND start_time > current_timestamp - interval '5' minute
            AND span_kind = 'SERVER'
        """
        results = self.executor.execute(sql)

        if not results:
            return None

        # Normalize to per-minute
        current_throughput = results[0]["requests"] / 5.0
        baseline = self.baseline_computer.get_baseline(service, "throughput")

        if not baseline or baseline["stddev"] == 0 or baseline["mean"] < 1:
            return None

        # For throughput, we care about drops (negative z-score)
        z_score = (current_throughput - baseline["mean"]) / baseline["stddev"]

        # Throughput drop is concerning when significantly below baseline
        if z_score < -self.config.zscore_threshold:
            severity = Severity.WARNING if z_score > -self.config.zscore_threshold * 1.5 else Severity.CRITICAL

            self._store_anomaly_score(
                service, "throughput", current_throughput,
                baseline["mean"], baseline["mean"], baseline["stddev"],
                z_score, True, "zscore"
            )

            pct_drop = (baseline["mean"] - current_throughput) / baseline["mean"] * 100

            return {
                "service": service,
                "metric_type": "throughput",
                "alert_type": AlertType.THROUGHPUT_DROP,
                "severity": severity,
                "current_value": current_throughput,
                "baseline_value": baseline["mean"],
                "z_score": z_score,
                "message": f"Throughput dropped {pct_drop:.0f}% ({current_throughput:.0f}/min vs {baseline['mean']:.0f}/min baseline)"
            }

        return None

    def _detect_service_down(self, service: str) -> Optional[Dict]:
        """Detect if a service has stopped sending data."""
        sql = f"""
            SELECT
                MAX(start_time) as last_seen,
                current_timestamp - MAX(start_time) as time_since
            FROM traces_otel_analytic
            WHERE service_name = '{service}'
            AND start_time > current_timestamp - interval '1' hour
        """
        results = self.executor.execute(sql)

        if not results or results[0]["last_seen"] is None:
            # No data in the last hour - service may be down
            return {
                "service": service,
                "metric_type": "availability",
                "alert_type": AlertType.SERVICE_DOWN,
                "severity": Severity.CRITICAL,
                "current_value": 0,
                "baseline_value": 1,
                "z_score": 0,
                "message": f"Service {service} has not sent telemetry in over 1 hour"
            }

        return None

    def _store_anomaly_score(
        self, service: str, metric_type: str, current_value: float,
        expected_value: float, baseline_mean: float, baseline_stddev: float,
        z_score: float, is_anomaly: bool, detection_method: str
    ):
        """Store anomaly score in database."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        anomaly_score = min(1.0, abs(z_score) / 5.0)  # Normalize z-score to 0-1

        sql = f"""
            INSERT INTO anomaly_scores (
                timestamp, service_name, metric_type,
                current_value, expected_value, baseline_mean, baseline_stddev,
                z_score, anomaly_score, is_anomaly, detection_method
            ) VALUES (
                TIMESTAMP '{now}', '{service}', '{metric_type}',
                {current_value}, {expected_value}, {baseline_mean}, {baseline_stddev},
                {z_score}, {anomaly_score}, {str(is_anomaly).lower()}, '{detection_method}'
            )
        """
        self.executor.execute_write(sql)

    # =========================================================================
    # ROOT CAUSE DETECTION METHODS
    # =========================================================================

    def _detect_database_issues(self, service: str) -> List[Dict]:
        """Detect database-related root causes: slow queries, connection failures."""
        anomalies = []

        # Get all database baselines for this service
        service_baselines = self.baseline_computer.baselines.get(service, {})
        db_metrics = [k for k in service_baselines.keys() if k.startswith("db_")]

        for metric in db_metrics:
            # Parse db_system from metric name (e.g., "db_postgresql_latency" -> "postgresql")
            parts = metric.split("_")
            if len(parts) < 3:
                continue

            db_system = parts[1]
            metric_type_suffix = parts[2]  # "latency" or "error_rate"

            baseline = service_baselines[metric]

            if metric_type_suffix == "latency":
                # Check database query latency
                sql = f"""
                    SELECT approx_percentile(duration_ns / 1e6, 0.95) as latency_p95
                    FROM traces_otel_analytic
                    WHERE service_name = '{service}'
                    AND db_system = '{db_system}'
                    AND start_time > current_timestamp - interval '5' minute
                    AND duration_ns > 0
                    HAVING COUNT(*) >= 3
                """
                results = self.executor.execute(sql)

                if results and results[0].get("latency_p95") is not None:
                    current_latency = results[0]["latency_p95"]

                    if baseline["stddev"] > 0:
                        z_score = (current_latency - baseline["mean"]) / baseline["stddev"]
                        threshold = self.threshold_manager.get_threshold("db_latency")

                        if z_score > threshold:
                            severity = Severity.WARNING if z_score < threshold * 1.5 else Severity.CRITICAL

                            self._store_anomaly_score(
                                service, metric, current_latency,
                                baseline["mean"], baseline["mean"], baseline["stddev"],
                                z_score, True, "zscore"
                            )

                            anomalies.append({
                                "service": service,
                                "metric_type": metric,
                                "alert_type": AlertType.DB_SLOW_QUERIES,
                                "severity": severity,
                                "current_value": current_latency,
                                "baseline_value": baseline["mean"],
                                "z_score": z_score,
                                "message": f"Database {db_system} queries slow: {current_latency:.0f}ms P95 (baseline: {baseline['mean']:.0f}ms, z={z_score:.1f})"
                            })

            elif metric_type_suffix == "error" or metric.endswith("_error_rate"):
                # Check database error rate (connection failures, query errors)
                sql = f"""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) as errors,
                        CAST(SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) AS DOUBLE) /
                            NULLIF(COUNT(*), 0) as error_rate
                    FROM traces_otel_analytic
                    WHERE service_name = '{service}'
                    AND db_system = '{db_system}'
                    AND start_time > current_timestamp - interval '5' minute
                """
                results = self.executor.execute(sql)

                if results and results[0].get("total", 0) >= 3:
                    current_rate = results[0].get("error_rate") or 0

                    if baseline["stddev"] > 0:
                        z_score = (current_rate - baseline["mean"]) / baseline["stddev"]
                        threshold = self.threshold_manager.get_threshold("db_error")

                        # Database errors use adaptive threshold
                        if z_score > threshold or current_rate > 0.1:
                            severity = Severity.CRITICAL if current_rate > 0.2 or z_score > threshold * 1.5 else Severity.WARNING

                            self._store_anomaly_score(
                                service, metric, current_rate,
                                baseline["mean"], baseline["mean"], baseline["stddev"],
                                z_score, True, "zscore"
                            )

                            anomalies.append({
                                "service": service,
                                "metric_type": metric,
                                "alert_type": AlertType.DB_CONNECTION_FAILURE,
                                "severity": severity,
                                "current_value": current_rate,
                                "baseline_value": baseline["mean"],
                                "z_score": z_score,
                                "message": f"Database {db_system} errors: {current_rate:.1%} error rate (baseline: {baseline['mean']:.1%})"
                            })

        return anomalies

    def _detect_dependency_issues(self, service: str) -> List[Dict]:
        """Detect dependency-related root causes: downstream service failures, latency."""
        anomalies = []

        # Get all dependency baselines for this service
        service_baselines = self.baseline_computer.baselines.get(service, {})
        dep_metrics = [k for k in service_baselines.keys() if k.startswith("dep_")]

        for metric in dep_metrics:
            # Parse dependency service from metric name (e.g., "dep_auth-service_latency")
            parts = metric.split("_")
            if len(parts) < 3:
                continue

            # Handle service names with underscores
            dep_service = "_".join(parts[1:-1])
            metric_type_suffix = parts[-1]  # "latency" or "error_rate"

            baseline = service_baselines[metric]

            if metric_type_suffix == "latency":
                # Check dependency call latency
                sql = f"""
                    SELECT approx_percentile(child.duration_ns / 1e6, 0.95) as latency_p95
                    FROM traces_otel_analytic parent
                    JOIN traces_otel_analytic child
                        ON parent.span_id = child.parent_span_id
                        AND parent.trace_id = child.trace_id
                    WHERE parent.service_name = '{service}'
                    AND child.service_name = '{dep_service}'
                    AND parent.start_time > current_timestamp - interval '5' minute
                    AND child.duration_ns > 0
                    HAVING COUNT(*) >= 3
                """
                results = self.executor.execute(sql)

                if results and results[0].get("latency_p95") is not None:
                    current_latency = results[0]["latency_p95"]

                    if baseline["stddev"] > 0:
                        z_score = (current_latency - baseline["mean"]) / baseline["stddev"]
                        threshold = self.threshold_manager.get_threshold("dependency_latency")

                        if z_score > threshold:
                            severity = Severity.WARNING if z_score < threshold * 1.5 else Severity.CRITICAL

                            self._store_anomaly_score(
                                service, metric, current_latency,
                                baseline["mean"], baseline["mean"], baseline["stddev"],
                                z_score, True, "zscore"
                            )

                            anomalies.append({
                                "service": service,
                                "metric_type": metric,
                                "alert_type": AlertType.DEPENDENCY_LATENCY,
                                "severity": severity,
                                "current_value": current_latency,
                                "baseline_value": baseline["mean"],
                                "z_score": z_score,
                                "message": f"Dependency {dep_service} slow: {current_latency:.0f}ms P95 (baseline: {baseline['mean']:.0f}ms, z={z_score:.1f})"
                            })

            elif metric_type_suffix == "rate":  # error_rate
                # Check dependency error rate
                sql = f"""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN child.status_code = 'ERROR' THEN 1 ELSE 0 END) as errors,
                        CAST(SUM(CASE WHEN child.status_code = 'ERROR' THEN 1 ELSE 0 END) AS DOUBLE) /
                            NULLIF(COUNT(*), 0) as error_rate
                    FROM traces_otel_analytic parent
                    JOIN traces_otel_analytic child
                        ON parent.span_id = child.parent_span_id
                        AND parent.trace_id = child.trace_id
                    WHERE parent.service_name = '{service}'
                    AND child.service_name = '{dep_service}'
                    AND parent.start_time > current_timestamp - interval '5' minute
                """
                results = self.executor.execute(sql)

                if results and results[0].get("total", 0) >= 3:
                    current_rate = results[0].get("error_rate") or 0

                    if baseline["stddev"] > 0:
                        z_score = (current_rate - baseline["mean"]) / baseline["stddev"]
                        threshold = self.threshold_manager.get_threshold("dependency_error")

                        if z_score > threshold or current_rate > 0.15:
                            severity = Severity.CRITICAL if current_rate > 0.25 or z_score > threshold * 1.5 else Severity.WARNING

                            self._store_anomaly_score(
                                service, metric, current_rate,
                                baseline["mean"], baseline["mean"], baseline["stddev"],
                                z_score, True, "zscore"
                            )

                            anomalies.append({
                                "service": service,
                                "metric_type": metric,
                                "alert_type": AlertType.DEPENDENCY_FAILURE,
                                "severity": severity,
                                "current_value": current_rate,
                                "baseline_value": baseline["mean"],
                                "z_score": z_score,
                                "message": f"Dependency {dep_service} failing: {current_rate:.1%} error rate (baseline: {baseline['mean']:.1%})"
                            })

        return anomalies

    def _detect_exception_issues(self, service: str) -> List[Dict]:
        """Detect exception-related root causes: surges and new exception types."""
        anomalies = []

        # Check exception rate surge
        baseline = self.baseline_computer.get_baseline(service, "exception_rate")
        if baseline:
            sql = f"""
                SELECT COUNT(*) as exception_count
                FROM span_events_otel_analytic
                WHERE service_name = '{service}'
                AND exception_type IS NOT NULL AND exception_type != ''
                AND timestamp > current_timestamp - interval '5' minute
            """
            results = self.executor.execute(sql)

            if results:
                # Normalize to hourly rate for comparison (5 min -> 1 hour = multiply by 12)
                current_count = results[0].get("exception_count", 0)
                current_hourly_rate = current_count * 12

                if baseline["stddev"] > 0 and current_hourly_rate > 0:
                    z_score = (current_hourly_rate - baseline["mean"]) / baseline["stddev"]
                    threshold = self.threshold_manager.get_threshold("exception_surge")

                    if z_score > threshold:
                        severity = Severity.WARNING if z_score < threshold * 1.5 else Severity.CRITICAL

                        self._store_anomaly_score(
                            service, "exception_rate", current_hourly_rate,
                            baseline["mean"], baseline["mean"], baseline["stddev"],
                            z_score, True, "zscore"
                        )

                        anomalies.append({
                            "service": service,
                            "metric_type": "exception_rate",
                            "alert_type": AlertType.EXCEPTION_SURGE,
                            "severity": severity,
                            "current_value": current_hourly_rate,
                            "baseline_value": baseline["mean"],
                            "z_score": z_score,
                            "message": f"Exception surge: {current_count} exceptions in 5 min (~{current_hourly_rate:.0f}/hour, baseline: {baseline['mean']:.0f}/hour)"
                        })

        # Check for new/unknown exception types
        known_types = self.baseline_computer.get_known_exception_types(service)
        if known_types:  # Only check if we have baseline exception types
            sql = f"""
                SELECT DISTINCT exception_type, COUNT(*) as count
                FROM span_events_otel_analytic
                WHERE service_name = '{service}'
                AND exception_type IS NOT NULL AND exception_type != ''
                AND timestamp > current_timestamp - interval '15' minute
                GROUP BY exception_type
                HAVING COUNT(*) >= 2
            """
            results = self.executor.execute(sql)

            for row in results:
                exc_type = row["exception_type"]
                exc_count = row["count"]

                if exc_type not in known_types:
                    # New exception type detected
                    anomalies.append({
                        "service": service,
                        "metric_type": f"new_exception:{exc_type[:50]}",
                        "alert_type": AlertType.NEW_EXCEPTION_TYPE,
                        "severity": Severity.WARNING,
                        "current_value": exc_count,
                        "baseline_value": 0,
                        "z_score": 0,
                        "message": f"New exception type detected: {exc_type} ({exc_count} occurrences in 15 min)"
                    })

        return anomalies


# =============================================================================
# Alert Manager
# =============================================================================

class AlertManager:
    """Manages alert lifecycle: creation, deduplication, and resolution."""

    def __init__(self, executor: TrinoExecutor, config: Config):
        self.executor = executor
        self.config = config
        self.active_alerts: Dict[str, Dict] = {}  # key -> alert
        self._load_active_alerts()

    def _load_active_alerts(self):
        """Load active alerts from database."""
        sql = """
            SELECT
                alert_id, service_name, alert_type, metric_type,
                created_at, severity, current_value
            FROM alerts
            WHERE status = 'active'
        """
        results = self.executor.execute(sql)

        for alert in results:
            key = self._alert_key(alert["service_name"], alert["alert_type"], alert["metric_type"])
            self.active_alerts[key] = alert

        print(f"[Alerts] Loaded {len(self.active_alerts)} active alerts")

    def _alert_key(self, service: str, alert_type: str, metric_type: str) -> str:
        """Generate unique key for alert deduplication."""
        return f"{service}:{alert_type}:{metric_type}"

    def process_anomalies(self, anomalies: List[Dict]) -> Tuple[int, int, List[Dict]]:
        """Process detected anomalies and create/update alerts. Returns (created, updated, new_alerts)."""
        created = 0
        updated = 0
        new_alerts = []

        seen_keys = set()

        for anomaly in anomalies:
            service = anomaly["service"]
            alert_type = anomaly["alert_type"].value
            metric_type = anomaly["metric_type"]
            key = self._alert_key(service, alert_type, metric_type)
            seen_keys.add(key)

            if key in self.active_alerts:
                # Update existing alert
                self._update_alert(key, anomaly)
                updated += 1
            else:
                # Check cooldown
                if not self._in_cooldown(service, alert_type, metric_type):
                    # Create new alert
                    alert_info = self._create_alert(anomaly)
                    if alert_info:
                        new_alerts.append(alert_info)
                    created += 1

        # Auto-resolve alerts that are no longer anomalous
        resolved = self._auto_resolve(seen_keys)

        if created or updated or resolved:
            print(f"[Alerts] Created: {created}, Updated: {updated}, Auto-resolved: {resolved}")

        return created, updated, new_alerts

    def _in_cooldown(self, service: str, alert_type: str, metric_type: str) -> bool:
        """Check if alert is in cooldown period after resolution."""
        sql = f"""
            SELECT created_at
            FROM alerts
            WHERE service_name = '{service}'
            AND alert_type = '{alert_type}'
            AND metric_type = '{metric_type}'
            AND status = 'resolved'
            AND resolved_at > current_timestamp - interval '{self.config.alert_cooldown_minutes}' minute
            ORDER BY resolved_at DESC
            LIMIT 1
        """
        results = self.executor.execute(sql)
        return len(results) > 0

    def _create_alert(self, anomaly: Dict) -> Optional[Dict]:
        """Create a new alert and return alert info for investigation."""
        alert_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        service = anomaly["service"]
        alert_type = anomaly["alert_type"].value
        severity = anomaly["severity"].value
        metric_type = anomaly["metric_type"]

        title = f"{alert_type.replace('_', ' ').title()} - {service}"
        description = anomaly["message"]

        sql = f"""
            INSERT INTO alerts (
                alert_id, created_at, updated_at, service_name,
                alert_type, severity, title, description,
                metric_type, current_value, threshold_value, baseline_value,
                z_score, status, auto_resolved
            ) VALUES (
                '{alert_id}', TIMESTAMP '{now}', TIMESTAMP '{now}', '{service}',
                '{alert_type}', '{severity}', '{title}', '{description}',
                '{metric_type}', {anomaly['current_value']}, 0, {anomaly['baseline_value']},
                {anomaly['z_score']}, 'active', false
            )
        """

        if self.executor.execute_write(sql):
            key = self._alert_key(service, alert_type, metric_type)
            alert_info = {
                "alert_id": alert_id,
                "service_name": service,
                "alert_type": alert_type,
                "metric_type": metric_type,
                "severity": severity,
                "description": description,
            }
            self.active_alerts[key] = alert_info
            print(f"[Alert] CREATED [{severity.upper()}] {title}: {description}")
            return alert_info
        return None

    def _update_alert(self, key: str, anomaly: Dict):
        """Update an existing alert with new values."""
        alert = self.active_alerts[key]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        sql = f"""
            UPDATE alerts
            SET updated_at = TIMESTAMP '{now}',
                current_value = {anomaly['current_value']},
                z_score = {anomaly['z_score']},
                severity = '{anomaly['severity'].value}'
            WHERE alert_id = '{alert['alert_id']}'
        """
        self.executor.execute_write(sql)

    def _auto_resolve(self, seen_keys: set) -> int:
        """Auto-resolve alerts that are no longer anomalous."""
        resolved = 0
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        keys_to_remove = []

        for key, alert in self.active_alerts.items():
            if key not in seen_keys:
                # Alert condition no longer present
                sql = f"""
                    UPDATE alerts
                    SET status = 'resolved',
                        resolved_at = TIMESTAMP '{now}',
                        auto_resolved = true
                    WHERE alert_id = '{alert['alert_id']}'
                """
                if self.executor.execute_write(sql):
                    keys_to_remove.append(key)
                    resolved += 1
                    print(f"[Alert] AUTO-RESOLVED: {alert['service_name']} - {alert['alert_type']}")

        for key in keys_to_remove:
            del self.active_alerts[key]

        return resolved


# =============================================================================
# Alert Investigator (LLM-powered root cause analysis)
# =============================================================================

INVESTIGATION_SYSTEM_PROMPT = """You are an expert SRE assistant performing automated root cause analysis for alerts.
You have access to observability data via SQL queries (Trino/Presto dialect). Analyze the alert and determine the root cause.

Available tables and their EXACT columns (use ONLY these columns):

traces_otel_analytic (time column: start_time):
  start_time, trace_id, span_id, parent_span_id, service_name, span_name,
  span_kind, status_code, http_status, duration_ns, db_system

logs_otel_analytic (time column: timestamp):
  timestamp, service_name, severity_number, severity_text, body_text, trace_id, span_id

span_events_otel_analytic (time column: timestamp):
  timestamp, trace_id, span_id, service_name, span_name, event_name,
  exception_type, exception_message, exception_stacktrace

metrics_otel_analytic (time column: timestamp):
  timestamp, service_name, metric_name, metric_unit, value_double

CRITICAL SQL RULES:
- For traces: WHERE start_time > current_timestamp - INTERVAL '15' MINUTE
- For logs/events/metrics: WHERE timestamp > current_timestamp - INTERVAL '15' MINUTE
- There is NO 'attributes' column - do not use it
- NO semicolons at end of queries
- NO square brackets [] anywhere
- Interval format: INTERVAL '15' MINUTE (number in quotes)

Your analysis should be CONCISE (under 500 words). Output format:
ROOT CAUSE: <one sentence summary>
EVIDENCE:
- <key finding 1>
- <key finding 2>
RECOMMENDED ACTIONS:
1. <action 1>
2. <action 2>
"""

class AlertInvestigator:
    """LLM-powered automatic investigation of alerts."""

    def __init__(self, executor: 'TrinoExecutor', config: Config):
        self.executor = executor
        self.config = config
        self.client = None
        self.enabled = False

        # Rate limiting: track investigation timestamps
        self.investigation_times: deque = deque(maxlen=100)
        # Per-service cooldown: service -> last investigation time
        self.service_last_investigated: Dict[str, datetime] = {}

        if ANTHROPIC_AVAILABLE and config.anthropic_api_key:
            self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
            self.enabled = True
            print(f"[Investigator] Enabled (model: {config.investigation_model}, max {config.max_investigations_per_hour}/hour)")
        else:
            print("[Investigator] Disabled (no ANTHROPIC_API_KEY)")

        self.tools = [{
            "name": "execute_sql",
            "description": "Execute a SQL query against the observability database",
            "input_schema": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "The SQL query to execute"
                    }
                },
                "required": ["sql"]
            }
        }]

    def should_investigate(self, alert: Dict) -> bool:
        """Check if we should investigate this alert (rate limits, cooldowns)."""
        if not self.enabled:
            return False

        service = alert.get("service_name", "")
        severity = alert.get("severity", "")

        # Check if critical-only mode
        if self.config.investigate_critical_only and severity != "critical":
            return False

        # Check hourly rate limit
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)

        # Remove old timestamps
        while self.investigation_times and self.investigation_times[0] < hour_ago:
            self.investigation_times.popleft()

        if len(self.investigation_times) >= self.config.max_investigations_per_hour:
            print(f"[Investigator] Rate limit reached ({self.config.max_investigations_per_hour}/hour)")
            return False

        # Check per-service cooldown
        if service in self.service_last_investigated:
            cooldown_until = self.service_last_investigated[service] + timedelta(
                minutes=self.config.investigation_service_cooldown_minutes
            )
            if now < cooldown_until:
                remaining = (cooldown_until - now).seconds // 60
                print(f"[Investigator] Service {service} in cooldown ({remaining}m remaining)")
                return False

        return True

    def investigate(self, alert: Dict) -> Optional[Dict]:
        """Investigate an alert and return findings."""
        if not self.should_investigate(alert):
            return None

        service = alert.get("service_name", "")
        alert_type = alert.get("alert_type", "")
        alert_id = alert.get("alert_id", "")
        description = alert.get("description", "")

        print(f"[Investigator] Starting investigation for {service} - {alert_type}")

        # Record investigation attempt
        now = datetime.now(timezone.utc)
        self.investigation_times.append(now)
        self.service_last_investigated[service] = now

        # Build investigation prompt
        user_prompt = f"""Investigate this alert:

Service: {service}
Alert Type: {alert_type}
Description: {description}

Find the root cause by querying the observability data. Focus on the last 15 minutes.
Start by checking for errors, exceptions, and anomalies in this service and its dependencies."""

        try:
            # Run investigation with tool use
            messages = [{"role": "user", "content": user_prompt}]
            queries_executed = 0
            total_tokens = 0

            for _ in range(5):  # Max 5 iterations
                response = self.client.messages.create(
                    model=self.config.investigation_model,
                    max_tokens=self.config.investigation_max_tokens,
                    system=INVESTIGATION_SYSTEM_PROMPT,
                    tools=self.tools,
                    messages=messages
                )

                total_tokens += response.usage.input_tokens + response.usage.output_tokens

                # Check for tool use
                tool_calls = [b for b in response.content if b.type == "tool_use"]

                if not tool_calls:
                    # No more tool calls, extract final response
                    break

                # Process tool calls
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for tool_call in tool_calls:
                    if tool_call.name == "execute_sql":
                        sql = tool_call.input.get("sql", "")
                        # Strip semicolons - Trino doesn't accept them
                        sql = sql.strip().rstrip(';')
                        queries_executed += 1

                        # Execute query with error reporting
                        result = self.executor.execute(sql, return_error=True)
                        result_str = json.dumps(result[:20] if len(result) > 20 else result, default=str)

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": result_str
                        })
                    else:
                        # Unknown tool - still need to respond
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": "Unknown tool",
                            "is_error": True
                        })

                messages.append({"role": "user", "content": tool_results})

            # Handle the conversation state before requesting final summary
            if response.stop_reason == "end_turn":
                # Last response was natural completion, add it and request summary
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": """Based on your investigation, provide your final analysis in this EXACT format:

ROOT CAUSE: <one sentence describing the root cause>

EVIDENCE:
- <finding 1>
- <finding 2>

RECOMMENDED ACTIONS:
1. <action 1>
2. <action 2>"""
                })
            else:
                # Last response had tool calls - need to get a natural completion first
                # The tool_results are already in messages, so just request completion
                summary_response = self.client.messages.create(
                    model=self.config.investigation_model,
                    max_tokens=self.config.investigation_max_tokens,
                    system=INVESTIGATION_SYSTEM_PROMPT,
                    tools=self.tools,
                    messages=messages
                )
                total_tokens += summary_response.usage.input_tokens + summary_response.usage.output_tokens
                messages.append({"role": "assistant", "content": summary_response.content})
                messages.append({
                    "role": "user",
                    "content": """Based on your investigation, provide your final analysis in this EXACT format:

ROOT CAUSE: <one sentence describing the root cause>

EVIDENCE:
- <finding 1>
- <finding 2>

RECOMMENDED ACTIONS:
1. <action 1>
2. <action 2>"""
                })

            # Get structured response (no tools)
            final_response = self.client.messages.create(
                model=self.config.investigation_model,
                max_tokens=self.config.investigation_max_tokens,
                system=INVESTIGATION_SYSTEM_PROMPT,
                messages=messages
            )
            total_tokens += final_response.usage.input_tokens + final_response.usage.output_tokens

            # Extract final analysis
            analysis = self._extract_text(final_response)

            # Parse into structured format
            root_cause, actions, evidence = self._parse_analysis(analysis)

            # Store investigation
            investigation_id = str(uuid.uuid4())[:8]
            self._store_investigation(
                investigation_id=investigation_id,
                alert_id=alert_id,
                service=service,
                alert_type=alert_type,
                root_cause=root_cause,
                actions=actions,
                evidence=evidence,
                queries_executed=queries_executed,
                tokens_used=total_tokens
            )

            print(f"[Investigator] Completed: {root_cause[:80]}...")

            return {
                "investigation_id": investigation_id,
                "root_cause_summary": root_cause,
                "recommended_actions": actions,
                "supporting_evidence": evidence,
                "queries_executed": queries_executed,
                "tokens_used": total_tokens
            }

        except Exception as e:
            print(f"[Investigator] Error: {e}")
            return None

    def _extract_text(self, response) -> str:
        """Extract text content from response."""
        text_parts = []
        for block in response.content:
            if hasattr(block, 'text'):
                text_parts.append(block.text)
        return "\n".join(text_parts)

    def _parse_analysis(self, analysis: str) -> Tuple[str, str, str]:
        """Parse the analysis into structured components."""
        root_cause = ""
        actions = ""
        evidence = ""

        lines = analysis.split("\n")
        current_section = None

        for line in lines:
            line_upper = line.upper().strip()
            if line_upper.startswith("ROOT CAUSE:"):
                current_section = "root_cause"
                root_cause = line.split(":", 1)[1].strip() if ":" in line else ""
            elif line_upper.startswith("EVIDENCE:") or line_upper.startswith("SUPPORTING EVIDENCE:"):
                current_section = "evidence"
            elif line_upper.startswith("RECOMMENDED ACTIONS:") or line_upper.startswith("ACTIONS:"):
                current_section = "actions"
            elif current_section == "root_cause" and line.strip() and not root_cause:
                root_cause = line.strip()
            elif current_section == "evidence":
                evidence += line + "\n"
            elif current_section == "actions":
                actions += line + "\n"

        # Fallback: use first sentence as root cause if not parsed
        if not root_cause and analysis:
            root_cause = analysis.split(".")[0][:200]

        return root_cause.strip(), actions.strip(), evidence.strip()

    def _store_investigation(
        self, investigation_id: str, alert_id: str, service: str, alert_type: str,
        root_cause: str, actions: str, evidence: str, queries_executed: int, tokens_used: int
    ):
        """Store investigation results in database."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # Escape single quotes for SQL
        root_cause_escaped = root_cause.replace("'", "''")[:2000]
        actions_escaped = actions.replace("'", "''")[:2000]
        evidence_escaped = evidence.replace("'", "''")[:4000]

        sql = f"""
            INSERT INTO alert_investigations (
                investigation_id, alert_id, investigated_at, service_name, alert_type,
                model_used, root_cause_summary, recommended_actions, supporting_evidence,
                queries_executed, tokens_used
            ) VALUES (
                '{investigation_id}', '{alert_id}', TIMESTAMP '{now}', '{service}', '{alert_type}',
                '{self.config.investigation_model}', '{root_cause_escaped}', '{actions_escaped}', '{evidence_escaped}',
                {queries_executed}, {tokens_used}
            )
        """
        self.executor.execute_write(sql)


# =============================================================================
# Main Service
# =============================================================================

class PredictiveAlertsService:
    """Main service that orchestrates all components."""

    def __init__(self, config: Config):
        self.config = config
        self.executor = TrinoExecutor(config)
        self.baseline_computer = BaselineComputer(self.executor, config)
        self.anomaly_detector = AnomalyDetector(self.executor, config, self.baseline_computer)
        self.alert_manager = AlertManager(self.executor, config)
        self.investigator = AlertInvestigator(self.executor, config)

        self.running = True
        self.last_baseline_update = 0

        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print("\n[Service] Shutting down...")
        self.running = False

    def _ensure_tables(self):
        """Ensure required tables exist (creates them if not)."""
        # Check if tables exist by querying
        tables = ["service_baselines", "anomaly_scores", "alerts"]

        for table in tables:
            sql = f"SELECT 1 FROM {table} LIMIT 1"
            try:
                self.executor.execute(sql)
            except Exception as e:
                if "does not exist" in str(e).lower():
                    print(f"[Service] Table {table} does not exist. Please create it using ddl.sql")
                    return False

        return True

    def run(self):
        """Main service loop."""
        print("=" * 60)
        print("Predictive Maintenance Alerts Service")
        print("=" * 60)
        print(f"\nConfiguration:")
        print(f"  Detection interval: {self.config.detection_interval}s")
        print(f"  Baseline interval: {self.config.baseline_interval}s")
        print(f"  Baseline window: {self.config.baseline_window_hours}h")
        print(f"  Z-score threshold: {self.config.zscore_threshold}")
        print(f"  Error rate warning: {self.config.error_rate_warning:.0%}")
        print(f"  Error rate critical: {self.config.error_rate_critical:.0%}")
        print(f"  sklearn available: {SKLEARN_AVAILABLE}")
        print(f"\nRoot cause detection:")
        print(f"  Enabled: {self.config.root_cause_enabled}")
        if self.config.root_cause_enabled:
            if self.config.root_cause_types:
                print(f"  Types: {self.config.root_cause_types}")
            else:
                print(f"  Types: all (auto-discovered)")
            print(f"  Adaptive thresholds: {self.config.adaptive_thresholds_enabled}")
            if self.anomaly_detector.threshold_manager.multipliers:
                print(f"  Threshold multipliers: {self.anomaly_detector.threshold_manager.multipliers}")
        print(f"\nInvestigation settings:")
        print(f"  LLM investigations: {'enabled' if self.investigator.enabled else 'disabled'}")
        if self.investigator.enabled:
            print(f"  Model: {self.config.investigation_model}")
            print(f"  Max per hour: {self.config.max_investigations_per_hour}")
            print(f"  Service cooldown: {self.config.investigation_service_cooldown_minutes}m")
            print(f"  Critical only: {self.config.investigate_critical_only}")
        print()

        # Initial baseline computation
        print("[Service] Computing initial baselines...")
        self.baseline_computer.compute_all_baselines()
        self.last_baseline_update = time.time()

        # Learn adaptive thresholds from alert history
        if self.config.adaptive_thresholds_enabled:
            print("[Service] Learning adaptive thresholds from alert history...")
            self.anomaly_detector.learn_thresholds()

        print(f"\n[Service] Starting detection loop (interval: {self.config.detection_interval}s)...")

        while self.running:
            try:
                loop_start = time.time()

                # Update baselines periodically
                if time.time() - self.last_baseline_update > self.config.baseline_interval:
                    print("[Service] Updating baselines...")
                    self.baseline_computer.compute_all_baselines()
                    self.last_baseline_update = time.time()

                    # Re-learn adaptive thresholds
                    if self.config.adaptive_thresholds_enabled:
                        self.anomaly_detector.learn_thresholds()

                # Run anomaly detection
                anomalies = self.anomaly_detector.detect_all()

                # Process anomalies and manage alerts
                created, updated, new_alerts = self.alert_manager.process_anomalies(
                    anomalies if anomalies else []
                )

                # Investigate new alerts (with rate limiting)
                for alert in new_alerts:
                    self.investigator.investigate(alert)

                # Sleep for remaining interval time
                elapsed = time.time() - loop_start
                sleep_time = max(0, self.config.detection_interval - elapsed)

                if sleep_time > 0:
                    time.sleep(sleep_time)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[Service] Error in detection loop: {e}")
                time.sleep(5)  # Brief pause before retrying

        print("[Service] Stopped")


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    config = Config()

    try:
        config.validate()
    except ValueError as e:
        print(f"[Error] {e}")
        return 1

    service = PredictiveAlertsService(config)
    service.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())
