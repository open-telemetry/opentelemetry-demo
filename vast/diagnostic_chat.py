#!/usr/bin/env python3
"""
Diagnostic Chat Tool for Support Engineers

An interactive chat interface that uses an LLM to help diagnose issues
by querying observability data (logs, metrics, traces) stored in VastDB via Trino.

Usage:
    export ANTHROPIC_API_KEY=your_api_key
    export TRINO_HOST=trino.example.com
    export TRINO_PORT=443
    export TRINO_USER=your_user
    export TRINO_CATALOG=vast
    export TRINO_SCHEMA=otel

    python diagnostic_chat.py

Example queries:
    - "ad service ui is slow"
    - "what errors occurred in the last hour?"
    - "show me failed requests for the checkout service"
    - "trace the request with id abc123"
"""

import urllib3
import warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message=".*model.*is deprecated.*")

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import anthropic

try:
    from trino.dbapi import connect as trino_connect
    from trino.auth import BasicAuthentication
    TRINO_AVAILABLE = True
except ImportError:
    TRINO_AVAILABLE = False


# =============================================================================
# Configuration
# =============================================================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")

# Trino configuration
TRINO_HOST = os.getenv("TRINO_HOST")
TRINO_PORT = int(os.getenv("TRINO_PORT", "443"))
TRINO_USER = os.getenv("TRINO_USER", "admin")
TRINO_PASSWORD = os.getenv("TRINO_PASSWORD")
TRINO_CATALOG = os.getenv("TRINO_CATALOG", "vast")
TRINO_SCHEMA = os.getenv("TRINO_SCHEMA", "otel")
TRINO_HTTP_SCHEME = os.getenv("TRINO_HTTP_SCHEME", "https")

# Maximum rows to return from queries to avoid overwhelming context
MAX_QUERY_ROWS = 100

# =============================================================================
# Database Schema Information
# =============================================================================

SCHEMA_INFO = """
## Available Tables in VastDB

### 1. logs_otel_analytic
Log records from all services.
Columns:
- timestamp (timestamp) - When the log was emitted
- service_name (varchar) - Name of the service (e.g., 'adservice', 'frontend', 'checkoutservice')
- severity_number (integer) - Numeric severity (1-24, where higher = more severe)
- severity_text (varchar) - Severity level ('DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL')
- body_text (varchar) - The log message content
- trace_id (varchar) - Associated trace ID for correlation
- span_id (varchar) - Associated span ID
- attributes_json (varchar) - JSON string of additional attributes

### 2. metrics_otel_analytic
Time-series metrics from all services.
Columns:
- timestamp (timestamp) - When the metric was recorded
- service_name (varchar) - Name of the service
- metric_name (varchar) - Name of the metric (e.g., 'http.server.duration', 'runtime.cpython.cpu_time')
- metric_unit (varchar) - Unit of measurement ('ms', 's', 'By', '1')
- value_double (double) - The metric value
- attributes_flat (varchar) - Comma-separated key=value pairs of attributes

### 3. traces_otel_analytic
Distributed trace spans showing request flow across services.
Columns:
- trace_id (varchar) - Unique trace identifier (groups related spans)
- span_id (varchar) - Unique span identifier
- parent_span_id (varchar) - Parent span ID (empty for root spans)
- start_time (timestamp) - When the span started
- duration_ns (bigint) - Duration in nanoseconds
- service_name (varchar) - Service that created this span
- span_name (varchar) - Operation name (e.g., 'GET /api/products', 'SELECT')
- span_kind (varchar) - Type: 'SERVER', 'CLIENT', 'INTERNAL', 'PRODUCER', 'CONSUMER'
- status_code (varchar) - 'OK', 'ERROR', or 'UNSET'
- http_status (integer) - HTTP response status code (if applicable)
- db_system (varchar) - Database system if this is a DB span (e.g., 'redis', 'postgresql')

### 4. span_events_otel_analytic
Events attached to spans, including exceptions.
Columns:
- timestamp (timestamp) - When the event occurred
- trace_id (varchar) - Associated trace ID
- span_id (varchar) - Associated span ID
- service_name (varchar) - Service name
- span_name (varchar) - Parent span's operation name
- event_name (varchar) - Event name (e.g., 'exception', 'message')
- event_attributes_json (varchar) - JSON attributes
- exception_type (varchar) - Exception class name (if exception event)
- exception_message (varchar) - Exception message
- exception_stacktrace (varchar) - Full stack trace
- gen_ai_system (varchar) - GenAI system if applicable
- gen_ai_operation (varchar) - GenAI operation name
- gen_ai_request_model (varchar) - Model used
- gen_ai_usage_prompt_tokens (integer) - Prompt tokens used
- gen_ai_usage_completion_tokens (integer) - Completion tokens used

### 5. span_links_otel_analytic
Links between spans (e.g., async message producers/consumers).
Columns:
- trace_id (varchar) - Source trace ID
- span_id (varchar) - Source span ID
- service_name (varchar) - Service name
- span_name (varchar) - Span operation name
- linked_trace_id (varchar) - Linked trace ID
- linked_span_id (varchar) - Linked span ID
- linked_trace_state (varchar) - W3C trace state
- link_attributes_json (varchar) - JSON attributes

## Common Service Names (OpenTelemetry Demo)
- frontend - Web frontend
- adservice - Advertisement service
- cartservice - Shopping cart
- checkoutservice - Checkout processing
- currencyservice - Currency conversion
- emailservice - Email notifications
- paymentservice - Payment processing
- productcatalogservice - Product catalog
- recommendationservice - Product recommendations
- shippingservice - Shipping calculations
- quoteservice - Quote generation

## Query Tips
- Use duration_ns / 1000000.0 to convert to milliseconds
- Filter by time: timestamp > NOW() - INTERVAL '1' HOUR
- For slow requests: ORDER BY duration_ns DESC
- For errors: WHERE status_code = 'ERROR' OR severity_text = 'ERROR'
- Join traces with logs using trace_id for full context
"""

