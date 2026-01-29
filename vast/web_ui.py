#!/usr/bin/env python3
"""
Web UI for Observability Diagnostic Chat

A web-based interface for support engineers to diagnose issues
and monitor system status.

Usage:
    export ANTHROPIC_API_KEY=your_api_key
    export TRINO_HOST=trino.example.com
    python web_ui.py

Then open http://localhost:5000 in your browser.
"""

import urllib3
import warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message=".*model.*is deprecated.*")

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List

from flask import Flask, render_template, request, jsonify, Response
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

# Investigation config (mirrors predictive_alerts.py settings)
INVESTIGATE_CRITICAL_ONLY = os.getenv("INVESTIGATE_CRITICAL_ONLY", "false").lower() == "true"

TRINO_HOST = os.getenv("TRINO_HOST")
TRINO_PORT = int(os.getenv("TRINO_PORT", "443"))
TRINO_USER = os.getenv("TRINO_USER", "admin")
TRINO_PASSWORD = os.getenv("TRINO_PASSWORD")
TRINO_CATALOG = os.getenv("TRINO_CATALOG", "vast")
TRINO_SCHEMA = os.getenv("TRINO_SCHEMA", "otel")
TRINO_HTTP_SCHEME = os.getenv("TRINO_HTTP_SCHEME", "https")

MAX_QUERY_ROWS = 100

app = Flask(__name__)

# Import the system prompt from diagnostic_chat
from diagnostic_chat import SYSTEM_PROMPT

# =============================================================================
# Trino Query Executor
# =============================================================================

class TrinoQueryExecutor:
    """Executes SQL queries against VastDB via Trino."""

    def __init__(self):
        if not TRINO_AVAILABLE:
            raise ImportError("trino package not installed")

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

    def execute_query(self, sql: str) -> Dict[str, Any]:
        """Execute a SQL query via Trino."""
        sql = sql.strip()

        if not sql.lower().startswith("select"):
            return {"success": False, "error": "Only SELECT queries are supported", "rows": [], "columns": []}

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
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            raw_rows = cursor.fetchall()

            rows = []
            for raw_row in raw_rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    val = raw_row[i]
                    if hasattr(val, 'isoformat'):
                        val = val.isoformat()
                    row_dict[col] = val
                rows.append(row_dict)

            return {"success": True, "rows": rows, "columns": columns, "row_count": len(rows)}

        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {str(e)}", "rows": [], "columns": []}


# Global instances
query_executor = None
anthropic_client = None

def get_query_executor():
    global query_executor
    if query_executor is None:
        query_executor = TrinoQueryExecutor()
    return query_executor

def get_anthropic_client():
    global anthropic_client
    if anthropic_client is None:
        anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return anthropic_client


# =============================================================================
# Chat Session Management
# =============================================================================

chat_sessions = {}

def get_or_create_session(session_id: str) -> List[Dict]:
    if session_id not in chat_sessions:
        chat_sessions[session_id] = []
    return chat_sessions[session_id]


# =============================================================================
# Routes
# =============================================================================

@app.route('/')
def index():
    return render_template('index.html')


