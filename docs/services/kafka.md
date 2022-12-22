# Kafka

This is used as a message queue service to connect the checkout service with
the accounting and fraud detection services.

[Kafka service source](../../src/kafka/)

## Auto-instrumentation

This service relies on the OpenTelemetry Java Agent and the built in
[JMX Metric Insight Module](https://github.com/open-telemetry/opentelemetry-java-instrumentation/tree/main/instrumentation/jmx-metrics/javaagent)
to capture [kafka broker metrics](https://github.com/open-telemetry/opentelemetry-java-instrumentation/blob/main/instrumentation/jmx-metrics/javaagent/kafka-broker.md)
and send them off to the collector via OTLP.

The agent is passed into the process using the `-javaagent` command line
argument. Command line arguments are added through the `KAFKA_OPTS`
in the `Dockerfile`.

```dockerfile
ENV KAFKA_OPTS="-javaagent:/tmp/opentelemetry-javaagent.jar -Dotel.jmx.target.system=kafka-broker"
```
