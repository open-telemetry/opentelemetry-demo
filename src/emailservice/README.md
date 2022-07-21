# Email Service

The Email service "sends" an email to the customer with their order details by
rendering it as a log message. It expects a JSON payload like:

```json
{
  "email": "some.address@website.com",
  "order": "<serialized order protobuf>"
}
```

## Building locally

We use `bundler` to manage dependencies. To get started, simply `bundle install`.

## Running locally

You may run this service locally with `bundle exec ruby email_server.rb`.

## Building docker image

From `src/emailservice`, run `docker build .`

## OpenTelemetry features

### Emoji Legend

- Completed: :100:
- Not Present (Yet): :construction:

### Metrics

- :construction: [Instrumentation
  Libraries](https://opentelemetry.io/docs/concepts/instrumenting-library/)
- :construction: [Manual Metric
  Creation](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/glossary.md#manual-instrumentation)
- :construction: [Collector Agent Metric
  Transformation](https://opentelemetry.io/docs/collector/deployment/#agent)
- :construction: [Push
  Metrics](https://opentelemetry.io/docs/reference/specification/metrics/sdk/#push-metric-exporter)
- :construction: [SLO Metrics](https://github.com/openslo/openslo#slo)
- :construction: [Multiple Manual Metric
  Instruments](https://opentelemetry.io/docs/reference/specification/metrics/api/#synchronous-and-asynchronous-instruments)
