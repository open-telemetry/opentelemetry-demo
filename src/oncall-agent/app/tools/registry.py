from typing import Any, Callable

from app.tools.containers import get_container_health
from app.tools.deployments import get_recent_changes
from app.tools.diagnosis import submit_diagnosis
from app.tools.jaeger import get_trace, search_traces
from app.tools.logs import search_logs
from app.tools.memory import search_incident_memory
from app.tools.prometheus import get_health_overview, query_prometheus

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_health_overview",
            "description": "Fetch overall system health from Prometheus span metrics, ranked by error rate and latency anomalies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lookback_min": {
                        "type": "integer",
                        "description": "Time window in minutes to compute metrics over (default: 15).",
                        "default": 15,
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_prometheus",
            "description": "Execute a PromQL range query against Prometheus and receive a compact summary (min, max, last, trend).",
            "parameters": {
                "type": "object",
                "properties": {
                    "promql": {
                        "type": "string",
                        "description": "The PromQL expression to query.",
                    },
                    "lookback_min": {
                        "type": "integer",
                        "description": "Time window in minutes (default: 15).",
                        "default": 15,
                    },
                },
                "required": ["promql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_traces",
            "description": "Search distributed traces in Jaeger for a given service, optionally filtering for errors or minimum latency.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Target service name to search traces for.",
                    },
                    "error_only": {
                        "type": "boolean",
                        "description": "Only return traces that contain error spans.",
                        "default": False,
                    },
                    "min_duration_ms": {
                        "type": "integer",
                        "description": "Minimum trace duration in milliseconds.",
                        "default": 0,
                    },
                    "lookback_min": {
                        "type": "integer",
                        "description": "Time window in minutes (default: 15).",
                        "default": 15,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of traces to return (default: 5).",
                        "default": 5,
                    },
                },
                "required": ["service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trace",
            "description": "Retrieve detailed span hierarchy and error details for a specific trace ID. Strips feature flags.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trace_id": {
                        "type": "string",
                        "description": "The 32-character hexadecimal trace ID.",
                    }
                },
                "required": ["trace_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_logs",
            "description": "Query structured application logs from OpenSearch for a service, deduplicating repetitive messages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Target service name.",
                    },
                    "severity": {
                        "type": "string",
                        "description": "Filter by severity level ('error', 'warn', 'info').",
                    },
                    "text": {
                        "type": "string",
                        "description": "Substring or message text to search for.",
                    },
                    "lookback_min": {
                        "type": "integer",
                        "description": "Time window in minutes (default: 15).",
                        "default": 15,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of unique log patterns to return (default: 10).",
                        "default": 10,
                    },
                },
                "required": ["service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_container_health",
            "description": "Inspect container runtime health, status, restart counts, OOM kills, CPU%, and memory limits via Action API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Optional service/container name to inspect. Omit to list all containers.",
                        "default": "",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_changes",
            "description": "Inspect recent container lifecycle events (starts, stops, restarts, OOM) and Action API changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lookback_min": {
                        "type": "integer",
                        "description": "Time window in minutes (default: 60).",
                        "default": 60,
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_incident_memory",
            "description": "Search past resolved incidents in memory for similar symptoms, root causes, and effective runbooks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symptom_summary": {
                        "type": "string",
                        "description": "Summary of current symptoms, failing services, and observed anomalies.",
                    }
                },
                "required": ["symptom_summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_diagnosis",
            "description": "Terminal tool: submit the final structured diagnosis with exact evidence citations and calibrated confidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component": {
                        "type": "string",
                        "description": "The root-cause service component identified.",
                    },
                    "cause_category": {
                        "type": "string",
                        "description": "Category: service_fault_injected_errors | dependency_unavailable | container_down_or_crashloop | resource_exhaustion_memory | resource_exhaustion_cpu | traffic_overload | latency_degradation | data_store_unavailable | unknown",
                    },
                    "cause_description": {
                        "type": "string",
                        "description": "Concise technical explanation of the failure mechanism.",
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence score between 0.0 and 1.0.",
                    },
                    "evidence": {
                        "type": "array",
                        "description": "List of evidence items [{evidence_id, type, ref, why_it_matters}] citing previous tool outputs.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "evidence_id": {
                                    "type": "string",
                                    "description": "Exact evidence ID (e.g. 'E1', 'E2') from tool outputs.",
                                },
                                "type": {
                                    "type": "string",
                                    "description": "Evidence type: metric | trace | log | container | change | memory",
                                },
                                "ref": {
                                    "type": "string",
                                    "description": "Exact quoted substring, trace ID, or metric value present in that evidence output.",
                                },
                                "why_it_matters": {
                                    "type": "string",
                                    "description": "Why this evidence proves the root cause or refutes alternatives.",
                                },
                            },
                            "required": ["evidence_id", "type", "ref", "why_it_matters"],
                        },
                    },
                    "alternatives_considered": {
                        "type": "array",
                        "description": "List of alternative hypotheses evaluated and why they were refuted.",
                        "items": {"type": "string"},
                    },
                    "recommended_runbook_ids": {
                        "type": "array",
                        "description": "List of recommended runbook IDs.",
                        "items": {"type": "string"},
                    },
                },
                "required": ["component", "cause_category", "cause_description", "confidence", "evidence"],
            },
        },
    },
]

TOOL_FUNCTIONS: dict[str, Callable[..., str]] = {
    "get_health_overview": get_health_overview,
    "query_prometheus": query_prometheus,
    "search_traces": search_traces,
    "get_trace": get_trace,
    "search_logs": search_logs,
    "get_container_health": get_container_health,
    "get_recent_changes": get_recent_changes,
    "search_incident_memory": search_incident_memory,
    "submit_diagnosis": submit_diagnosis,
}


def execute_tool(name: str, args: dict[str, Any] | None = None) -> str:
    func = TOOL_FUNCTIONS.get(name)
    if not func:
        return f"Error: Tool '{name}' is not recognized. Available tools: {sorted(TOOL_FUNCTIONS.keys())}"

    kwargs = args or {}
    try:
        raw_result = func(**kwargs)
        result_str = str(raw_result)
        # CRITICAL CONSTRAINT: outputs must remain compact (<= 2000 chars)
        if len(result_str) > 2000:
            result_str = result_str[:1960] + "\n... [truncated to 2000 chars]"
        return result_str
    except TypeError as e:
        return f"Error: Invalid parameters for tool '{name}': {e}"
    except Exception as e:
        return f"Error executing tool '{name}': {e}"
