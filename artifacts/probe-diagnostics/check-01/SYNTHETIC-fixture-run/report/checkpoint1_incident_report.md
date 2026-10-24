# Eyes incident symptom report

Origin: fixture
Incident: incident-897caa6016a74d8f9da9ed8344105c74
Service: checkout
Window: {"start": "2026-01-01T11:56:00Z", "end": "2026-01-01T12:01:00Z"}

## Executive summary
An automatically detected metric breach initiated this observation workflow. Root cause is not established.

## Observed alert facts
- {"metric": "latency_p95_ms", "threshold": 1000, "value": 1500, "timestamp": "2026-01-01T12:01:00Z", "source_time": "2026-01-01T12:01:00Z", "evidence_id": "fixture-10", "freshness_evidence_id": "fresh-7b8b89097786da711fb1efbe", "coverage_evidence_id": "fixture-9", "query": "fixture metric expression"}

## Telemetry and timeline
- 2026-01-01T12:01:30Z — search_traces: ok [fixture-15]
~~~json
{
  "tool": "search_traces",
  "service": "checkout",
  "window": {
    "start": "2026-01-01T11:56:00Z",
    "end": "2026-01-01T12:01:00Z"
  },
  "origin": "fixture",
  "status": "ok",
  "warnings": [],
  "collected_at": "2026-01-01T12:01:30Z",
  "evidence_id": "fixture-15",
  "observations": [
    {
      "source_id": "fixture-source",
      "samples": [
        {
          "timestamp": "2026-01-01T12:01:30Z",
          "value": 500
        }
      ],
      "symptom": "timeout"
    }
  ],
  "provenance": {
    "query": "fixture metric expression"
  }
}
~~~
- 2026-01-01T12:01:30Z — search_logs: ok [fixture-16]
~~~json
{
  "tool": "search_logs",
  "service": "checkout",
  "window": {
    "start": "2026-01-01T11:56:00Z",
    "end": "2026-01-01T12:01:00Z"
  },
  "origin": "fixture",
  "status": "ok",
  "warnings": [],
  "collected_at": "2026-01-01T12:01:30Z",
  "evidence_id": "fixture-16",
  "observations": [
    {
      "source_id": "fixture-source",
      "samples": [
        {
          "timestamp": "2026-01-01T12:01:30Z",
          "value": 500
        }
      ],
      "symptom": "timeout"
    }
  ],
  "provenance": {
    "query": "fixture metric expression"
  }
}
~~~

## Model interpretations (require operator review)
- Timeout symptoms require further investigation [fixture-16]

## Missing evidence and limitations
- Synthetic test data
- Interpretations are model hypotheses; reference validation does not prove semantic entailment. Root cause is not established by this Eyes report.

## Model execution
~~~json
[
  {
    "model": "fixture-model",
    "slot": "fixture",
    "backend": "fixture",
    "provider": "operator-configured compatible provider"
  },
  {
    "model": "fixture-model",
    "slot": "fixture",
    "backend": "fixture",
    "provider": "operator-configured compatible provider"
  },
  {
    "model": "fixture-model",
    "slot": "fixture",
    "backend": "fixture",
    "provider": "operator-configured compatible provider"
  }
]
~~~
Stop reason: model_finished
