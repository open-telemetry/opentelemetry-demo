# Observer Collector

This service runs a second OpenTelemetry Collector, managed by the
[OpAMP Supervisor](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/cmd/opampsupervisor).
It receives the main Collector's own (self) telemetry (metrics and logs) and
forwards it to the observability backends (Prometheus and OpenSearch).

The main Collector's self-telemetry is routed here, instead of back to itself, via
the `OTEL_COLLECTOR_SELF_TELEMETRY_HOST` setting.

The Supervisor is the OpAMP client: it connects to the demo's OpAMP server,
manages the observer Collector process, and can apply remote configuration pushed
from the server.

Only enabled when running with the observability stack
(`compose.observability.yaml`).
