# OpAMP Server

This service runs the Go reference OpAMP server from
[`open-telemetry/opamp-go`](https://github.com/open-telemetry/opamp-go).

The OpenTelemetry Collector connects to this service through the Collector
`opampextension` and reports its health status, version, attributes, and
effective configuration. The server also exposes a minimal HTML UI that is
routed through the frontend proxy at
[`/opamp/`](http://localhost:8080/opamp/).

This demonstrates how OpAMP can be used as a Collector control plane.

The reference UI is patched during the Docker build so its links work when
served under the demo's `/opamp/` proxy prefix.
