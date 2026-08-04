# OpAMP Server

This service runs the Go reference OpAMP server from
[`open-telemetry/opamp-go`](https://github.com/open-telemetry/opamp-go).

The OpAMP Supervisor manages the OpenTelemetry Collector process and connects
to this service to report health and effective configuration and to receive
remote configuration. The server exposes a minimal HTML UI that is routed
through the frontend proxy at
`http://<demo-host>:8080/opamp/`.

This demonstrates how OpAMP can be used as a Collector control plane.

The Supervisor is alpha and this setup is not production guidance. It starts
the checked-in Collector configuration when the OpAMP server is unavailable
and retries the connection while telemetry continues flowing.

The UI can send remote configuration to the Collector, and the Supervisor rolls
back changes that fail to start. This demo write path is trusted-local only:
the browser posts config changes to `http://127.0.0.1:4321/save_config` on the
machine running the browser, and Compose binds that endpoint to
`127.0.0.1:4321` on the demo host. To push config with this reference UI, run
the browser on the demo host and open `http://localhost:8080/opamp/`; remote
viewers can inspect the UI at `http://<demo-host>:8080/opamp/`, but their Save
button would post to their own loopback address. Do not expose port `4321`.

Production OpAMP control planes should provide authentication, authorization,
auditing, and scoped permissions before accepting remote configuration.

## Try remote configuration locally

Open the OpAMP UI on the demo host at <http://localhost:8080/opamp/>, then
click the Collector instance ID. The **Additional Configuration** box accepts a
Collector YAML overlay snippet; the Supervisor merges it on top of the
checked-in demo config. This merge behavior is Supervisor-specific; in
Collector config, arrays generally replace existing arrays rather than append,
so include the full desired array whenever you override one.

To apply a harmless config change, paste:

```yaml
exporters:
  debug:
    sampling_initial: 10
```

After saving, the page redirects back to the agent view and the effective
configuration should show `sampling_initial: 10`.

To see rollback, paste an invalid component:

```yaml
exporters:
  nosuchcomponent:
    endpoint: nowhere
```

The Supervisor should report the remote config as failed, restart the Collector
with the last working config, and keep telemetry flowing.

To see startup fallback, stop the OpAMP server and restart the Collector:

```sh
docker compose -f compose.yaml -f compose.observability.yaml stop opamp-server
docker compose -f compose.yaml -f compose.observability.yaml restart otel-collector
```

The Collector should stay healthy using the checked-in fallback configuration.
Start the OpAMP server again with:

```sh
docker compose -f compose.yaml -f compose.observability.yaml start opamp-server
```

The reference UI is patched during the Docker build so its links work when
served under the demo's `/opamp/` proxy prefix.
