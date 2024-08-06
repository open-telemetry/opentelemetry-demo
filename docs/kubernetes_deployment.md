
# Kubernetes

We provide an [OpenTelemetry Demo Helm chart](https://github.com/open-telemetry/opentelemetry-helm-charts/tree/main/charts/opentelemetry-demo)
to help deploy the demo to an existing Kubernetes cluster. We also provide a
[values.yaml](https://github.com/newrelic/opentelemetry-demo/blob/main/helm/values.yaml)
template to customize the deployment for New Relic. More details on this are included
below.

[Helm](https://helm.sh) must be installed to use the charts. Please refer to
Helm's [documentation](https://helm.sh/docs/) to get started.

## Prerequisites

- Pre-existing Kubernetes 1.23+ Cluster
- Helm 3.9+
- New Relic Account

**Please note that this chart is not supported for clusters running on arm64
architecture, such as kind/minikube running on Apple Silicon.**

## Install the Chart

Add OpenTelemetry Helm repository:

```console
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts && helm repo update open-telemetry
```

Set your New Relic license key environment variable:

```console
export NEW_RELIC_LICENSE_KEY='<NEW_RELIC_LICENSE_KEY>'
```

Set a Kubernetes secret containing your New Relic license key:

```console
kubectl create ns opentelemetry-demo && kubectl create secret generic newrelic-license-key --from-literal=license-key="$NEW_RELIC_LICENSE_KEY" -n opentelemetry-demo
```

To install the chart with the release name newrelic-otel, run the following
command and pass in the provided `values.yaml` file to customize the deployment:

```console
helm upgrade --install newrelic-otel open-telemetry/opentelemetry-demo --version 0.32.0 --values ./helm/values.yaml -n opentelemetry-demo
```

**Remark:** If your New Relic account is in Europe, install the chart as follows instead:

```console
helm upgrade --install newrelic-otel open-telemetry/opentelemetry-demo --version 0.32.0 --values ./helm/values.yaml --set opentelemetry-collector.config.exporters.otlp.endpoint="otlp.eu01.nr-data.net:4317" -n opentelemetry-demo
```

## New Relic Overrides (Optional)

Optionally, you can enable a version of the `recommendationService` that is instrumented with New Relic APM instead of OpenTelemetry.  New Relic APM instrumented services are interoperable with OpenTelemetry instrumented services as New Relic supports W3C trace context.

```console
helm upgrade --install newrelic-otel open-telemetry/opentelemetry-demo --version 0.32.0 --values ./helm/values.yaml --values ./helm/recommendation_service_values.yaml -n opentelemetry-demo
```

## Install Prometheus Exporters (Optional)

You can install the Prometheus Exporters for Kafka, Postgres, and Redis to expose Prometheus metrics for the Kafka,
Postgres, and Redis components used by the demo application.

Add the Prometheus Helm repository:

```console
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts && helm repo update prometheus-community
```

Install the Prometheus Kafka exporter:

```console
helm upgrade --install prometheus-kafka-exporter prometheus-community/prometheus-kafka-exporter --values ./helm/prometheus-kafka-exporter/values.yaml -n opentelemetry-demo
```

Install the Prometheus Postgres exporter:

```console
helm upgrade --install prometheus-postgres-exporter prometheus-community/prometheus-postgres-exporter --values ./helm/prometheus-postgres-exporter/values.yaml -n opentelemetry-demo
```

Install the Prometheus Redis exporter:

```console
helm upgrade --install prometheus-redis-exporter prometheus-community/prometheus-redis-exporter --values ./helm/prometheus-redis-exporter/values.yaml -n opentelemetry-demo
```

## Install Kubernetes Integration (Optional)

You can install the New Relic Kubernetes integration, which includes the Prometheus Agent, to give you visibility into
 the K8s cluster used to host the demo application.

Add the New Relic Helm repository:

```console
helm repo add newrelic https://helm-charts.newrelic.com && helm repo update newrelic
```

Install the New Relic Kubernetes integration (be sure to add your New Relic
 license key and K8s cluster name):

```console
 helm upgrade --install newrelic-bundle newrelic/nri-bundle \
 --set global.licenseKey=<NEW_RELIC_LICENSE_KEY> \
 --set global.cluster=<K8S_CLUSTER_NAME> \
 --namespace=newrelic \
 --create-namespace \
 --set newrelic-infrastructure.privileged=true \
 --set nri-metadata-injection.enable=true \
 --set kube-state-metrics.enabled=true \
 --set newrelic-logging.enabled=false \
 --set nri-kube-events.enabled=true \
 --set newrelic-prometheus-agent.enabled=true \
 --set newrelic-prometheus-agent.lowDataMode=true \
 --set-json='newrelic-prometheus-agent.config.kubernetes.integrations_filter.app_values=["redis", "kafka", "postgres"]'
```

## Helm Chart Parameters

Chart parameters are separated in 4 general sections:

- `default` - Used to specify defaults applied to all demo components
- `components` - Used to configure the individual components (microservices) for
the demo
- `opentelemetry-collector` - Used to configure the OpenTelemetry Collector

## New Relic Configurations

In our values template we have disabled several observability components in
favor of the New Relic tool suite:

| Parameter                          | Description                                   | Default |
|------------------------------------|-----------------------------------------------|---------|
| `opentelemetry-collector.enabled`  | Enables the OpenTelemetry Collector sub-chart | `true`  |
| `jaeger.enabled`                   | Enables the Jaeger sub-chart                  | `false`  |
| `prometheus.enabled`               | Enables the Prometheus sub-chart              | `false`  |
| `grafana.enabled`                  | Enables the Grafana sub-chart                 | `false`  |
| `opensearch.enabled`               | Enables the Opensearch sub-chart              | `false`  |

### OpenTelemetry Collector

> **Note**
> The following parameters have a `opentelemetry-collector.` prefix.

- `mode`: Specifies the mode in which the collector should run. In this case, it
  is set to run in a "daemonset" mode, which means that the collector will be
  running on each node in a Kubernetes cluster. We use this mode for the
  resourcedetection, k8sattributes processors
- `service`: Configures the service that is exposed by the collector, it uses
 LoadBalancer type service on AWS.
- `ports`: Configures the ports that the collector should listen on. In this
  case, it is configured to listen on several different ports for different
  protocols such as otlp, otlp-http, jaeger-compact, jaeger-thrift, jaeger-grpc,
  zipkin and metrics, with some protocols enabled and some disabled based on
  support and usage.
- `podAnnotations`: Configures annotations that should be added to the collector's
  pod. In this case, it is configured to be scraped by Prometheus and specify the
  port for Prometheus to scrape on.
- `config` :
  - `extensions` : used for health_check and zpages.
  - `receivers` : used to configure the different receivers that the collector
  should use to receive telemetry data. like hostmetrics and otlp.
  - `processors` : used to configure the different processors that the collector
  should use to process telemetry data. like batch [(New Relic Opentelemetry Framework)](https://discuss.newrelic.com/t/opentelemetry-troubleshooting-framework-troubleshooting/178669),
  cumulativetodelta [(New Relic Opentelemetry metrics)](https://docs.newrelic.com/docs/more-integrations/open-source-telemetry-integrations/opentelemetry/best-practices/opentelemetry-best-practices-metrics/#otel-histogram),
  resource, resourcedetection, and k8sattributes
  [(Link OpenTelemetry-instrumented applications to Kubernetes in New Relic)](https://docs.newrelic.com/docs/kubernetes-pixie/kubernetes-integration/advanced-configuration/link-otel-applications-kubernetes/).
  - `exporters` : used to configure the New Relic OTLP backed with the required
    `api-key` header
- `service` inside `config` is used to configure the service extensions,
  `pipelines` are used to configure the different pipelines that the collector
  should use to process different types of telemetry data, like traces and
  metrics with their respective receivers, processors and exporters.
- `ingress` configuration is not present in the file since we are using the
  LoadBalancer type service on AWS

> **Note**
> Please make sure to update the collector configuration options according to
> your needs before using values template file.

### Component parameters

The OpenTelemetry demo contains several components (microservices). Each
component is configured with a common set of parameters. All components will be
defined within `components.[NAME]` where `[NAME]` is the name of the demo component.

> **Note**
> The following parameters require a `components.[NAME].` prefix where `[NAME]`
> is the name of the demo component.

| Parameter                            | Description                                                                                                | Default                                                       |
|--------------------------------------|------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------|
| `enabled`                            | Is this component enabled                                                                                  | `true`                                                        |
| `useDefault.env`                     | Use the default environment variables in this component                                                    | `true`                                                        |
| `imageOverride.repository`           | Name of image for this component                                                                           | Defaults to the overall default image repository              |
| `imageOverride.tag`                  | Tag of the image for this component                                                                        | Defaults to the overall default image tag                     |
| `imageOverride.pullPolicy`           | Image pull policy for this component                                                                       | `IfNotPresent`                                                |
| `imageOverride.pullSecrets`          | Image pull secrets for this component                                                                      | `[]`                                                          |
| `servicePort`                        | Service port used for this component                                                                       | `nil`                                                         |
| `ports`                              | Array of ports to open for deployment and service of this component                                        | `[]`                                                          |
| `env`                                | Array of environment variables added to this component                                                     | Each component will have its own set of environment variables |
| `envOverrides`                       | Used to override individual environment variables without re-specifying the entire array                   | `[]`                                                          |
| `resources`                          | CPU/Memory resource requests/limits                                                                        | Each component will have a default memory limit set           |
| `schedulingRules.nodeSelector`       | Node labels for pod assignment                                                                             | `{}`                                                          |
| `schedulingRules.affinity`           | Man of node/pod affinities                                                                                 | `{}`                                                          |
| `schedulingRules.tolerations`        | Tolerations for pod assignment                                                                             | `[]`                                                          |
| `securityContext`                    | Container security context to define user ID (UID), group ID (GID) and other security policies             | `{}`                                                          |
| `podAnnotations`                     | Pod annotations for this component                                                                         | `{}`                                                          |
| `ingress.enabled`                    | Enable the creation of Ingress rules                                                                       | `false`                                                       |
| `ingress.annotations`                | Annotations to add to the ingress rule                                                                     | `{}`                                                          |
| `ingress.ingressClassName`           | Ingress class to use. If not specified default Ingress class will be used.                                 | `nil`                                                         |
| `ingress.hosts`                      | Array of Hosts to use for the ingress rule.                                                                | `[]`                                                          |
| `ingress.hosts[].paths`              | Array of paths / routes to use for the ingress rule host.                                                  | `[]`                                                          |
| `ingress.hosts[].paths[].path`       | Actual path route to use                                                                                   | `nil`                                                         |
| `ingress.hosts[].paths[].pathType`   | Path type to use for the given path. Typically this is `Prefix`.                                           | `nil`                                                         |
| `ingress.hosts[].paths[].port`       | Port to use for the given path                                                                             | `nil`                                                         |
| `ingress.additionalIngresses`        | Array of additional ingress rules to add. This is handy if you need to differently annotated ingress rules | `[]`                                                          |
| `ingress.additionalIngresses[].name` | Each additional ingress rule needs to have a unique name                                                   | `nil`                                                         |
| `command`                            | Command & arguments to pass to the container being spun up for this service                                | `[]`                                                          |
| `configuration`                      | Configuration for the container being spun up; will create a ConfigMap, Volume and VolumeMount             | `{}`                                                          |

The services are configured to use the OpenTelemetry exporter to send traces
and metrics to a backend service. The endpoint for these services are set to
use the environment variable `OTEL_EXPORTER_OTLP_ENDPOINT`. The endpoint is
set to the value `http://$(HOST_IP):4317` and `http://$(HOST_IP):4318` respectively.

This configuration is necessary because the service is deployed as a Kubernetes
daemonset. A daemonset ensures that all, or some, nodes run a copy the collector
pod. This means the IP address of the endpoint may be different depending on the
node that the pod is running on. By using the variable `HOST_IP` the exporter
 will automatically substitute the correct IP address of the endpoint when the
  pod starts up, regardless of which node it's running on.

So, this configuration ensures that the exporter sends traces and metrics to the
correct endpoint, even if the pod is running on different nodes in the
kubernetes cluster.

### Default parameters (applied to all demo components)

| Property                               | Description                                                                               | Default                                              |
|----------------------------------------|-------------------------------------------------------------------------------------------|------------------------------------------------------|
| `default.env`                          | Environment variables added to all components                                             | Array of several OpenTelemetry environment variables |
| `default.envOverrides`                 | Used to override individual environment variables without re-specifying the entire array. | `[]`                                                 |
| `default.image.repository`             | Demo components image name                                                                | `otel/demo`                                          |
| `default.image.tag`                    | Demo components image tag (leave blank to use app version)                                | `nil`                                                |
| `default.image.pullPolicy`             | Demo components image pull policy                                                         | `IfNotPresent`                                       |
| `default.image.pullSecrets`            | Demo components image pull secrets                                                        | `[]`                                                 |
| `default.schedulingRules.nodeSelector` | Node labels for pod assignment                                                            | `{}`                                                 |
| `default.schedulingRules.affinity`     | Man of node/pod affinities                                                                | `{}`                                                 |
| `default.schedulingRules.tolerations`  | Tolerations for pod assignment                                                            | `[]`                                                 |
| `default.securityContext`              | Demo components container security context                                                | `{}`                                                 |
| `serviceAccount`                       | The name of the ServiceAccount to use for demo components                                 | `""`                                                 |

## Use the Demo

The demo application will need the services exposed outside of the Kubernetes
cluster in order to use them. You can expose the services to your local system
using the `kubectl port-forward` command or by configuring service types
(ie: LoadBalancer) with optionally deployed ingress resources.

### Expose services using kubectl port-forward

To expose the frontendproxy service use the following command (replace
`newrelic-otel` with your Helm chart release name accordingly):

```shell
kubectl port-forward svc/newrelic-otel-frontendproxy 8080:8080
```

In order for spans from the browser to be properly collected, you will also
need to expose the OpenTelemetry Collector's OTLP/HTTP port (replace
`newrelic-otel` with your Helm chart release name accordingly):

```shell
kubectl port-forward svc/newrelic-otel-otelcol 4318:4318
```

> **Note**
> `kubectl port-forward` will proxy the port until the process terminates. You
> may need to create separate terminal sessions for each use of
> `kubectl port-forward`, and use CTRL-C to terminate the process when done.

The following services are available at these paths once the proxy is exposed:
- Webstore             http://localhost:8080/
- Grafana              http://localhost:8080/grafana/
- Load Generator UI    http://localhost:8080/loadgen/
- Jaeger UI            http://localhost:8080/jaeger/ui/

### Expose services using service type configurations

> **Note**
> Kubernetes clusters may not have the proper infrastructure components to
> enable LoadBalancer service types or ingress resources. Verify your cluster
> has the proper support before using these configuration options.

Each demo service (ie: frontendproxy) offers a way to have its Kubernetes
service type configured. By default these will be `ClusterIP` but you can change
each one using the `serviceType` property for each service.

To configure the frontendproxy service to use a LoadBalancer service type you
would specify the following in your values file:

```yaml
components:
  frontendProxy:
    serviceType: LoadBalancer
```

> **Note**
> It is recommended to use a values file when installing the Helm chart in order
> to specify additional configuration options.

The Helm chart does not provide facilities to create ingress resources. If
required these would need to be created manually after installing the Helm chart.
Some Kubernetes providers require specific service types in order to be used by
ingress resources (ie: EKS ALB ingress, requires a NodePort service type).

In order for spans from the browser to be properly collected, you will also
need to expose the OpenTelemetry Collector's OTLP/HTTP port to be accessible to
user web browsers. The location where the OpenTelemetry Collector is exposed
must also be passed into the frontend service using the
`PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` environment variable. You can do
this using the following in your values file:

```yaml
components:
  frontend:
    env:
      - name: PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT
        value: "http://otel-demo-collector.mydomain.com:4318/v1/traces"
```

With the frontendproxy and Collector exposed, you can access the demo UI at the
base path for the frontendproxy. Other demo components can be accessed at the
following sub-paths:

- Webstore: `/` (base)
- Load Generator UI: `/loadgen/` (must include trailing slash)
