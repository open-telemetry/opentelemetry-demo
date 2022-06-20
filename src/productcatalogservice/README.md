# Read Me

When this service is run the output should be similar to the following

```json
{"message":"successfully parsed product catalog json","severity":"info","timestamp":"2022-06-02T23:54:10.191283363Z"}
{"message":"starting grpc server at :3550","severity":"info","timestamp":"2022-06-02T23:54:10.191849078Z"}
```

## OpenTelemetry features

### Emoji Legend

- Completed: :100:
- Not Present (Yet): :red_circle:

### Traces

- [Instrumentation
  Libraries](https://opentelemetry.io/docs/concepts/instrumenting-library/):
  :100:
- [Manual Span
  Creation](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/glossary.md#manual-instrumentation):
  :red_circle:
- [Span Data
  Enrichment](https://opentelemetry.io/docs/instrumentation/net/manual/#add-tags-to-an-activity):
  :100:
- Interprocess Context Propagation: :red_circle:
- [Intra-service Context
  Propagation](https://opentelemetry.io/docs/instrumentation/java/manual/#context-propagation):
  :red_circle:
- [Trace
  Links](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/overview.md#links-between-spans):
  :red_circle:
- [Baggage](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/baggage/api.md#overview):
  :red_circle:

### Metrics

- [Instrumentation
  Libraries](https://opentelemetry.io/docs/concepts/instrumenting-library/):
  :red_circle:
- [Manual Metric
  Creation](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/glossary.md#manual-instrumentation):
  :red_circle:
- [Collector Agent Metric
  Transformation](https://opentelemetry.io/docs/collector/deployment/#agent)::red_circle:
- [Push
  Metrics](https://opentelemetry.io/docs/reference/specification/metrics/sdk/#push-metric-exporter):
  :red_circle:
- [SLO Metrics](https://github.com/openslo/openslo#slo): :red_circle:
- [Multiple Manual Metric
  Instruments](https://opentelemetry.io/docs/reference/specification/metrics/api/#synchronous-and-asynchronous-instruments):
  :red_circle:
