# Fraud Detection Service

This service analyses incoming orders and detects malicious customers.
This is only mocked and received orders are printed out.

## Auto-instrumentation

This service relies on the OpenTelemetry Java Agent to automatically instrument
libraries such as Kafka, and to configure the OpenTelemetry SDK. The agent is
passed into the process using the `-javaagent` command line argument. Command
line arguments are added through the `JAVA_TOOL_OPTIONS` in the `Dockerfile`,
and leveraged during the automatically generated Gradle startup script.

```dockerfile
ENV JAVA_TOOL_OPTIONS=-javaagent:/app/opentelemetry-javaagent.jar
```
