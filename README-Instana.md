# OpenTelemetry Demo with Instana Backend

This repo is a fork of the original [OpenTelemetry Demo](https://github.com/open-telemetry/opentelemetry-demo) with added integration to Instana host-agent OTLP endpoint and application infrastructure monitoring configuration.

## Build and run the demo webstore app

Follow the main [README](README.md). This is basically:
```sh
docker compose up
```

### In case you are behind an HTTP proxy ...
Configure the proxy behavior for the Docker daemon systemd service according to the [guide](https://docs.docker.com/config/daemon/systemd/#httphttps-proxy).

Optionally (not needed for building and running `docker compose`), you may [configure your Docker client](https://docs.docker.com/network/proxy/) by adding the following snippet to `~/.docker/config.json`
```json
{
 "proxies":
 {
   "default":
   {
     "httpProxy": "http://192.168.31.253:3128",
     "httpsProxy": "http://192.168.31.253:3128",
     "noProxy": "192.168.0.0/16,.tec.cz.ibm.com,127.0.0.0/8"
   }
 }
}
```

Create a new gradle properties file `src/adservice/gradle.properties` with your proxy settings:
```
systemProp.https.proxyHost=192.168.31.253
systemProp.https.proxyPort=3128
```

Build the Webstore app with `http_proxy` and `https_proxy` environment variables passed to `docker-compose`:
```sh
docker compose build \ 
    --build-arg 'https_proxy=http://192.168.31.253:3128' \
    --build-arg 'http_proxy=http://192.168.31.253:3128' 
```

## Build and run Instana host agent

Create an environment file for `docker-compose` with your Instana endpoint connection configuration and keys. Use the template:
```sh
cd instana-agent
cp instana-agent.env.template .env
```

Edit the OTEL Collector configuration file [`src/otelcollector/otelcol-config.yml`](src/otelcollector/otelcol-config.yml) and replace the Instana endpoint with your host IP or DNS-resolvable hostname. Use the actual host interface IP; don't use `localhost` or `127.0.0.1` as the collector must be able to reach the IP from inside a container.

Launch the agent (inside the `instana-agent` directory):
```sh
docker compose up -d
```

## Customizations

### Link calls from FeatureFlag to Postgres database
**Problem:** FeatureFlag service calls to downstream PostgreSQL database aren't linked.  
**Reason:** The reason for the missing downstream database link is that the current v1.0 release of Erlang/Elix [OpentelemetryEcto instrumentation library](https://github.com/open-telemetry/opentelemetry-erlang-contrib/tree/main/instrumentation/opentelemetry_ecto) doesn't yet add the OTel peer attributes `net.peer.host` and `net.peer.port`. These standardized attributes are used by Instana to correlate downstream services.  
**Solution:** Although the instrumentation library provides other attributes with the downstream link details, it isn't possible to use plain OTel attributes for creating custom service mapping via [manual service configuration](https://www.ibm.com/docs/en/instana-observability/current?topic=applications-services#link-calls-to-an-existing-database-or-messaging-service-that-is-created-from-a-monitored-infrastructure-entity). Therefore, in order to inject the required attributes into the generated spans it was necessary to modify the OpentelemetryEcto library source and use the custom-built library in place of the default distribution package.

The [patched](https://github.com/styblope/opentelemetry_ecto/commit/0bc71d465621e6f76d71bc8d6d336011661eb754) OpenTelemetryEcto library is available at https://github.com/styblope/opentelemetry_ecto. The rest of the solution involved changing the FeatureFlag service Elixir code dependencies and building a new custom image.

### Adding W3C context propagation to Envoy the enable cross-tracer trace continuity
**Problem:** 

## Deploy on OpenShift


TODO: ... using the official helm chart in namespace `otel-demo`

Make sure you have sufficient privileges to run the pods:
```sh
oc adm policy -n otel-demo add-scc-to-user anyuid -z default
```

You should have a Kubernetes service configured for the Instana host-agent in order to receive OTLP traffic from the OTel collector. You can also use the following simplified service configuration:
```sh
cat <<EOF | oc create -f-
apiVersion: v1
kind: Service
metadata:
  name: instana-otlp
  namespace: instana-agent
  labels:
    app.kubernetes.io/name: instana-agent
spec:
  selector:
    app.kubernetes.io/name: instana-agent
  ports:
    - name: otlp
      protocol: TCP
      port: 4317
      targetPort: 4317
  internalTrafficPolicy: Local
EOF
```

Add an OTLP exporter endpoint for Instana by editing the otelcol configmap. 
```sh
oc edit cm my-otel-demo-otelcol
```

and make the following modifications. We'll keep the existing Jaeger export active so we can compare the tracing outcomes.
```yaml
exporters:
  otlp/jaeger:
    endpoint: 'my-otel-demo-jaeger:4317'
    tls:
      insecure: true
  otlp/instana:
    endpoint: instana-otlp.instana-agent:4317    # <service_name>.<namespace>:4317
    tls:
      insecure: true
...

service:
  pipelines:
    traces:
      exporters:
      - otlp/jaeger
      - otlp/instana
```

Apply the changes by restarting the collector pod:
```sh
oc delete pod -l app.kubernetes.io/name=otelcol
```