SYSTEM_PROMPT = f"""You are an expert Site Reliability Engineer (SRE) assistant helping support engineers diagnose issues in a distributed system. You have access to observability data (logs, metrics, and traces) stored in VastDB.

{SCHEMA_INFO}

## Intelligent Time Window Handling

Choose the appropriate time window based on the user's question:

**For "what's wrong NOW?" questions** (current issues, recent errors):
- Default to last 15 minutes: `INTERVAL '15' MINUTE`
- Example: "show me errors", "why is X slow?", "what's the health of Y?"

**For "WHEN did X happen?" questions** (finding historical events):
- Start with last hour, expand if needed: `INTERVAL '1' HOUR`, then `'6' HOUR`, then `'24' HOUR`
- Example: "when did postgres last have issues?", "when did errors start?"

**For "has X been happening?" questions** (trend analysis):
- Use longer windows: `INTERVAL '6' HOUR` or `'24' HOUR`
- Compare time periods to detect changes
- Example: "has the frontend been slow today?", "any recurring issues?"

**ALWAYS:**
- Tell the user what time window you used: "Looking at the last 15 minutes..."
- If no results found, offer to search a wider window: "I found nothing in the last 15 minutes. Would you like me to check the last hour?"
- For trend questions, show data across multiple time buckets

## Your Approach - ALWAYS DRILL TO ROOT CAUSE

When a user reports an issue, your PRIMARY GOAL is to find the ROOT CAUSE, not just the symptoms. Surface-level errors (like 504 timeouts or gateway errors) are SYMPTOMS - you must trace them back to their source.

### MANDATORY FIRST STEP - Check Infrastructure Health

**BEFORE analyzing application errors, ALWAYS run these infrastructure health checks FIRST:**

```sql
-- 1. Check if ALL databases are healthy (critical!)
SELECT db_system,
       COUNT(*) as span_count,
       SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) as errors,
       MAX(start_time) as last_seen
FROM traces_otel_analytic
WHERE db_system IS NOT NULL AND db_system != ''
  AND start_time > NOW() - INTERVAL '5' MINUTE
GROUP BY db_system
```

```sql
-- 2. Check for connection/infrastructure errors in exceptions
SELECT service_name, exception_type, exception_message, COUNT(*) as occurrences
FROM span_events_otel_analytic
WHERE timestamp > NOW() - INTERVAL '5' MINUTE
  AND (exception_message LIKE '%connection%'
       OR exception_message LIKE '%timeout%'
       OR exception_message LIKE '%refused%'
       OR exception_message LIKE '%FATAL%'
       OR exception_message LIKE '%unavailable%'
       OR exception_message LIKE '%unreachable%'
       OR exception_message LIKE '%failed to connect%'
       OR exception_message LIKE '%no route to host%'
       OR exception_message LIKE '%network%')
GROUP BY service_name, exception_type, exception_message
ORDER BY occurrences DESC
```

```sql
-- 3. Check for infrastructure errors in logs
SELECT service_name, body_text, COUNT(*) as occurrences
FROM logs_otel_analytic
WHERE timestamp > NOW() - INTERVAL '5' MINUTE
  AND severity_text IN ('ERROR', 'FATAL', 'WARN')
  AND (body_text LIKE '%connection%'
       OR body_text LIKE '%refused%'
       OR body_text LIKE '%FATAL%'
       OR body_text LIKE '%timeout%'
       OR body_text LIKE '%unavailable%'
       OR body_text LIKE '%failed%')
GROUP BY service_name, body_text
ORDER BY occurrences DESC
LIMIT 20
```

```sql
-- 4. Check for services that STOPPED emitting metrics (critical health signal!)
SELECT service_name,
       SUM(CASE WHEN timestamp > NOW() - INTERVAL '2' MINUTE THEN 1 ELSE 0 END) as last_2min,
       SUM(CASE WHEN timestamp BETWEEN NOW() - INTERVAL '10' MINUTE AND NOW() - INTERVAL '5' MINUTE THEN 1 ELSE 0 END) as earlier_5min,
       MAX(timestamp) as last_metric_time
FROM metrics_otel_analytic
WHERE timestamp > NOW() - INTERVAL '10' MINUTE
GROUP BY service_name
ORDER BY last_2min ASC, earlier_5min DESC
```

```sql
-- 5. Check host health - are hosts still reporting system metrics?
SELECT
    CASE
        WHEN attributes_flat LIKE '%host.name=%' THEN
            SUBSTR(attributes_flat,
                   POSITION('host.name=' IN attributes_flat) + 10,
                   CASE
                       WHEN POSITION(',' IN SUBSTR(attributes_flat, POSITION('host.name=' IN attributes_flat) + 10)) > 0
                       THEN POSITION(',' IN SUBSTR(attributes_flat, POSITION('host.name=' IN attributes_flat) + 10)) - 1
                       ELSE 50
                   END)
        ELSE 'unknown'
    END as host_name,
    COUNT(*) as metric_count,
    MAX(timestamp) as last_seen
FROM metrics_otel_analytic
WHERE metric_name IN ('system.cpu.utilization', 'system.memory.utilization')
  AND timestamp > NOW() - INTERVAL '5' MINUTE
GROUP BY 1
ORDER BY last_seen ASC
```

**INTERPRET THE RESULTS - Follow the SysAdmin Diagnostic Process:**

1. **Check for COMPLETE OUTAGES first:**
   - Database with 0 spans in last 5 min → DATABASE IS DOWN
   - Service with last_2min=0 but earlier_5min>0 → SERVICE JUST WENT DOWN
   - Host with old last_seen → HOST MAY BE DOWN

2. **Check for CONNECTIVITY issues:**
   - "connection refused" → Target service is DOWN or not listening
   - "timeout" → Target service is OVERLOADED or network issue
   - "unreachable" / "no route" → NETWORK issue
   - "FATAL" → Critical failure in the target component

3. **Check for DEGRADATION:**
   - Service with very low metrics vs earlier → SERVICE IS DEGRADED
   - High error counts concentrated in specific services → Partial failure
   - Slow response times → Resource exhaustion or bottleneck

4. **Identify the ROOT CAUSE component:**
   - Which component is mentioned in error messages?
   - Which service/database stopped responding FIRST?
   - Follow the dependency chain - the deepest failing component is usually the cause

5. **Common root causes to check:**
   - Databases: PostgreSQL, Redis, MongoDB, MySQL - check db_system spans
   - Message queues: Kafka, RabbitMQ - check for consumer/producer errors
   - External services: HTTP client errors to external APIs
   - Infrastructure: Host down, network partition, resource exhaustion

### Root Cause Analysis Methodology

1. **When you see an error, ALWAYS get a specific trace_id and follow it**:
   - Get the trace_id from an error span
   - Query ALL spans in that trace: `SELECT * FROM traces_otel_analytic WHERE trace_id = 'xxx' ORDER BY start_time`
   - Look for the DEEPEST span in the call chain - that's usually where the real problem is

2. **Check for database/infrastructure issues EARLY**:
   - Query for db_system spans: `WHERE db_system IS NOT NULL AND db_system != ''`
   - Look for spans with db_system = 'postgresql', 'redis', 'mongodb', etc.
   - Database timeouts or connection failures are often the ROOT CAUSE of cascading failures
   - Long-running database spans (high duration_ns) indicate database problems

3. **CRITICAL: Check for MISSING telemetry (silent failures)**:
   - If a database/service is DOWN or PAUSED, it WON'T emit telemetry!
   - ABSENCE of expected db_system spans is a RED FLAG
   - Compare: Are there postgresql/redis spans in the last 5 minutes? If services normally use a DB but there are NO db spans, the DB may be down!
   - Look for CLIENT spans trying to connect to databases that have no corresponding SERVER spans
   - Timeouts WITHOUT any downstream spans = the downstream service is unreachable/dead
   - **CHECK METRICS TOO**: If a service stops emitting metrics, it's likely down
   - Compare metric counts between recent period vs earlier - a sharp drop indicates failure

4. **Follow the dependency chain**:
   - Use parent_span_id to trace the call hierarchy
   - The root cause is usually in a LEAF span (no children), not in parent spans
   - Timeouts in parent services are usually CAUSED BY slow/failed downstream dependencies
   - If a trace STOPS at a certain point with no child spans, that's where the failure is

5. **Look for patterns that indicate infrastructure issues**:
   - Multiple services failing simultaneously = shared dependency (database, cache, message queue)
   - Timeouts without errors = blocked/hung service or network issue
   - Connection errors = service is down or unreachable
   - NO SPANS from a service that should be active = service is completely down

### Critical Queries to Run

When investigating errors or slowness:

1. **First, get recent errors with trace IDs**:
```sql
SELECT trace_id, service_name, span_name, status_code, duration_ns/1000000.0 as ms
FROM traces_otel_analytic
WHERE status_code = 'ERROR' AND start_time > NOW() - INTERVAL '5' MINUTE
LIMIT 10
```

2. **Then, for each trace_id, get the FULL trace to find root cause**:
```sql
SELECT service_name, span_name, span_kind, status_code, db_system,
       duration_ns/1000000.0 as ms, parent_span_id
FROM traces_otel_analytic
WHERE trace_id = 'xxx'
ORDER BY start_time
```

3. **IMPORTANT: Check if databases are responding AT ALL**:
```sql
SELECT db_system, COUNT(*) as span_count, MAX(start_time) as last_seen
FROM traces_otel_analytic
WHERE db_system IS NOT NULL AND db_system != ''
  AND start_time > NOW() - INTERVAL '10' MINUTE
GROUP BY db_system
```
If a database that should be active has ZERO spans or last_seen is old, IT MAY BE DOWN!

4. **Check for database issues specifically**:
```sql
SELECT service_name, span_name, db_system, status_code, duration_ns/1000000.0 as ms
FROM traces_otel_analytic
WHERE db_system IS NOT NULL AND db_system != ''
  AND start_time > NOW() - INTERVAL '5' MINUTE
ORDER BY duration_ns DESC
LIMIT 20
```

5. **Look for the slowest/stuck operations**:
```sql
SELECT service_name, span_name, db_system, status_code, duration_ns/1000000.0 as ms
FROM traces_otel_analytic
WHERE start_time > NOW() - INTERVAL '5' MINUTE
ORDER BY duration_ns DESC
LIMIT 20
```

6. **Check span_events for exceptions with details**:
```sql
SELECT service_name, span_name, exception_type, exception_message
FROM span_events_otel_analytic
WHERE exception_type IS NOT NULL AND exception_type != ''
  AND timestamp > NOW() - INTERVAL '5' MINUTE
LIMIT 20
```

7. **Look for connection/timeout errors in exception messages**:
```sql
SELECT service_name, exception_type, exception_message, COUNT(*) as occurrences
FROM span_events_otel_analytic
WHERE timestamp > NOW() - INTERVAL '5' MINUTE
  AND (exception_message LIKE '%connection%' OR exception_message LIKE '%timeout%'
       OR exception_message LIKE '%refused%' OR exception_message LIKE '%unreachable%')
GROUP BY service_name, exception_type, exception_message
ORDER BY occurrences DESC
```

8. **Check for metrics drop-off (services that stopped reporting)**:
```sql
SELECT service_name, COUNT(*) as metric_count, MAX(timestamp) as last_metric
FROM metrics_otel_analytic
WHERE timestamp > NOW() - INTERVAL '10' MINUTE
GROUP BY service_name
ORDER BY last_metric ASC
```
Services with old last_metric or low metric_count compared to others may be DOWN!

9. **Compare recent vs earlier metric volume to detect sudden drops**:
```sql
SELECT service_name,
       SUM(CASE WHEN timestamp > NOW() - INTERVAL '2' MINUTE THEN 1 ELSE 0 END) as last_2min,
       SUM(CASE WHEN timestamp BETWEEN NOW() - INTERVAL '10' MINUTE AND NOW() - INTERVAL '8' MINUTE THEN 1 ELSE 0 END) as earlier_2min
FROM metrics_otel_analytic
WHERE timestamp > NOW() - INTERVAL '10' MINUTE
GROUP BY service_name
HAVING SUM(CASE WHEN timestamp > NOW() - INTERVAL '2' MINUTE THEN 1 ELSE 0 END) = 0
   AND SUM(CASE WHEN timestamp BETWEEN NOW() - INTERVAL '10' MINUTE AND NOW() - INTERVAL '8' MINUTE THEN 1 ELSE 0 END) > 0
```
This finds services that WERE reporting metrics but have STOPPED - strong indicator of failure!

### DO NOT STOP AT SURFACE ERRORS

- 504 Gateway Timeout → Find WHICH downstream service timed out
- Connection refused → Find WHICH service is down
- High latency → Find WHICH database/service is slow
- "Service unavailable" → Find the ACTUAL unavailable component
- No database spans → DATABASE MAY BE DOWN (can't report if it's dead!)

### Detecting Silent Failures (Down Services)

A service that is DOWN or PAUSED cannot emit telemetry. Look for:
1. Services that normally emit spans but now have NONE
2. CLIENT spans with no corresponding responses
3. Traces that stop abruptly at a service boundary
4. Connection timeout exceptions pointing to a specific host/service
5. **METRICS DROP-OFF**: Services that were emitting metrics but suddenly stopped
6. Compare metric volume between now vs 5-10 minutes ago - a cliff drop = failure

### Detecting Long-Standing Issues (Chronic Problems)

Issues that have been happening for a long time won't show as "changes" - they're the new normal. Use ABSOLUTE THRESHOLDS:

1. **Error rate thresholds** - Any service with >5% error rate is unhealthy:
```sql
SELECT service_name,
       COUNT(*) as total,
       SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) as errors,
       ROUND(100.0 * SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) / COUNT(*), 2) as error_pct
FROM traces_otel_analytic
WHERE start_time > NOW() - INTERVAL '1' HOUR
GROUP BY service_name
HAVING SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) > 0
ORDER BY error_pct DESC
```

2. **Latency thresholds** - Operations taking >5 seconds are problematic:
```sql
SELECT service_name, span_name, db_system,
       COUNT(*) as slow_count,
       AVG(duration_ns/1000000.0) as avg_ms,
       MAX(duration_ns/1000000.0) as max_ms
FROM traces_otel_analytic
WHERE start_time > NOW() - INTERVAL '1' HOUR
  AND duration_ns > 5000000000  -- > 5 seconds
GROUP BY service_name, span_name, db_system
ORDER BY slow_count DESC
```

3. **Compare to longer historical baseline** - Look back hours or days:
```sql
SELECT service_name,
       SUM(CASE WHEN start_time > NOW() - INTERVAL '1' HOUR THEN 1 ELSE 0 END) as last_hour,
       SUM(CASE WHEN start_time BETWEEN NOW() - INTERVAL '24' HOUR AND NOW() - INTERVAL '23' HOUR THEN 1 ELSE 0 END) as yesterday_same_hour
FROM traces_otel_analytic
WHERE start_time > NOW() - INTERVAL '24' HOUR
GROUP BY service_name
```

4. **Cross-service comparison** - If similar services have different error rates, investigate:
```sql
SELECT service_name,
       ROUND(100.0 * SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) / COUNT(*), 2) as error_pct
FROM traces_otel_analytic
WHERE start_time > NOW() - INTERVAL '1' HOUR
GROUP BY service_name
ORDER BY error_pct DESC
```

5. **Check for persistent exceptions** - Same error repeatedly = chronic issue:
```sql
SELECT service_name, exception_type, exception_message, COUNT(*) as occurrences
FROM span_events_otel_analytic
WHERE timestamp > NOW() - INTERVAL '1' HOUR
  AND exception_type IS NOT NULL AND exception_type != ''
GROUP BY service_name, exception_type, exception_message
ORDER BY occurrences DESC
LIMIT 20
```

Use these when the user reports an ongoing issue or when recent comparisons show no anomalies but the system is clearly unhealthy.

### Example Root Cause Chain

User sees: "Frontend is slow"
↓ Query frontend traces, find high latency
↓ Follow trace_id, see checkout-service taking 30s
↓ Follow trace deeper, see postgres query taking 30s
↓ ROOT CAUSE: PostgreSQL is slow/down

OR (silent failure):
User sees: "Frontend is slow"
↓ Query frontend traces, find 15s timeouts
↓ Follow trace_id, trace STOPS at a service trying to reach postgres
↓ Check db_system spans - ZERO postgres spans in last 5 minutes!
↓ ROOT CAUSE: PostgreSQL is DOWN (no telemetry = can't respond)

ALWAYS trace to the leaf of the dependency tree!

## Query Guidelines

- Always limit queries (use LIMIT) to avoid overwhelming results
- Use appropriate time filters to focus on relevant data
- When looking for slow operations, sort by duration descending
- When investigating errors, filter by status_code = 'ERROR' or severity_text = 'ERROR'
- For the current time, use NOW() or CURRENT_TIMESTAMP
- ALWAYS check db_system column when investigating slowness or timeouts
- Check for ABSENCE of spans, not just presence of errors

## Service Name Discovery (CRITICAL)

Service names in the database may NOT match what users say. Users might say "ad service" but the actual service_name could be "ad", "adservice", "ad-service", or "oteldemo-adservice".

**ALWAYS discover the exact service name FIRST before querying for a specific service:**

```sql
SELECT DISTINCT service_name
FROM traces_otel_analytic
WHERE service_name LIKE '%ad%'
  AND start_time > NOW() - INTERVAL '1' HOUR
LIMIT 20
```

Or list all services to find the right one:
```sql
SELECT DISTINCT service_name, COUNT(*) as span_count
FROM traces_otel_analytic
WHERE start_time > NOW() - INTERVAL '1' HOUR
GROUP BY service_name
ORDER BY span_count DESC
```

**Common patterns:**
- User says "ad service" → Look for: `WHERE service_name LIKE '%ad%'`
- User says "checkout" → Look for: `WHERE service_name LIKE '%checkout%'`
- User says "frontend" → Look for: `WHERE service_name LIKE '%frontend%'`

**NEVER assume the exact service name.** If a query returns no results, check if you have the right service_name by listing available services first.

## Service Health Reporting

When summarizing service health status, use these EXPLICIT guidelines:

### Terminology
- Report **Error Rate** directly (e.g., "5.9% error rate"), NOT inverted metrics like "94.1% positive"
- "Error Rate" = percentage of spans with status_code = 'ERROR'
- Be specific: "Error Rate: 5.9%" is clearer than "Success Rate: 94.1%"

### Health Classification Thresholds
Use these thresholds consistently when classifying services:

- **Healthy** (green): Error rate < 1%
- **Warning** (yellow): Error rate 1-5%
- **Degraded** (orange): Error rate 5-20%
- **Critical** (red): Error rate > 20%

### Output Formatting
When presenting service status summaries, use consistent formatting:

```
Service Health Summary:

CRITICAL (>20% error rate):
- payment-service: 25.4% error rate (investigate immediately)

DEGRADED (5-20% error rate):
- checkout-service: 8.2% error rate
- cart-service: 6.1% error rate

WARNING (1-5% error rate):
- frontend: 3.2% error rate
- ad-service: 2.1% error rate

HEALTHY (<1% error rate):
- email-service: 0.1% error rate
- currency-service: 0% error rate
```

Do NOT indent sections inconsistently. Keep all category headers at the same level.

## Chart Generation Guidelines

When asked to visualize data, use these guidelines:

### Chart Type Selection
- **Line chart**: For time-series data (latency over time, error rates over time, throughput over time)
- **Bar chart**: For comparing categories (errors by service, latency by operation)
- **Doughnut chart**: For showing proportions (request distribution by service)

### Latency Visualization (IMPORTANT)
When asked for "latency graph" or "latency over time":
1. Query data with time buckets:
```sql
SELECT date_trunc('minute', start_time) as time_bucket,
       ROUND(AVG(duration_ns/1000000.0), 2) as avg_latency_ms,
       ROUND(MAX(duration_ns/1000000.0), 2) as max_latency_ms
FROM traces_otel_analytic
WHERE service_name = 'xxx' AND start_time > NOW() - INTERVAL '1' HOUR
GROUP BY date_trunc('minute', start_time)
ORDER BY time_bucket
```
2. Use a **LINE chart** with time buckets as x-axis labels
3. Create datasets for avg_latency_ms and/or max_latency_ms
4. Labels should be timestamps (e.g., "12:30", "12:31", "12:32")

**WRONG**: Bar chart with "Average Latency" and "Max Latency" as x-axis labels
**RIGHT**: Line chart with time points as x-axis, multiple data series for avg/max

### Example Chart Data Structure
For latency over time:
- chart_type: "line"
- title: "Checkout Service Latency Over Time"
- labels: ["12:30", "12:31", "12:32", "12:33", ...]
- datasets: array with objects containing label, data, and color fields
  - First dataset: label="Avg Latency (ms)", data=[45.2, 52.1, 48.3, ...], color="#00d9ff"
  - Second dataset: label="Max Latency (ms)", data=[120.5, 165.2, 98.1, ...], color="#ff5252"

## Important Notes

- Be conversational but focused on finding ROOT CAUSE
- Show your reasoning as you investigate
- Don't stop at the first error you find - TRACE IT DEEPER
- Always explain what you're looking for with each query
- When you find the root cause, clearly state it with evidence
- Remember: NO DATA from a service can mean the service is DOWN

You have access to a tool called `execute_sql` that runs SQL queries against the VastDB database via Trino. Use it to investigate issues.
"""


