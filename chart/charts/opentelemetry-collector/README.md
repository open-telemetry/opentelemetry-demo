# OpenTelemetry Collector Helm Chart

The helm chart installs [OpenTelemetry Collector](https://github.com/open-telemetry/opentelemetry-collector)
in kubernetes cluster.

## Prerequisites

- Kubernetes 1.24+
- Helm 3.9+

## Installing the Chart

Add OpenTelemetry Helm repository:

```console
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
```

To install the chart with the release name my-opentelemetry-collector, run the following command:

```console
helm install my-opentelemetry-collector open-telemetry/opentelemetry-collector --set mode=<value> --set image.repository="ghcr.io/open-telemetry/opentelemetry-collector-releases/opentelemetry-collector-k8s" --set command.name="otelcol-k8s"
```

Where the `mode` value needs to be set to one of `daemonset`, `deployment` or `statefulset`.

For an in-depth walk through getting started in Kubernetes using this helm chart, see [OpenTelemetry Kubernetes Getting Started](https://opentelemetry.io/docs/kubernetes/getting-started/).

## Upgrading

See [UPGRADING.md](UPGRADING.md).

## Security Considerations

OpenTelemetry Collector recommends to bind receivers' servers to addresses that limit connections to authorized users.
For this reason, by default the chart binds all the Collector's endpoints to the pod's IP.

More info is available in the [Security Best Practices documentation](https://github.com/open-telemetry/opentelemetry-collector/blob/main/docs/security-best-practices.md#safeguards-against-denial-of-service-attacks)

Some care must be taken when using `hostNetwork: true`, as then OpenTelemetry Collector will listen on all the addresses in the host network namespace.

## Configuration

### Default configuration

By default this chart will deploy an OpenTelemetry Collector with three pipelines (logs, metrics and traces)
and debug exporter enabled by default. The collector can be installed either as daemonset (agent), deployment or stateful set.

*Example*: Install collector as a deployment.

```yaml
mode: deployment
```

By default collector has the following receivers enabled:

- **metrics**: OTLP and prometheus. Prometheus is configured only for scraping collector's own metrics.
- **traces**: OTLP, zipkin and jaeger (thrift and grpc).
- **logs**: OTLP (to enable container logs, see [Configuration for Kubernetes container logs](#configuration-for-kubernetes-container-logs)).

### Basic Top Level Configuration

The Collector's configuration is set via the `config` section. Default components can be removed with `null`. Remember that lists in helm are not merged, so if you want to modify any default list you must specify all items, including any default items you want to keep.

*Example*: Disable metrics and logs pipelines and non-otlp receivers:

```yaml
config:
  receivers:
    jaeger: null
    prometheus: null
    zipkin: null
  service:
    pipelines:
      traces:
        receivers:
          - otlp
      metrics: null
      logs: null
```

The chart also provides several presets, detailed below, to help configure important Kubernetes components. For more details on each component, see [Kubernetes Collector Components](https://opentelemetry.io/docs/kubernetes/collector/components/).

### Configuration for Kubernetes Container Logs

The collector can be used to collect logs sent to standard output by Kubernetes containers.
This feature is disabled by default. It has the following requirements:

- It needs agent collector to be deployed.
- It requires the [Filelog receiver](https://opentelemetry.io/docs/kubernetes/collector/components/#filelog-receiver) to be included in the collector, such as [k8s](https://github.com/open-telemetry/opentelemetry-collector-releases/tree/main/distributions/otelcol-k8s) version of the collector image.

To enable this feature, set the  `presets.logsCollection.enabled` property to `true`.
Here is an example `values.yaml`:

```yaml
mode: daemonset

presets:
  logsCollection:
    enabled: true
    includeCollectorLogs: true
```

The way this feature works is it adds a `filelog` receiver on the `logs` pipeline. This receiver is preconfigured
to read the files where Kubernetes container runtime writes all containers' console output to.

#### :warning: Warning: Risk of looping the exported logs back into the receiver, causing "log explosion"

#### Log collection for a subset of pods or containers

The `logsCollection` preset will by default ingest the logs of all kubernetes containers.
This is achieved by using an include path of `/var/log/pods/*/*/*.log` for the `filelog`receiver.

To limit the import to a certain subset of pods or containers, the `filelog`
receivers `include` list can be overwritten by supplying explicit configuration.

E.g. The following configuration would only import logs for pods within the namespace: `example-namespace`:

```yaml
mode: daemonset

presets:
  logsCollection:
    enabled: true
config:
  receivers:
    filelog:
      include:
        - /var/log/pods/example-namespace_*/*/*.log
```

The container logs pipeline uses the `debug` exporter by default.
Paired with the default `filelog` receiver that receives all containers' console output,
it is easy to accidentally feed the exported logs back into the receiver.

Also note that using the `--verbosity=detailed` option for the `debug` exporter causes it to output
multiple lines per single received log, which when looped, would amplify the logs exponentially.

To prevent the looping, the default configuration of the receiver excludes logs from the collector's containers.

If you want to include the collector's logs, make sure to replace the `debug` exporter
with an exporter that does not send logs to collector's standard output.

Here's an example `values.yaml` file that replaces the default `debug` exporter on the `logs` pipeline
with an `otlphttp` exporter that sends the container logs to `https://example.com:55681` endpoint.
It also clears the `filelog` receiver's `exclude` property, for collector logs to be included in the pipeline.

```yaml
mode: daemonset

presets:
  logsCollection:
    enabled: true
    includeCollectorLogs: true

config:
  exporters:
    otlphttp:
      endpoint: https://example.com:55681
  service:
    pipelines:
      logs:
        exporters:
          - otlphttp
```

### Configuration for Kubernetes Attributes Processor

The collector can be configured to add Kubernetes metadata, such as pod name and namespace name, as resource attributes to incoming logs, metrics and traces.

This feature is disabled by default. It has the following requirements:

- It requires the [Kubernetes Attributes processor](https://opentelemetry.io/docs/kubernetes/collector/components/#kubernetes-attributes-processor) to be included in the collector, such as [k8s](https://github.com/open-telemetry/opentelemetry-collector-releases/tree/main/distributions/otelcol-k8s) version of the collector image.

#### :memo: Note: Changing or supplementing `k8sattributes` scopes

In order to minimize the collector's privileges, the [Kubernetes RBAC Rules](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) that are applied to the collector as part of this chart are the minimum required for the `presets.kubernetesAttributes` preset to work. If additional configuration scopes are desired outside of the preset you must apply the corresponding RBAC rules to grant the collector access.

To enable this feature, set the  `presets.kubernetesAttributes.enabled` property to `true`.
Here is an example `values.yaml`:

```yaml
mode: daemonset
presets:
  kubernetesAttributes:
    enabled: true
    # You can also configure the preset to add all of the associated pod's labels and annotations to you telemetry.
    # The label/annotation name will become the resource attribute's key.
    extractAllPodLabels: true
    extractAllPodAnnotations: true
```

### Configuration for Annotation-Based Discovery

The collector can be configured to automatically discover and collect telemetry from pods based on annotations. For logs specifically the feature can be used as a drop-in replacement for the `logsCollection` preset, allowing for more selective collection of logs and additional parsing capabilities.

> [!WARNING] > `annotationDiscovery.logs` and `logsCollection` are mutually exclusive.

`presets.annotationDiscovery.logs.enabled: true`: Collects logs only from all pods by-default, and allows to define additional configuration through annotations. Log collection from specific Pods/containers, can be disabled by using the proper annotation.

Here is an example `values.yaml`:

```yaml
mode: daemonset

image:
  repository: "ghcr.io/open-telemetry/opentelemetry-collector-releases/opentelemetry-collector-k8s"

command:
  name: "otelcol-k8s"

presets:
  annotationDiscovery:
    logs:
      enabled: true
    metrics:
      enabled: true
```

#### How Annotation-Based Discovery Works

When annotation-based discovery is enabled, the collector will:

1. **Discover Pods**: Use the Receiver Creator receiver to watch for pods with specific annotations
2. **Generate Receiver Configurations**: Automatically generate receiver configuration

**Default Behavior**: When `presets.annotationDiscovery.logs.enabled` is `true`, the collector will collect logs from all containers by default, unless a pod explicitly opts out using the `io.opentelemetry.discovery.logs/enabled: "false"` annotation.

This approach provides the same functionality as `logsCollection` but with fine-grained control over which pods are monitored, making it ideal for environments where you want to selectively collect telemetry from specific applications or services.

For more details and configuration options, see the [Receiver Creator](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/receiver/receivercreator/README.md#generate-receiver-configurations-from-provided-hints) documentation.

#### :memo: Note: RBAC Permissions

When annotation-based discovery is enabled, the chart automatically creates the necessary RBAC rules to allow the collector to list pods in the cluster. This is required for the Receiver Creator receiver to discover pods with the relevant annotations.

### Configuration for Retrieving Kubelet Metrics

The collector can be configured to collect node, pod, and container metrics from the API server on a kubelet.

This feature is disabled by default. It has the following requirements:

- It requires the [Kubeletstats receiver](https://opentelemetry.io/docs/kubernetes/collector/components/#kubeletstats-receiver) to be included in the collector, such as [k8s](https://github.com/open-telemetry/opentelemetry-collector-releases/tree/main/distributions/otelcol-k8s) version of the collector image.

To enable this feature, set the  `presets.kubeletMetrics.enabled` property to `true`.
Here is an example `values.yaml`:

```yaml
mode: daemonset
presets:
  kubeletMetrics:
    enabled: true
```

### Configuration for Kubernetes Cluster Metrics

The collector can be configured to collects cluster-level metrics from the Kubernetes API server. A single instance of this receiver can be used to monitor a cluster.

This feature is disabled by default. It has the following requirements:

- It requires the [Kubernetes Cluster receiver](https://opentelemetry.io/docs/kubernetes/collector/components/#kubernetes-cluster-receiver) to be included in the collector, such as [k8s](https://github.com/open-telemetry/opentelemetry-collector-releases/tree/main/distributions/otelcol-k8s) version of the collector image.
- It requires statefulset or deployment mode with a single replica.

To enable this feature, set the  `presets.clusterMetrics.enabled` property to `true`.

Here is an example `values.yaml`:

```yaml
mode: deployment
replicaCount: 1
presets:
  clusterMetrics:
    enabled: true
```

### Configuration for Retrieving Kubernetes Events

The collector can be configured to collect Kubernetes events.

This feature is disabled by default. It has the following requirements:

- It requires [Kubernetes Objects receiver](https://opentelemetry.io/docs/kubernetes/collector/components/#kubernetes-objects-receiver) to be included in the collector, such as [k8s](https://github.com/open-telemetry/opentelemetry-collector-releases/tree/main/distributions/otelcol-k8s) version of the collector image.

To enable this feature, set the  `presets.kubernetesEvents.enabled` property to `true`.
Here is an example `values.yaml`:

```yaml
mode: deployment
replicaCount: 1
presets:
  kubernetesEvents:
    enabled: true
```

### Configuration for Host Metrics

The collector can be configured to collect host metrics for Kubernetes nodes.

This feature is disabled by default. It has the following requirements:

- It requires [Host Metrics receiver](https://opentelemetry.io/docs/kubernetes/collector/components/#host-metrics-receiver) to be included in the collector, such as [k8s](https://github.com/open-telemetry/opentelemetry-collector-releases/tree/main/distributions/otelcol-k8s) version of the collector image.

To enable this feature, set the  `presets.hostMetrics.enabled` property to `true`.
Here is an example `values.yaml`:

```yaml
mode: daemonset
presets:
  hostMetrics:
    enabled: true
```

## CRDs

At this time, Prometheus CRDs are supported but other CRDs are not.

### Service Account Configuration

The chart allows you to control the `automountServiceAccountToken` setting for the collector pods. This can be useful for security purposes when you want to prevent automatic mounting of the service account token.

*Example*: Disable automatic mounting of service account token:

```yaml
serviceAccount:
  create: true
  automountServiceAccountToken: false
```

By default, `automountServiceAccountToken` is set to `true` (Kubernetes default behavior). When set to `false`, the service account token will not be automatically mounted into the collector pods.

### Other configuration options

The [values.yaml](./values.yaml) file contains information about all other configuration
options for this chart.

For more examples see [Examples](examples).
