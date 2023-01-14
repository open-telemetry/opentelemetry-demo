# OpenTelemetry Demo with Instana Agent and OTEL Collector

This repo is a fork of the original [OpenTelemetry Demo](https://github.com/open-telemetry/opentelemetry-demo) with added integration to Instana host-agent OTLP endpoint and application infrastructure monitoring configuration.

## Build and run the demo webstore app locally

Follow the main [README](README.md). This is basically:
```sh
docker compose build
docker compose up -d
```

**Note**, if you plan to push the built images to a remote container registry, such as for deploying the demo in Kubernetes, you should modify the `IMAGE_NAME` variable in `.env` and use your own registry domain. 


To push the images to a remote container registry, login to the registry (`oc registry login` in case of OpenShift internal registry) and run:
```sh
make push
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

Create or edit a gradle properties file for adservice (`src/adservice/gradele.properties`) and frauddetectionservice (`src/frauddetectionservice/gradle.properties`) and fill in your proxy settings:
```
systemProp.https.proxyHost=192.168.31.253
systemProp.https.proxyPort=3128
```

Build the app with `http_proxy` and `https_proxy` build agruments passed to `docker-compose`:
```sh
docker compose build \ 
    --build-arg 'https_proxy=http://192.168.31.253:3128' \
    --build-arg 'http_proxy=http://192.168.31.253:3128' 
```

## Run Instana agent locally

Create an environment file for `docker-compose` with your Instana connection configuration. Use the template:
```sh
cd instana-agent
cp instana-agent.env.template .env
```
Launch the agent (still inside the `instana-agent` directory):
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
To demosntrate the context propagation across Instana and OTel tracing implementations, we chose to instrument the `frontendproxy` service with the Instana native tracer. The Instana sensor supports W3C propagatiopn headers, which is the default propagation header format used by OpenTelemetry. We use a custom build of the Instana envoy sensor which supports W3C context propagation (public release of the W3C enabled sensor is due soon).

## Deploy in Kubernetes

Create new namespace/project:
```sh
kubectl create namespace otel-demo

# or equivalently in OpenShift:
oc new-project otel-demo
```

In OpenShift, make sure you have sufficient privileges to run the pods in the namespace (this step my be no longer necessary as the demo containers can now run as non-root):
```sh
oc adm policy -n otel-demo add-scc-to-user anyuid -z default
```

Deploy the Instana agent via Helm or using an operator:

Use a standard installation according to Instana documentation. Apply the agent configuration as in `instana-agent/configuration-otel.yaml`


The demo assumes that an Instana [agent Kubernetes service](https://www.ibm.com/docs/en/instana-observability/current?topic=requirements-installing-host-agent-kubernetes#instana-agent-service) `instana-agent` exists in the agent namesapce `instana-agent`. The agent service, besides exposing the standard Instana agent API endpoint, also provides the common OTLP endpoint for both gRPC (port 4317) and HTTP (port 4318) protocols across all nodes. Be aware that at the time of writing, the HTTP endpoint definition wasn't yet included in the public Instana agent Helm chart (and likely neither in the Operator). You can thus create the service manually using the following manifest that is tested to work well with the demo.
```sh
cat <<EOF | oc create -f-
apiVersion: v1
kind: Service
metadata:
  name: instana-agent
  namespace: instana-agent
  labels:
    app.kubernetes.io/name: instana-agent
spec:
  selector:
    app.kubernetes.io/name: instana-agent
  ports:
    - name: otlp-grpc
      protocol: TCP
      port: 4317
      targetPort: 4317
    - name: otlp-http
      protocol: TCP
      port: 4318
      targetPort: 4318
    - name: agent-apis
      protocol: TCP
      port: 42699
      targetPort: 42699
  internalTrafficPolicy: Local
  topologyKeys:
    - "kubernetes.io/hostname"
EOF
```

Deploy the demo using the published Helm chart:

We use custom values file with additional settings for the Instana agent to act as the default OTel traces and metrics receiver, to suppress native Instana tracing so it doesn't clash with the OTel instrumentaion, and to enable Instana to perform full component infrastructure monitoring including the databases.
```sh
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm install my-otel-demo open-telemetry/opentelemetry-demo -f values-instana-agent.yaml
```

In OpenShift, you'll want to create a route for the `frontendproxy` service for easy access to the demo frontpage and featureflags services instead of the `kubectl port-forward` way that Helm prompts you after installation.