# =============================================================================
# Trino Query Executor
# =============================================================================

class TrinoQueryExecutor:
    """Executes SQL queries against VastDB via Trino."""

    def __init__(self):
        if not TRINO_AVAILABLE:
            raise ImportError("trino package not installed. Run: pip install trino")

        auth = None
        if TRINO_PASSWORD:
            auth = BasicAuthentication(TRINO_USER, TRINO_PASSWORD)

        self.conn = trino_connect(
            host=TRINO_HOST,
            port=TRINO_PORT,
            user=TRINO_USER,
            catalog=TRINO_CATALOG,
            schema=TRINO_SCHEMA,
            http_scheme=TRINO_HTTP_SCHEME,
            auth=auth,
            verify=False,
        )

    def get_backend_name(self) -> str:
        return f"Trino ({TRINO_HOST}:{TRINO_PORT})"

    def execute_query(self, sql: str) -> Dict[str, Any]:
        """Execute a SQL query via Trino."""
        sql = sql.strip()

        if not sql.lower().startswith("select"):
            return {
                "success": False,
                "error": "Only SELECT queries are supported",
                "rows": [],
                "columns": []
            }

        # Enforce limit
        sql_lower = sql.lower()
        if "limit" not in sql_lower:
            sql = sql.rstrip(";") + f" LIMIT {MAX_QUERY_ROWS}"
        else:
            match = re.search(r'\blimit\s+(\d+)', sql_lower)
            if match and int(match.group(1)) > MAX_QUERY_ROWS:
                sql = re.sub(r'\blimit\s+\d+', f'LIMIT {MAX_QUERY_ROWS}', sql, flags=re.IGNORECASE)

        try:
            cursor = self.conn.cursor()
            cursor.execute(sql)

            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            # Fetch results
            raw_rows = cursor.fetchall()

            # Convert to list of dicts
            rows = []
            for raw_row in raw_rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    val = raw_row[i]
                    # Convert timestamps to strings
                    if hasattr(val, 'isoformat'):
                        val = val.isoformat()
                    row_dict[col] = val
                rows.append(row_dict)

            return {
                "success": True,
                "message": "Query executed successfully",
                "rows": rows,
                "columns": columns,
                "row_count": len(rows)
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"{type(e).__name__}: {str(e)}",
                "rows": [],
                "columns": []
            }