def get_chat_tools():
    """Return the tools definition for the chat endpoint."""
    return [{
        "name": "execute_sql",
        "description": "Execute a SQL query against the observability database",
        "input_schema": {
            "type": "object",
            "properties": {"sql": {"type": "string", "description": "The SQL SELECT query"}},
            "required": ["sql"]
        }
    }, {
        "name": "generate_chart",
        "description": """Generate a chart/graph to visualize data. Use this when the user asks for visualizations, trends, or graphs.

CRITICAL - Choose the correct chart type:
- **line**: ONLY for TIME SERIES data where X-axis is timestamps/time buckets (e.g., "latency over time", "errors per hour")
- **bar**: For CATEGORICAL comparisons where X-axis is categories like services, endpoints, operations (e.g., "latency by endpoint", "errors by service")
- **doughnut**: For showing proportions/percentages of a whole (e.g., "request distribution")

WRONG: Using line chart for "latency by endpoint" (endpoints are categories, not time)
RIGHT: Using bar chart for "latency by endpoint"
RIGHT: Using line chart for "latency over the last hour" (time series)

IMPORTANT: Always provide data sorted appropriately - by time for line charts, by value (desc) for bar charts.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": ["line", "bar", "doughnut"],
                    "description": "Type of chart: 'line' for time series, 'bar' for categorical comparisons, 'doughnut' for proportions"
                },
                "title": {
                    "type": "string",
                    "description": "Chart title"
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "X-axis labels (categories or time points)"
                },
                "datasets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "Dataset name (shown in legend)"},
                            "data": {"type": "array", "items": {"type": "number"}, "description": "Data values"},
                            "color": {"type": "string", "description": "Color (optional, e.g., '#00d9ff' or 'red')"}
                        },
                        "required": ["label", "data"]
                    },
                    "description": "One or more data series to plot"
                }
            },
            "required": ["chart_type", "title", "labels", "datasets"]
        }
    }, {
        "name": "generate_topology",
        "description": """Generate a service topology/dependency graph visualization. Use this when the user asks about:
- Service dependencies or topology
- What depends on a service/database
- What a service/database depends on
- Architecture or call flow visualization

The topology will be rendered as an interactive network graph. Nodes represent services or databases, edges represent call relationships.

To find dependencies, query traces_otel_analytic:
- For service-to-service calls: Look at parent_span_id relationships where services differ
- For database dependencies: Look at db_system field to find which services call which databases

Example query to find service dependencies:
SELECT DISTINCT
    parent.service_name as caller,
    child.service_name as callee
FROM traces_otel_analytic child
JOIN traces_otel_analytic parent ON child.parent_span_id = parent.span_id AND child.trace_id = parent.trace_id
WHERE child.service_name != parent.service_name
  AND child.start_time > NOW() - INTERVAL '10' MINUTE

Example query to find database dependencies:
SELECT DISTINCT service_name, db_system
FROM traces_otel_analytic
WHERE db_system IS NOT NULL AND db_system != ''
  AND start_time > NOW() - INTERVAL '10' MINUTE""",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Title for the topology graph"
                },
                "nodes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Unique node identifier"},
                            "label": {"type": "string", "description": "Display label for the node"},
                            "type": {"type": "string", "enum": ["service", "database", "external"], "description": "Node type for styling"},
                            "status": {"type": "string", "enum": ["healthy", "warning", "error"], "description": "Health status (optional)"}
                        },
                        "required": ["id", "label", "type"]
                    },
                    "description": "List of nodes (services, databases, external systems)"
                },
                "edges": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "from": {"type": "string", "description": "Source node ID"},
                            "to": {"type": "string", "description": "Target node ID"},
                            "label": {"type": "string", "description": "Edge label (optional, e.g., call count)"}
                        },
                        "required": ["from", "to"]
                    },
                    "description": "List of edges (call relationships between nodes)"
                }
            },
            "required": ["title", "nodes", "edges"]
        }
    }]


@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    """Handle chat messages with streaming progress updates via SSE."""
    data = request.json
    user_message = data.get('message', '')
    session_id = data.get('session_id', 'default')

    if not user_message:
        return jsonify({'error': 'No message provided'}), 400

    def generate():
        conversation_history = get_or_create_session(session_id)
        conversation_history.append({"role": "user", "content": user_message})

        # Keep history manageable
        if len(conversation_history) > 20:
            conversation_history = conversation_history[-20:]
            chat_sessions[session_id] = conversation_history

        client = get_anthropic_client()
        executor = get_query_executor()
        tools = get_chat_tools()

        executed_queries = []
        generated_charts = []
        generated_topologies = []
        iteration = 0
        max_iterations = 10  # Safety limit

        try:
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': 'Analyzing your question...', 'step': 1})}\n\n"

            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=conversation_history
            )

            # Handle tool use loop
            while response.stop_reason == "tool_use" and iteration < max_iterations:
                iteration += 1
                tool_results = []

                # Count tools to execute
                tool_count = sum(1 for cb in response.content if cb.type == "tool_use")
                tool_index = 0

                for content_block in response.content:
                    if content_block.type == "tool_use":
                        tool_index += 1

                        if content_block.name == "execute_sql":
                            sql = content_block.input.get("sql", "")
                            # Send query status
                            yield f"data: {json.dumps({'type': 'status', 'message': f'Executing query {tool_index}/{tool_count}...', 'step': iteration + 1, 'detail': sql[:80] + '...' if len(sql) > 80 else sql})}\n\n"

                            result = executor.execute_query(sql)
                            executed_queries.append({"sql": sql, "result": result})

                            row_count = result.get('row_count', 0) if result.get('success') else 0
                            yield f"data: {json.dumps({'type': 'query_result', 'query_index': len(executed_queries) - 1, 'row_count': row_count, 'success': result.get('success', False)})}\n\n"

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": content_block.id,
                                "content": json.dumps(result, default=str)
                            })

                        elif content_block.name == "generate_chart":
                            chart_title = content_block.input.get("title", "Chart")
                            yield f"data: {json.dumps({'type': 'status', 'message': f'Generating chart: {chart_title}...', 'step': iteration + 1})}\n\n"

                            chart_data = {
                                "chart_type": content_block.input.get("chart_type", "line"),
                                "title": content_block.input.get("title", "Chart"),
                                "labels": content_block.input.get("labels", []),
                                "datasets": content_block.input.get("datasets", [])
                            }
                            generated_charts.append(chart_data)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": content_block.id,
                                "content": json.dumps({"success": True, "message": "Chart generated successfully"})
                            })

                        elif content_block.name == "generate_topology":
                            topo_title = content_block.input.get("title", "Topology")
                            yield f"data: {json.dumps({'type': 'status', 'message': f'Generating topology: {topo_title}...', 'step': iteration + 1})}\n\n"

                            topology_data = {
                                "title": topo_title,
                                "nodes": content_block.input.get("nodes", []),
                                "edges": content_block.input.get("edges", [])
                            }
                            generated_topologies.append(topology_data)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": content_block.id,
                                "content": json.dumps({"success": True, "message": "Topology generated successfully"})
                            })

                conversation_history.append({"role": "assistant", "content": response.content})
                conversation_history.append({"role": "user", "content": tool_results})

                # Send analyzing status before next API call
                yield f"data: {json.dumps({'type': 'status', 'message': 'Analyzing results...', 'step': iteration + 1})}\n\n"

                response = client.messages.create(
                    model=ANTHROPIC_MODEL,
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    tools=tools,
                    messages=conversation_history
                )

            # Extract final response
            yield f"data: {json.dumps({'type': 'status', 'message': 'Preparing response...', 'step': iteration + 2})}\n\n"

            final_response = ""
            for content_block in response.content:
                if hasattr(content_block, 'text'):
                    final_response += content_block.text

            conversation_history.append({"role": "assistant", "content": final_response})

            # Send final result (use default=str to handle Decimal types from Trino)
            yield f"data: {json.dumps({'type': 'complete', 'response': final_response, 'queries': executed_queries, 'charts': generated_charts, 'topologies': generated_topologies}, default=str)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages (non-streaming fallback)."""
    data = request.json
    user_message = data.get('message', '')
    session_id = data.get('session_id', 'default')

    if not user_message:
        return jsonify({'error': 'No message provided'}), 400

    conversation_history = get_or_create_session(session_id)
    conversation_history.append({"role": "user", "content": user_message})

    # Keep history manageable
    if len(conversation_history) > 20:
        conversation_history = conversation_history[-20:]
        chat_sessions[session_id] = conversation_history

    client = get_anthropic_client()
    executor = get_query_executor()
    tools = get_chat_tools()

    executed_queries = []
    generated_charts = []
    generated_topologies = []

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=conversation_history
        )

        # Handle tool use loop
        while response.stop_reason == "tool_use":
            tool_results = []

            for content_block in response.content:
                if content_block.type == "tool_use":
                    if content_block.name == "execute_sql":
                        sql = content_block.input.get("sql", "")
                        result = executor.execute_query(sql)
                        executed_queries.append({"sql": sql, "result": result})
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": json.dumps(result, default=str)
                        })
                    elif content_block.name == "generate_chart":
                        chart_data = {
                            "chart_type": content_block.input.get("chart_type", "line"),
                            "title": content_block.input.get("title", "Chart"),
                            "labels": content_block.input.get("labels", []),
                            "datasets": content_block.input.get("datasets", [])
                        }
                        generated_charts.append(chart_data)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": json.dumps({"success": True, "message": "Chart generated successfully"})
                        })
                    elif content_block.name == "generate_topology":
                        topology_data = {
                            "title": content_block.input.get("title", "Topology"),
                            "nodes": content_block.input.get("nodes", []),
                            "edges": content_block.input.get("edges", [])
                        }
                        generated_topologies.append(topology_data)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": json.dumps({"success": True, "message": "Topology generated successfully"})
                        })

            conversation_history.append({"role": "assistant", "content": response.content})
            conversation_history.append({"role": "user", "content": tool_results})

            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=conversation_history
            )

        # Extract final response
        final_response = ""
        for content_block in response.content:
            if hasattr(content_block, 'text'):
                final_response += content_block.text

        conversation_history.append({"role": "assistant", "content": final_response})

        return jsonify({
            'response': final_response,
            'queries': executed_queries,
            'charts': generated_charts,
            'topologies': generated_topologies
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/clear', methods=['POST'])
def clear_session():
    """Clear chat session."""
    data = request.json
    session_id = data.get('session_id', 'default')
    chat_sessions[session_id] = []
    return jsonify({'status': 'cleared'})


@app.route('/api/status', methods=['GET'])
def system_status():
    """Get current system status."""
    executor = get_query_executor()
    time_param = request.args.get('time', '5m')

    # Parse time parameter
    time_value = int(time_param[:-1])
    time_unit = time_param[-1]

    if time_unit == 's':
        interval = f"'{time_value}' SECOND"
    elif time_unit == 'm':
        interval = f"'{time_value}' MINUTE"
    elif time_unit == 'h':
        interval = f"'{time_value}' HOUR"
    else:
        interval = "'5' MINUTE"

    status = {
        'services': [],
        'databases': [],
        'hosts': [],
        'recent_errors': [],
        'error_summary': {},
        'timestamp': datetime.utcnow().isoformat()
    }

    # Get service health - discover from 1 hour, but calculate stats for selected window
    # Use two queries and merge in Python for better compatibility

    # First: discover all services from the last hour
    all_services_query = """
    SELECT DISTINCT service_name
    FROM traces_otel_analytic
    WHERE start_time > NOW() - INTERVAL '1' HOUR
    """
    all_services = set()
    result = executor.execute_query(all_services_query)
    if result['success']:
        all_services = {row['service_name'] for row in result['rows']}

    # Second: get stats for the selected time window
    stats_query = f"""
    SELECT service_name,
           COUNT(*) as total_spans,
           SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) as errors,
           ROUND(100.0 * SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as error_pct,
           ROUND(AVG(duration_ns / 1000000.0), 2) as avg_latency_ms
    FROM traces_otel_analytic
    WHERE start_time > NOW() - INTERVAL {interval}
    GROUP BY service_name
    ORDER BY total_spans DESC
    """
    stats_by_service = {}
    result = executor.execute_query(stats_query)
    if result['success']:
        for row in result['rows']:
            stats_by_service[row['service_name']] = row

    # Merge: all discovered services with their stats (or zeros if no recent activity)
    services_list = []
    for svc in all_services:
        if svc in stats_by_service:
            services_list.append(stats_by_service[svc])
        else:
            # Service exists but has no activity in selected time window
            services_list.append({
                'service_name': svc,
                'total_spans': 0,
                'errors': 0,
                'error_pct': None,
                'avg_latency_ms': None
            })

    # Sort by total_spans descending
    services_list.sort(key=lambda x: x['total_spans'], reverse=True)
    status['services'] = services_list

    # Get database status
    db_query = """
    SELECT db_system,
           COUNT(*) as span_count,
           MAX(start_time) as last_seen,
           ROUND(AVG(duration_ns / 1000000.0), 2) as avg_latency_ms
    FROM traces_otel_analytic
    WHERE db_system IS NOT NULL AND db_system != ''
      AND start_time > NOW() - INTERVAL '10' MINUTE
    GROUP BY db_system
    """
    result = executor.execute_query(db_query)
    if result['success']:
        status['databases'] = result['rows']

    # Get error summary stats
    error_summary_query = """
    SELECT
        COUNT(*) as total_errors,
        COUNT(DISTINCT service_name) as affected_services
    FROM traces_otel_analytic
    WHERE status_code = 'ERROR'
      AND start_time > NOW() - INTERVAL '5' MINUTE
    """
    result = executor.execute_query(error_summary_query)
    if result['success'] and result['rows']:
        status['error_summary'] = result['rows'][0]

    # Get recent errors with trace_id and span_id for drill-down
    error_query = """
    SELECT trace_id, span_id, service_name, span_name, status_code,
           duration_ns / 1000000.0 as duration_ms,
           start_time
    FROM traces_otel_analytic
    WHERE status_code = 'ERROR'
      AND start_time > NOW() - INTERVAL '5' MINUTE
    ORDER BY start_time DESC
    LIMIT 10
    """
    result = executor.execute_query(error_query)
    if result['success']:
        status['recent_errors'] = result['rows']

    # Get host metrics (CPU, memory, etc.)
    # Note: memory.utilization has state=used/free/cached - we want state=used
    host_query = """
    SELECT
        SUBSTR(attributes_flat,
               POSITION('host.name=' IN attributes_flat) + 10,
               POSITION(',' IN SUBSTR(attributes_flat, POSITION('host.name=' IN attributes_flat) + 10)) - 1
        ) as host_name,
        MAX(CASE WHEN metric_name = 'system.cpu.utilization' AND value_double <= 1 THEN ROUND(value_double * 100, 1) END) as cpu_pct,
        MAX(CASE WHEN metric_name = 'system.memory.utilization' AND attributes_flat LIKE '%state=used%' AND value_double <= 1 THEN ROUND(value_double * 100, 1) END) as memory_pct,
        MAX(CASE WHEN metric_name = 'system.filesystem.utilization' AND value_double <= 1 THEN ROUND(value_double * 100, 1) END) as disk_pct,
        MAX(timestamp) as last_seen
    FROM metrics_otel_analytic
    WHERE metric_name IN ('system.cpu.utilization', 'system.memory.utilization', 'system.filesystem.utilization')
      AND timestamp > NOW() - INTERVAL '5' MINUTE
      AND attributes_flat LIKE '%host.name=%'
    GROUP BY SUBSTR(attributes_flat,
               POSITION('host.name=' IN attributes_flat) + 10,
               POSITION(',' IN SUBSTR(attributes_flat, POSITION('host.name=' IN attributes_flat) + 10)) - 1
        )
    HAVING SUBSTR(attributes_flat,
               POSITION('host.name=' IN attributes_flat) + 10,
               POSITION(',' IN SUBSTR(attributes_flat, POSITION('host.name=' IN attributes_flat) + 10)) - 1
        ) IS NOT NULL
    """
    result = executor.execute_query(host_query)
    if result['success']:
        status['hosts'] = result['rows']

    return jsonify(status)


@app.route('/api/query', methods=['POST'])
def execute_query():
    """Execute a custom SQL query."""
    data = request.json
    sql = data.get('sql', '')

    if not sql:
        return jsonify({'error': 'No SQL provided'}), 400

    executor = get_query_executor()
    result = executor.execute_query(sql)
    return jsonify(result)


@app.route('/api/service/<service_name>', methods=['GET'])
def service_details(service_name):
    """Get detailed metrics for a specific service."""
    executor = get_query_executor()
    time_range = request.args.get('range', '1')  # hours

    data = {
        'service_name': service_name,
        'latency_history': [],
        'error_history': [],
        'throughput_history': [],
        'recent_errors': [],
        'top_operations': []
    }

    # Latency over time (1-minute buckets)
    latency_query = f"""
    SELECT
        date_trunc('minute', start_time) as time_bucket,
        ROUND(AVG(duration_ns / 1000000.0), 2) as avg_latency_ms,
        ROUND(MAX(duration_ns / 1000000.0), 2) as max_latency_ms,
        COUNT(*) as request_count
    FROM traces_otel_analytic
    WHERE service_name = '{service_name}'
      AND start_time > NOW() - INTERVAL '{time_range}' HOUR
    GROUP BY date_trunc('minute', start_time)
    ORDER BY time_bucket
    """
    result = executor.execute_query(latency_query)
    if result['success']:
        data['latency_history'] = result['rows']

    # Error rate over time
    error_query = f"""
    SELECT
        date_trunc('minute', start_time) as time_bucket,
        COUNT(*) as total,
        SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) as errors,
        ROUND(100.0 * SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) / COUNT(*), 2) as error_pct
    FROM traces_otel_analytic
    WHERE service_name = '{service_name}'
      AND start_time > NOW() - INTERVAL '{time_range}' HOUR
    GROUP BY date_trunc('minute', start_time)
    ORDER BY time_bucket
    """
    result = executor.execute_query(error_query)
    if result['success']:
        data['error_history'] = result['rows']

    # Recent errors for this service
    recent_errors_query = f"""
    SELECT span_name, status_code, start_time,
           duration_ns / 1000000.0 as duration_ms
    FROM traces_otel_analytic
    WHERE service_name = '{service_name}'
      AND status_code = 'ERROR'
      AND start_time > NOW() - INTERVAL '{time_range}' HOUR
    ORDER BY start_time DESC
    LIMIT 10
    """
    result = executor.execute_query(recent_errors_query)
    if result['success']:
        data['recent_errors'] = result['rows']

    # Top operations by volume
    top_ops_query = f"""
    SELECT span_name,
           COUNT(*) as call_count,
           ROUND(AVG(duration_ns / 1000000.0), 2) as avg_latency_ms,
           ROUND(100.0 * SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) / COUNT(*), 2) as error_pct
    FROM traces_otel_analytic
    WHERE service_name = '{service_name}'
      AND start_time > NOW() - INTERVAL '{time_range}' HOUR
    GROUP BY span_name
    ORDER BY call_count DESC
    LIMIT 10
    """
    result = executor.execute_query(top_ops_query)
    if result['success']:
        data['top_operations'] = result['rows']

    return jsonify(data)


@app.route('/api/error/<trace_id>/<span_id>', methods=['GET'])
def error_details(trace_id, span_id):
    """Get detailed information about a specific error."""
    executor = get_query_executor()

    data = {
        'error_info': None,
        'exception': None,
        'trace': []
    }

    # Get error span info
    error_query = f"""
    SELECT service_name, span_name, span_kind, status_code,
           duration_ns / 1000000.0 as duration_ms,
           start_time, db_system
    FROM traces_otel_analytic
    WHERE trace_id = '{trace_id}' AND span_id = '{span_id}'
    LIMIT 1
    """
    result = executor.execute_query(error_query)
    if result['success'] and result['rows']:
        data['error_info'] = result['rows'][0]

    # Get exception details from span_events
    exception_query = f"""
    SELECT exception_type, exception_message
    FROM span_events_otel_analytic
    WHERE trace_id = '{trace_id}' AND span_id = '{span_id}'
      AND exception_type IS NOT NULL AND exception_type != ''
    LIMIT 1
    """
    result = executor.execute_query(exception_query)
    if result['success'] and result['rows']:
        data['exception'] = result['rows'][0]

    # Get full trace for context
    trace_query = f"""
    SELECT service_name, span_name, span_kind, status_code,
           duration_ns / 1000000.0 as duration_ms,
           start_time, parent_span_id
    FROM traces_otel_analytic
    WHERE trace_id = '{trace_id}'
    ORDER BY start_time
    """
    result = executor.execute_query(trace_query)
    if result['success']:
        data['trace'] = result['rows']

    return jsonify(data)


@app.route('/api/service/<service_name>/logs', methods=['GET'])
def service_logs(service_name):
    """Get recent logs for a specific service."""
    executor = get_query_executor()
    limit = min(int(request.args.get('limit', '20')), 100)
    time_param = request.args.get('time', '5m')

    # Parse time parameter
    time_value = int(time_param[:-1])
    time_unit = time_param[-1]
    if time_unit == 's':
        interval = f"'{time_value}' SECOND"
    elif time_unit == 'm':
        interval = f"'{time_value}' MINUTE"
    elif time_unit == 'h':
        interval = f"'{time_value}' HOUR"
    else:
        interval = "'5' MINUTE"

    logs_query = f"""
    SELECT timestamp, severity_text, body, trace_id, span_id
    FROM logs_otel_analytic
    WHERE service_name = '{service_name}'
      AND timestamp > NOW() - INTERVAL {interval}
    ORDER BY timestamp DESC
    LIMIT {limit}
    """
    result = executor.execute_query(logs_query)

    if result['success']:
        return jsonify({'logs': result['rows']})
    else:
        return jsonify({'logs': [], 'error': result.get('error')})


@app.route('/api/service/<service_name>/traces', methods=['GET'])
def service_traces(service_name):
    """Get recent traces for a specific service."""
    executor = get_query_executor()
    limit = min(int(request.args.get('limit', '20')), 100)
    time_param = request.args.get('time', '5m')

    # Parse time parameter
    time_value = int(time_param[:-1])
    time_unit = time_param[-1]
    if time_unit == 's':
        interval = f"'{time_value}' SECOND"
    elif time_unit == 'm':
        interval = f"'{time_value}' MINUTE"
    elif time_unit == 'h':
        interval = f"'{time_value}' HOUR"
    else:
        interval = "'5' MINUTE"

    traces_query = f"""
    SELECT trace_id, span_id, span_name, span_kind, status_code,
           ROUND(duration_ns / 1000000.0, 2) as duration_ms,
           start_time, db_system
    FROM traces_otel_analytic
    WHERE service_name = '{service_name}'
      AND start_time > NOW() - INTERVAL {interval}
    ORDER BY start_time DESC
    LIMIT {limit}
    """
    result = executor.execute_query(traces_query)

    if result['success']:
        return jsonify({'traces': result['rows']})
    else:
        return jsonify({'traces': [], 'error': result.get('error')})


@app.route('/api/service/<service_name>/metrics', methods=['GET'])
def service_metrics(service_name):
    """Get recent metrics for a specific service."""
    executor = get_query_executor()
    limit = min(int(request.args.get('limit', '20')), 100)
    time_param = request.args.get('time', '5m')

    # Parse time parameter
    time_value = int(time_param[:-1])
    time_unit = time_param[-1]
    if time_unit == 's':
        interval = f"'{time_value}' SECOND"
    elif time_unit == 'm':
        interval = f"'{time_value}' MINUTE"
    elif time_unit == 'h':
        interval = f"'{time_value}' HOUR"
    else:
        interval = "'5' MINUTE"

    # Get metrics summary by metric name for this service
    metrics_query = f"""
    SELECT metric_name,
           COUNT(*) as data_points,
           ROUND(AVG(value_double), 4) as avg_value,
           ROUND(MIN(value_double), 4) as min_value,
           ROUND(MAX(value_double), 4) as max_value,
           MAX(timestamp) as last_seen
    FROM metrics_otel_analytic
    WHERE service_name = '{service_name}'
      AND timestamp > NOW() - INTERVAL {interval}
    GROUP BY metric_name
    ORDER BY data_points DESC
    LIMIT {limit}
    """
    result = executor.execute_query(metrics_query)

    if result['success']:
        return jsonify({'metrics': result['rows']})
    else:
        return jsonify({'metrics': [], 'error': result.get('error')})


@app.route('/api/service/<service_name>/dependencies', methods=['GET'])
def service_dependencies(service_name):
    """Get upstream and downstream dependencies for a service."""
    executor = get_query_executor()
    time_param = request.args.get('time', '15m')

    # Parse time parameter
    time_value = int(time_param[:-1])
    time_unit = time_param[-1]
    if time_unit == 's':
        interval = f"'{time_value}' SECOND"
    elif time_unit == 'm':
        interval = f"'{time_value}' MINUTE"
    elif time_unit == 'h':
        interval = f"'{time_value}' HOUR"
    else:
        interval = "'15' MINUTE"

    # Find services this service calls (downstream/dependencies)
    downstream_query = f"""
    SELECT DISTINCT
        COALESCE(child.db_system, child.service_name) as dependency,
        CASE WHEN child.db_system IS NOT NULL THEN 'database' ELSE 'service' END as dep_type,
        COUNT(*) as call_count
    FROM traces_otel_analytic parent
    JOIN traces_otel_analytic child ON parent.span_id = child.parent_span_id
        AND parent.trace_id = child.trace_id
    WHERE parent.service_name = '{service_name}'
      AND (child.service_name != '{service_name}' OR child.db_system IS NOT NULL)
      AND parent.start_time > NOW() - INTERVAL {interval}
    GROUP BY COALESCE(child.db_system, child.service_name),
             CASE WHEN child.db_system IS NOT NULL THEN 'database' ELSE 'service' END
    ORDER BY call_count DESC
    LIMIT 20
    """

    # Find services that call this service (upstream/dependents)
    upstream_query = f"""
    SELECT DISTINCT
        parent.service_name as dependent,
        'service' as dep_type,
        COUNT(*) as call_count
    FROM traces_otel_analytic parent
    JOIN traces_otel_analytic child ON parent.span_id = child.parent_span_id
        AND parent.trace_id = child.trace_id
    WHERE child.service_name = '{service_name}'
      AND parent.service_name != '{service_name}'
      AND child.start_time > NOW() - INTERVAL {interval}
    GROUP BY parent.service_name
    ORDER BY call_count DESC
    LIMIT 20
    """

    data = {'upstream': [], 'downstream': []}

    result = executor.execute_query(downstream_query)
    if result['success']:
        data['downstream'] = result['rows']

    result = executor.execute_query(upstream_query)
    if result['success']:
        data['upstream'] = result['rows']

    return jsonify(data)


@app.route('/api/service/<service_name>/operations', methods=['GET'])
def service_operations(service_name):
    """Get top operations for a service with configurable time window."""
    executor = get_query_executor()
    time_param = request.args.get('time', '5m')

    # Parse time parameter (e.g., "10s", "1m", "5m", "1h")
    time_value = int(time_param[:-1])
    time_unit = time_param[-1]

    if time_unit == 's':
        interval = f"'{time_value}' SECOND"
    elif time_unit == 'm':
        interval = f"'{time_value}' MINUTE"
    elif time_unit == 'h':
        interval = f"'{time_value}' HOUR"
    else:
        interval = "'5' MINUTE"  # default

    top_ops_query = f"""
    SELECT span_name,
           COUNT(*) as call_count,
           ROUND(AVG(duration_ns / 1000000.0), 2) as avg_latency_ms,
           ROUND(100.0 * SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as error_pct
    FROM traces_otel_analytic
    WHERE service_name = '{service_name}'
      AND start_time > NOW() - INTERVAL {interval}
    GROUP BY span_name
    ORDER BY call_count DESC
    LIMIT 10
    """
    result = executor.execute_query(top_ops_query)

    if result['success']:
        return jsonify({'operations': result['rows']})
    else:
        return jsonify({'operations': [], 'error': result.get('error')})


@app.route('/api/database/<db_system>', methods=['GET'])
def database_details(db_system):
    """Get detailed metrics for a specific database system."""
    executor = get_query_executor()
    time_range = request.args.get('range', '1')  # hours

    data = {
        'db_system': db_system,
        'latency_history': [],
        'error_history': [],
        'slow_queries': []
    }

    # Query latency and volume over time (1-minute buckets)
    latency_query = f"""
    SELECT
        date_trunc('minute', start_time) as time_bucket,
        ROUND(AVG(duration_ns / 1000000.0), 2) as avg_latency_ms,
        ROUND(MAX(duration_ns / 1000000.0), 2) as max_latency_ms,
        COUNT(*) as query_count
    FROM traces_otel_analytic
    WHERE db_system = '{db_system}'
      AND start_time > NOW() - INTERVAL '{time_range}' HOUR
    GROUP BY date_trunc('minute', start_time)
    ORDER BY time_bucket
    """
    result = executor.execute_query(latency_query)
    if result['success']:
        data['latency_history'] = result['rows']

    # Error rate over time
    error_query = f"""
    SELECT
        date_trunc('minute', start_time) as time_bucket,
        COUNT(*) as total,
        SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) as errors,
        ROUND(100.0 * SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as error_pct
    FROM traces_otel_analytic
    WHERE db_system = '{db_system}'
      AND start_time > NOW() - INTERVAL '{time_range}' HOUR
    GROUP BY date_trunc('minute', start_time)
    ORDER BY time_bucket
    """
    result = executor.execute_query(error_query)
    if result['success']:
        data['error_history'] = result['rows']

    # Slowest queries by service/operation
    slow_queries_query = f"""
    SELECT service_name, span_name,
           COUNT(*) as call_count,
           ROUND(AVG(duration_ns / 1000000.0), 2) as avg_latency_ms,
           ROUND(100.0 * SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as error_pct
    FROM traces_otel_analytic
    WHERE db_system = '{db_system}'
      AND start_time > NOW() - INTERVAL '{time_range}' HOUR
    GROUP BY service_name, span_name
    ORDER BY avg_latency_ms DESC
    LIMIT 10
    """
    result = executor.execute_query(slow_queries_query)
    if result['success']:
        data['slow_queries'] = result['rows']

    return jsonify(data)


@app.route('/api/database/<db_system>/dependencies', methods=['GET'])
def database_dependencies(db_system):
    """Get services that depend on this database."""
    executor = get_query_executor()
    time_param = request.args.get('time', '15m')

    # Parse time parameter
    time_value = int(time_param[:-1])
    time_unit = time_param[-1]
    if time_unit == 's':
        interval = f"'{time_value}' SECOND"
    elif time_unit == 'm':
        interval = f"'{time_value}' MINUTE"
    elif time_unit == 'h':
        interval = f"'{time_value}' HOUR"
    else:
        interval = "'15' MINUTE"

    # Find services that call this database
    dependents_query = f"""
    SELECT DISTINCT
        service_name as dependent,
        'service' as dep_type,
        COUNT(*) as call_count,
        ROUND(AVG(duration_ns / 1000000.0), 2) as avg_latency_ms,
        ROUND(100.0 * SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) / COUNT(*), 2) as error_pct
    FROM traces_otel_analytic
    WHERE db_system = '{db_system}'
      AND start_time > NOW() - INTERVAL {interval}
    GROUP BY service_name
    ORDER BY call_count DESC
    LIMIT 20
    """

    data = {'dependents': []}

    result = executor.execute_query(dependents_query)
    if result['success']:
        data['dependents'] = result['rows']

    return jsonify(data)


@app.route('/api/host/<host_name>/services', methods=['GET'])
def host_services(host_name):
    """Get services/metrics running on this host."""
    executor = get_query_executor()
    time_param = request.args.get('time', '15m')

    # Parse time parameter
    time_value = int(time_param[:-1])
    time_unit = time_param[-1]
    if time_unit == 's':
        interval = f"'{time_value}' SECOND"
    elif time_unit == 'm':
        interval = f"'{time_value}' MINUTE"
    elif time_unit == 'h':
        interval = f"'{time_value}' HOUR"
    else:
        interval = "'15' MINUTE"

    data = {'services': [], 'current_metrics': None, 'host_info': None}

    # Find services running on this host from traces
    services_query = f"""
    SELECT
        service_name,
        COUNT(*) as span_count,
        ROUND(100.0 * SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) / COUNT(*), 1) as error_pct
    FROM spans_otel_analytic
    WHERE attributes_flat LIKE '%host.name={host_name}%'
      AND timestamp > NOW() - INTERVAL {interval}
      AND service_name IS NOT NULL AND service_name != '' AND service_name != 'unknown'
    GROUP BY service_name
    ORDER BY span_count DESC
    """

    result = executor.execute_query(services_query)
    if result['success']:
        data['services'] = result['rows']

    # Get current host metrics
    host_metrics_query = f"""
    SELECT
        MAX(CASE WHEN metric_name = 'system.cpu.utilization' AND value_double <= 1 THEN ROUND(value_double * 100, 1) END) as cpu_pct,
        MAX(CASE WHEN metric_name = 'system.memory.utilization' AND attributes_flat LIKE '%state=used%' AND value_double <= 1 THEN ROUND(value_double * 100, 1) END) as memory_pct,
        MAX(CASE WHEN metric_name = 'system.filesystem.utilization' AND value_double <= 1 THEN ROUND(value_double * 100, 1) END) as disk_pct,
        MAX(timestamp) as last_seen
    FROM metrics_otel_analytic
    WHERE attributes_flat LIKE '%host.name={host_name}%'
      AND metric_name IN ('system.cpu.utilization', 'system.memory.utilization', 'system.filesystem.utilization')
      AND timestamp > NOW() - INTERVAL '5' MINUTE
    """

    result = executor.execute_query(host_metrics_query)
    if result['success'] and result['rows']:
        row = result['rows'][0]
        data['current_metrics'] = {
            'cpu_pct': row.get('cpu_pct'),
            'memory_pct': row.get('memory_pct'),
            'disk_pct': row.get('disk_pct')
        }
        data['host_info'] = {
            'last_seen': row.get('last_seen')
        }

    # Get OS type from metrics attributes
    os_query = f"""
    SELECT DISTINCT
        CASE
            WHEN attributes_flat LIKE '%os.type=linux%' THEN 'linux'
            WHEN attributes_flat LIKE '%os.type=windows%' THEN 'windows'
            WHEN attributes_flat LIKE '%os.type=darwin%' THEN 'darwin'
            ELSE 'unknown'
        END as os_type
    FROM metrics_otel_analytic
    WHERE attributes_flat LIKE '%host.name={host_name}%'
      AND timestamp > NOW() - INTERVAL '5' MINUTE
    LIMIT 1
    """

    result = executor.execute_query(os_query)
    if result['success'] and result['rows']:
        if data['host_info'] is None:
            data['host_info'] = {}
        data['host_info']['os_type'] = result['rows'][0].get('os_type', 'unknown')

    return jsonify(data)


# =============================================================================
# Alerts API
# =============================================================================

@app.route('/api/alerts/config', methods=['GET'])
def get_alerts_config():
    """Get investigation configuration for display in UI."""
    return jsonify({
        'investigate_critical_only': INVESTIGATE_CRITICAL_ONLY
    })


@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Get alerts with optional filtering."""
    executor = get_query_executor()

    status = request.args.get('status', 'active')  # active, resolved, all
    severity = request.args.get('severity')  # info, warning, critical
    service = request.args.get('service')
    limit = min(int(request.args.get('limit', 50)), 100)

    data = {
        'alerts': [],
        'summary': {
            'active': 0,
            'critical': 0,
            'warning': 0,
            'info': 0
        }
    }

    # Build query with filters
    conditions = []

    if status == 'active':
        conditions.append("status = 'active'")
    elif status == 'resolved':
        conditions.append("status = 'resolved'")
    # 'all' has no status filter

    if severity:
        conditions.append(f"severity = '{severity}'")

    if service:
        conditions.append(f"service_name = '{service}'")

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    # Get alerts with investigations
    alerts_query = f"""
    SELECT
        a.alert_id,
        a.created_at,
        a.updated_at,
        a.service_name,
        a.alert_type,
        a.severity,
        a.title,
        a.description,
        a.metric_type,
        a.current_value,
        a.baseline_value,
        a.z_score,
        a.status,
        a.resolved_at,
        a.auto_resolved,
        i.investigation_id,
        i.investigated_at,
        i.root_cause_summary,
        i.recommended_actions,
        i.supporting_evidence,
        i.queries_executed,
        i.tokens_used,
        i.model_used
    FROM alerts a
    LEFT JOIN alert_investigations i ON a.alert_id = i.alert_id
    {where_clause.replace('status', 'a.status').replace('severity', 'a.severity').replace('service_name', 'a.service_name') if where_clause else ''}
    ORDER BY
        CASE a.severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
        a.created_at DESC
    LIMIT {limit}
    """

    result = executor.execute_query(alerts_query)
    if result['success']:
        data['alerts'] = result['rows']

    # Get summary counts
    summary_query = """
    SELECT
        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
        SUM(CASE WHEN status = 'active' AND severity = 'critical' THEN 1 ELSE 0 END) as critical,
        SUM(CASE WHEN status = 'active' AND severity = 'warning' THEN 1 ELSE 0 END) as warning,
        SUM(CASE WHEN status = 'active' AND severity = 'info' THEN 1 ELSE 0 END) as info
    FROM alerts
    """
    result = executor.execute_query(summary_query)
    if result['success'] and result['rows']:
        row = result['rows'][0]
        data['summary'] = {
            'active': row.get('active') or 0,
            'critical': row.get('critical') or 0,
            'warning': row.get('warning') or 0,
            'info': row.get('info') or 0
        }

    return jsonify(data)


@app.route('/api/alerts/<alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    """Acknowledge an alert."""
    executor = get_query_executor()

    sql = f"""
    UPDATE alerts
    SET status = 'acknowledged',
        updated_at = NOW()
    WHERE alert_id = '{alert_id}'
    """

    try:
        cursor = executor.conn.cursor()
        cursor.execute(sql)
        return jsonify({'success': True, 'message': f'Alert {alert_id} acknowledged'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/alerts/<alert_id>/resolve', methods=['POST'])
def resolve_alert(alert_id):
    """Manually resolve an alert."""
    executor = get_query_executor()

    sql = f"""
    UPDATE alerts
    SET status = 'resolved',
        resolved_at = NOW(),
        updated_at = NOW(),
        auto_resolved = false
    WHERE alert_id = '{alert_id}'
    """

    try:
        cursor = executor.conn.cursor()
        cursor.execute(sql)
        return jsonify({'success': True, 'message': f'Alert {alert_id} resolved'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/alerts/<alert_id>/archive', methods=['POST'])
def archive_alert(alert_id):
    """Archive an alert (moves it out of active view but keeps history)."""
    executor = get_query_executor()

    sql = f"""
    UPDATE alerts
    SET status = 'archived',
        updated_at = NOW()
    WHERE alert_id = '{alert_id}'
    """

    try:
        cursor = executor.conn.cursor()
        cursor.execute(sql)
        return jsonify({'success': True, 'message': f'Alert {alert_id} archived'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/alerts/<alert_id>/investigate', methods=['POST'])
def investigate_alert(alert_id):
    """Manually trigger investigation for an alert."""
    executor = get_query_executor()

    # Get alert details
    alert_query = f"""
    SELECT alert_id, service_name, alert_type, severity, title, description
    FROM alerts
    WHERE alert_id = '{alert_id}'
    """
    result = executor.execute_query(alert_query)
    if not result['success'] or not result['rows']:
        return jsonify({'success': False, 'error': 'Alert not found'}), 404

    alert = result['rows'][0]

    # Check if already investigated
    inv_query = f"SELECT investigation_id FROM alert_investigations WHERE alert_id = '{alert_id}'"
    inv_result = executor.execute_query(inv_query)
    if inv_result['success'] and inv_result['rows']:
        return jsonify({'success': False, 'error': 'Alert already has investigation'}), 400

    # Run investigation
    try:
        investigation = run_alert_investigation(executor, alert)
        if investigation:
            return jsonify({'success': True, 'investigation': investigation})
        else:
            return jsonify({'success': False, 'error': 'Investigation failed'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def run_alert_investigation(executor, alert):
    """Run LLM investigation for an alert."""
    import uuid

    service = alert.get('service_name', '')
    alert_type = alert.get('alert_type', '')
    alert_id = alert.get('alert_id', '')
    description = alert.get('description', '')

    system_prompt = """You are an expert SRE assistant performing root cause analysis.
You have access to observability data via SQL queries (Trino/Presto dialect).

Available tables and their EXACT columns (use ONLY these):

traces_otel_analytic (time column: start_time):
  start_time, trace_id, span_id, parent_span_id, service_name, span_name,
  span_kind, status_code, http_status, duration_ns, db_system

logs_otel_analytic (time column: timestamp):
  timestamp, service_name, severity_number, severity_text, body_text, trace_id, span_id

span_events_otel_analytic (time column: timestamp):
  timestamp, trace_id, span_id, service_name, span_name, event_name,
  exception_type, exception_message, exception_stacktrace

CRITICAL SQL RULES:
- For traces: WHERE start_time > current_timestamp - INTERVAL '15' MINUTE
- For logs/events: WHERE timestamp > current_timestamp - INTERVAL '15' MINUTE
- NO 'attributes' column exists - do not use it
- NO semicolons, NO square brackets
- Interval: INTERVAL '15' MINUTE (quoted number)

Be CONCISE. Output:
ROOT CAUSE: <one sentence>
EVIDENCE:
- <finding 1>
RECOMMENDED ACTIONS:
1. <action 1>"""

    tools = [{
        "name": "execute_sql",
        "description": "Execute a SQL query against the observability database",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "The SQL query to execute"}
            },
            "required": ["sql"]
        }
    }]

    user_prompt = f"""Investigate this alert:
Service: {service}
Alert Type: {alert_type}
Description: {description}

Find the root cause by querying the data. Focus on the last 15 minutes."""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    messages = [{"role": "user", "content": user_prompt}]
    queries_executed = 0
    total_tokens = 0

    for _ in range(5):
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            system=system_prompt,
            tools=tools,
            messages=messages
        )
        total_tokens += response.usage.input_tokens + response.usage.output_tokens

        tool_calls = [b for b in response.content if b.type == "tool_use"]
        if not tool_calls:
            break

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []

        for tool_call in tool_calls:
            if tool_call.name == "execute_sql":
                sql = tool_call.input.get("sql", "").strip().rstrip(';')
                queries_executed += 1
                result = executor.execute_query(sql)
                if result['success']:
                    result_str = json.dumps(result['rows'][:20], default=str)
                else:
                    result_str = json.dumps([{"error": result.get('error', 'Query failed')}])
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": result_str
                })

        messages.append({"role": "user", "content": tool_results})

    # Get final summary
    if response.stop_reason != "end_turn":
        messages.append({"role": "assistant", "content": response.content})

    messages.append({
        "role": "user",
        "content": "Provide your final analysis in this format:\nROOT CAUSE: <one sentence>\nEVIDENCE:\n- <finding>\nRECOMMENDED ACTIONS:\n1. <action>"
    })

    final = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1000,
        system=system_prompt,
        messages=messages
    )
    total_tokens += final.usage.input_tokens + final.usage.output_tokens

    # Parse response
    text = "".join(b.text for b in final.content if hasattr(b, 'text'))

    root_cause = ""
    actions = ""
    evidence = ""

    if "ROOT CAUSE:" in text:
        parts = text.split("ROOT CAUSE:", 1)[1]
        if "EVIDENCE:" in parts:
            root_cause = parts.split("EVIDENCE:")[0].strip()
            parts = parts.split("EVIDENCE:", 1)[1]
            if "RECOMMENDED ACTIONS:" in parts:
                evidence = parts.split("RECOMMENDED ACTIONS:")[0].strip()
                actions = parts.split("RECOMMENDED ACTIONS:", 1)[1].strip()
            else:
                evidence = parts.strip()
        else:
            root_cause = parts.strip()

    # Store investigation
    investigation_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    store_sql = f"""
    INSERT INTO alert_investigations (
        investigation_id, alert_id, investigated_at, service_name, alert_type,
        model_used, root_cause_summary, recommended_actions, supporting_evidence,
        queries_executed, tokens_used
    ) VALUES (
        '{investigation_id}', '{alert_id}', TIMESTAMP '{now}', '{service}', '{alert_type}',
        '{ANTHROPIC_MODEL}', '{root_cause.replace("'", "''")}', '{actions.replace("'", "''")}',
        '{evidence.replace("'", "''")}', {queries_executed}, {total_tokens}
    )
    """

    try:
        cursor = executor.conn.cursor()
        cursor.execute(store_sql)
    except Exception as e:
        print(f"Failed to store investigation: {e}")

    return {
        "investigation_id": investigation_id,
        "root_cause_summary": root_cause,
        "recommended_actions": actions,
        "supporting_evidence": evidence,
        "queries_executed": queries_executed,
        "tokens_used": total_tokens
    }


@app.route('/api/alerts/history', methods=['GET'])
def get_alert_history():
    """Get historical alert data for trend analysis."""
    executor = get_query_executor()

    hours = min(int(request.args.get('hours', 24)), 168)  # max 1 week

    data = {
        'hourly_counts': [],
        'by_service': [],
        'by_type': []
    }

    # Hourly alert counts
    hourly_query = f"""
    SELECT
        date_trunc('hour', created_at) as hour,
        COUNT(*) as total,
        SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) as critical,
        SUM(CASE WHEN severity = 'warning' THEN 1 ELSE 0 END) as warning
    FROM alerts
    WHERE created_at > NOW() - INTERVAL '{hours}' HOUR
    GROUP BY date_trunc('hour', created_at)
    ORDER BY hour
    """
    result = executor.execute_query(hourly_query)
    if result['success']:
        data['hourly_counts'] = result['rows']

    # Alerts by service
    by_service_query = f"""
    SELECT
        service_name,
        COUNT(*) as total,
        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active
    FROM alerts
    WHERE created_at > NOW() - INTERVAL '{hours}' HOUR
    GROUP BY service_name
    ORDER BY total DESC
    LIMIT 10
    """
    result = executor.execute_query(by_service_query)
    if result['success']:
        data['by_service'] = result['rows']

    # Alerts by type
    by_type_query = f"""
    SELECT
        alert_type,
        COUNT(*) as total,
        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active
    FROM alerts
    WHERE created_at > NOW() - INTERVAL '{hours}' HOUR
    GROUP BY alert_type
    ORDER BY total DESC
    """
    result = executor.execute_query(by_type_query)
    if result['success']:
        data['by_type'] = result['rows']

    return jsonify(data)


@app.route('/api/baselines', methods=['GET'])
def get_baselines():
    """Get current baselines for monitoring."""
    executor = get_query_executor()

    service = request.args.get('service')

    data = {
        'baselines': []
    }

    conditions = ["1=1"]
    if service:
        conditions.append(f"service_name = '{service}'")

    where_clause = " AND ".join(conditions)

    # Get latest baselines for each service/metric combination
    baselines_query = f"""
    SELECT
        b.service_name,
        b.metric_type,
        b.baseline_mean,
        b.baseline_stddev,
        b.baseline_p50,
        b.baseline_p95,
        b.baseline_p99,
        b.sample_count,
        b.window_hours,
        b.computed_at
    FROM service_baselines b
    INNER JOIN (
        SELECT service_name, metric_type, MAX(computed_at) as max_computed
        FROM service_baselines
        WHERE {where_clause}
        GROUP BY service_name, metric_type
    ) latest ON b.service_name = latest.service_name
        AND b.metric_type = latest.metric_type
        AND b.computed_at = latest.max_computed
    ORDER BY b.service_name, b.metric_type
    """

    result = executor.execute_query(baselines_query)
    if result['success']:
        data['baselines'] = result['rows']

    return jsonify(data)


@app.route('/api/anomalies', methods=['GET'])
def get_anomalies():
    """Get recent anomaly scores."""
    executor = get_query_executor()

    minutes = min(int(request.args.get('minutes', 60)), 1440)  # max 24 hours
    service = request.args.get('service')
    only_anomalies = request.args.get('only_anomalies', 'true').lower() == 'true'

    data = {
        'anomalies': []
    }

    conditions = [f"timestamp > NOW() - INTERVAL '{minutes}' MINUTE"]

    if service:
        conditions.append(f"service_name = '{service}'")

    if only_anomalies:
        conditions.append("is_anomaly = true")

    where_clause = " AND ".join(conditions)

    anomalies_query = f"""
    SELECT
        timestamp,
        service_name,
        metric_type,
        current_value,
        expected_value,
        baseline_mean,
        baseline_stddev,
        z_score,
        anomaly_score,
        is_anomaly,
        detection_method
    FROM anomaly_scores
    WHERE {where_clause}
    ORDER BY timestamp DESC
    LIMIT 100
    """

    result = executor.execute_query(anomalies_query)
    if result['success']:
        data['anomalies'] = result['rows']

    return jsonify(data)


@app.route('/api/alerts/activity', methods=['GET'])
def get_alert_activity():
    """Get recent alert activity (created, resolved, auto-resolved)."""
    executor = get_query_executor()

    minutes = min(int(request.args.get('minutes', 60)), 1440)  # max 24 hours
    limit = min(int(request.args.get('limit', 20)), 100)

    data = {
        'events': []
    }

    # Get recent alert events from alerts table
    # We construct events from created_at, resolved_at timestamps
    activity_query = f"""
    WITH alert_events AS (
        -- Created events
        SELECT
            created_at as event_time,
            'created' as event_type,
            service_name,
            alert_type,
            severity,
            title
        FROM alerts
        WHERE created_at > NOW() - INTERVAL '{minutes}' MINUTE

        UNION ALL

        -- Resolved events (auto and manual)
        SELECT
            resolved_at as event_time,
            CASE WHEN auto_resolved = true THEN 'auto_resolved' ELSE 'resolved' END as event_type,
            service_name,
            alert_type,
            severity,
            title
        FROM alerts
        WHERE resolved_at IS NOT NULL
            AND resolved_at > NOW() - INTERVAL '{minutes}' MINUTE
    )
    SELECT
        event_time,
        event_type,
        service_name,
        alert_type,
        severity,
        title
    FROM alert_events
    ORDER BY event_time DESC
    LIMIT {limit}
    """

    result = executor.execute_query(activity_query)
    if result['success']:
        data['events'] = result['rows']

    return jsonify(data)


# =============================================================================
# Main
# =============================================================================

if __name__ == '__main__':
    # Validate config
    errors = []
    if not ANTHROPIC_API_KEY:
        errors.append("ANTHROPIC_API_KEY is required")
    if not TRINO_HOST:
        errors.append("TRINO_HOST is required")
    if not TRINO_AVAILABLE:
        errors.append("trino package not installed")

    if errors:
        print("Configuration errors:")
        for e in errors:
            print(f"  - {e}")
        exit(1)

    print("Starting Observability Diagnostic Web UI...")
    print(f"Trino: {TRINO_HOST}:{TRINO_PORT}")
    print(f"Model: {ANTHROPIC_MODEL}")
    print("\nOpen http://localhost:5000 in your browser\n")

    app.run(host='0.0.0.0', port=5000, debug=True)
