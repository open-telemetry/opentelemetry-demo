# Eyes incident symptom report

Origin: fixture
Incident: incident-e5ef63c228e74d3398e6e78e0acf01d2
Service: checkout
Window: {"start": "2026-01-01T11:55:30Z", "end": "2026-01-01T12:00:30Z"}

## Executive summary
An automatically detected metric breach initiated this observation workflow. Root cause is not established.

## Observed alert facts
- {"metric": "latency_p95_ms", "threshold": 1000, "value": 1500, "timestamp": "2026-01-01T12:00:30Z", "source_time": "2026-01-01T12:00:30Z", "evidence_id": "fixture-6", "freshness_evidence_id": "fresh-1c32d9b8789be44280ae04d3", "coverage_evidence_id": "fixture-5", "query": "fixture metric expression"}

## Telemetry and timeline
- 2026-01-01T12:00:45Z — search_traces: ok [fixture-7]
~~~json
{
  "tool": "search_traces",
  "service": "checkout",
  "window": {
    "start": "2026-01-01T11:55:30Z",
    "end": "2026-01-01T12:00:30Z"
  },
  "origin": "fixture",
  "status": "ok",
  "warnings": [],
  "collected_at": "2026-01-01T12:00:45Z",
  "evidence_id": "fixture-7",
  "observations": [
    {
      "source_id": "fixture-source",
      "samples": [
        {
          "timestamp": "2026-01-01T12:00:45Z",
          "value": 1500
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
- 2026-01-01T12:00:45Z — search_logs: ok [fixture-8]
~~~json
{
  "tool": "search_logs",
  "service": "checkout",
  "window": {
    "start": "2026-01-01T11:55:30Z",
    "end": "2026-01-01T12:00:30Z"
  },
  "origin": "fixture",
  "status": "ok",
  "warnings": [],
  "collected_at": "2026-01-01T12:00:45Z",
  "evidence_id": "fixture-8",
  "observations": [
    {
      "source_id": "fixture-source",
      "samples": [
        {
          "timestamp": "2026-01-01T12:00:45Z",
          "value": 1500
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
- Timeout symptoms require further investigation [fixture-8]

## Missing evidence and limitations
- Synthetic test data
- Interpretations are model hypotheses; reference validation does not prove semantic entailment. Root cause is not established by this Eyes report.

## Model execution
~~~json
[
  {
    "model": "fixture-model",
    "slot": "fixture"
  },
  {
    "model": "fixture-model",
    "slot": "fixture"
  },
  {
    "model": "fixture-model",
    "slot": "fixture"
  }
]
~~~
Stop reason: model_finished