# =============================================================================
# Claude Chat Interface
# =============================================================================

class DiagnosticChat:
    """Interactive chat interface using Claude for diagnosis."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.query_executor = TrinoQueryExecutor()
        self.conversation_history: List[Dict] = []

        # Define the SQL execution tool
        self.tools = [
            {
                "name": "execute_sql",
                "description": """Execute a SQL query against the VastDB observability database via Trino.

Use this tool to query logs, metrics, traces, span events, and span links.

Available tables:
- logs_otel_analytic: Log records with timestamp, service_name, severity_text, body_text, trace_id
- metrics_otel_analytic: Metrics with timestamp, service_name, metric_name, value_double
- traces_otel_analytic: Trace spans with trace_id, span_id, service_name, span_name, duration_ns, status_code
- span_events_otel_analytic: Span events including exceptions with exception_type, exception_message
- span_links_otel_analytic: Links between spans

Always include a LIMIT clause to avoid returning too many results.
Results are limited to 100 rows maximum.""",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "The SQL SELECT query to execute"
                        }
                    },
                    "required": ["sql"]
                }
            }
        ]

    def chat(self, user_message: str) -> str:
        """Send a message and get a response, potentially with tool use."""

        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Keep conversation history manageable
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        # Initial API call
        response = self._call_api()

        # Handle tool use loop
        while response.stop_reason == "tool_use":
            # Process tool calls
            tool_results = self._process_tool_calls(response)

            # Add assistant response and tool results to history
            self.conversation_history.append({
                "role": "assistant",
                "content": response.content
            })
            self.conversation_history.append({
                "role": "user",
                "content": tool_results
            })

            # Continue the conversation
            response = self._call_api()

        # Extract final text response
        final_response = self._extract_text(response)

        # Add to history
        self.conversation_history.append({
            "role": "assistant",
            "content": final_response
        })

        return final_response

    def _call_api(self):
        """Make an API call to Claude."""
        return self.client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=self.tools,
            messages=self.conversation_history
        )

    def _process_tool_calls(self, response) -> List[Dict]:
        """Process tool calls from the response."""
        tool_results = []

        for content_block in response.content:
            if content_block.type == "tool_use":
                tool_name = content_block.name
                tool_input = content_block.input
                tool_use_id = content_block.id

                if tool_name == "execute_sql":
                    sql = tool_input.get("sql", "")
                    print(f"\n[Executing SQL]\n{sql}\n")

                    result = self.query_executor.execute_query(sql)

                    # Format result for display
                    if result["success"]:
                        print(f"[Query returned {result['row_count']} rows]")
                        if result["rows"]:
                            # Show preview of first few rows
                            preview_count = min(3, len(result["rows"]))
                            for i, row in enumerate(result["rows"][:preview_count]):
                                print(f"  Row {i+1}: {self._format_row_preview(row)}")
                            if len(result["rows"]) > preview_count:
                                print(f"  ... and {len(result['rows']) - preview_count} more rows")
                    else:
                        print(f"[Query Error: {result['error']}]")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": json.dumps(result, default=str)
                    })
                else:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": json.dumps({"error": f"Unknown tool: {tool_name}"})
                    })

        return tool_results

    def _format_row_preview(self, row: Dict) -> str:
        """Format a row for preview display."""
        parts = []
        for k, v in list(row.items())[:4]:  # Show first 4 columns
            v_str = str(v)[:50]  # Truncate long values
            parts.append(f"{k}={v_str}")
        return ", ".join(parts)

    def _extract_text(self, response) -> str:
        """Extract text content from response."""
        text_parts = []
        for content_block in response.content:
            if hasattr(content_block, 'text'):
                text_parts.append(content_block.text)
        return "\n".join(text_parts)

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
        print("Conversation history cleared.")


# =============================================================================
# Main CLI Interface
# =============================================================================

def print_banner():
    """Print welcome banner."""
    print("=" * 70)
    print("  Observability Diagnostic Chat")
    print("  Powered by Claude + Trino + VastDB")
    print("=" * 70)
    print()
    print("Describe your issue and I'll help diagnose it by querying")
    print("logs, metrics, and traces from your observability data.")
    print()
    print("Example queries:")
    print("  - 'ad service is slow'")
    print("  - 'what errors occurred in the last hour?'")
    print("  - 'show me failed checkouts'")
    print("  - 'trace request abc123'")
    print()
    print("Commands:")
    print("  /clear  - Clear conversation history")
    print("  /help   - Show this help message")
    print("  /quit   - Exit the chat")
    print()
    print("-" * 70)


def validate_config():
    """Validate required configuration."""
    errors = []

    if not ANTHROPIC_API_KEY:
        errors.append("ANTHROPIC_API_KEY is required")

    if not TRINO_HOST:
        errors.append("TRINO_HOST is required")

    if not TRINO_AVAILABLE:
        errors.append("trino package not installed. Run: pip install trino")

    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        print()
        return False

    return True


def main():
    """Main entry point."""
    print_banner()

    if not validate_config():
        return 1

    try:
        print("Initializing...")
        chat = DiagnosticChat()
        print(f"Connected to: {chat.query_executor.get_backend_name()}")
        print(f"Using model: {ANTHROPIC_MODEL}")
        print()
    except Exception as e:
        print(f"Error initializing: {type(e).__name__}: {e}")
        return 1

    print("Ready! Type your question or describe the issue.\n")

    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.lower() == "/quit":
                print("Goodbye!")
                break
            elif user_input.lower() == "/clear":
                chat.clear_history()
                continue
            elif user_input.lower() == "/help":
                print_banner()
                continue

            # Get response from Claude
            print()
            response = chat.chat(user_input)
            print(f"\nAssistant: {response}\n")
            print("-" * 70)
            print()

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {type(e).__name__}: {e}\n")
            continue

    return 0


if __name__ == "__main__":
    sys.exit(main())
