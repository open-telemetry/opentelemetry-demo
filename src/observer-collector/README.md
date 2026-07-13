# Observer Collector

This service runs a second OpenTelemetry Collector, managed by the
[OpAMP Supervisor](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/cmd/opampsupervisor).
It receives the main Collector's own (self) telemetry and forwards it to the
observability backends.

The main Collector's self-telemetry (metrics and logs) is routed here instead of
back to itself, so that the observability-of-the-observability path is handled by
a dedicated, non-critical Collector. Splitting it out keeps the alpha OpAMP
Supervisor in front of a small surface area, isolated from the webstore's
application telemetry.

The Supervisor is the OpAMP client: it connects to the demo's OpAMP server,
manages the observer Collector process, and can apply remote configuration pushed
from the server. Showcasing OpAMP remote configuration control is left for a
future change.

Only enabled when running with the observability stack
(`compose.observability.yaml`).
