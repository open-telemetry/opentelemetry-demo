# Upgrade guidelines

These upgrade guidelines only contain instructions for version upgrades which require manual modifications on the user's side.
If the version you want to upgrade to is not listed here, then there is nothing to do for you.
Just upgrade and enjoy.

## 0.121.0 to 0.122.0

In the v0.123.1 Collector release we stopped pushing images to Dockerhub due to how their new rate limit changes affected our CI. If you're using `otel/opentelemetry-collector-k8s` for the image you should switch to `ghcr.io/open-telemetry/opentelemetry-collector-releases/opentelemetry-collector-k8s`. See https://github.com/open-telemetry/community/issues/2641 for more details.

## 0.110.0 to 0.110.1 or 0.110.2

We broke the selector labels in `0.110.0`, which causes `helm upgrades` to fail. Do not attempt to upgrade from `0.110.0` to either `0.110.1` or `0.110.2`. Go straight to `0.110.3` instead.

## 0.97.2 to 0.98.0

> [!WARNING]
> Critical content demanding immediate user attention due to potential risks.

The deprecated memory ballast extension has been removed from the default config. If you depend on this component you must manually configure `config.extensions` and `config.service.extensions` to include the memory ballast extension. Setting `useGOMEMLIMIT` to `false` will no longer keep the memory ballast extension in the rendered collector config.

## 0.88.0 to 0.89.0

> [!WARNING]  
> Critical content demanding immediate user attention due to potential risks.

As part of working towards using the [OpenTelemetry Collector Kubernetes Distro](https://github.com/open-telemetry/opentelemetry-collector-releases/tree/main/distributions/otelcol-k8s) by default, the chart now requires users to explicitly set an image repository. If you are already explicitly setting an image repository this breaking change does not affect you.

If you are using a OpenTelemetry Community distribution of the Collector we recommend you use `otel/opentelemetry-collector-k8s`, but carefully review the [components included in this distribution](https://github.com/open-telemetry/opentelemetry-collector-releases/blob/main/distributions/otelcol-k8s/manifest.yaml) to make sure it includes all the components you use in your configuration. In the future this distribution will become the default image used for the chart.

You can use the OpenTelemetry Collector Kubernetes Distro by adding these lines to your values.yaml:

```yaml
image:
  repository: "otel/opentelemetry-collector-k8s"
```

If you want to stick with using the Contrib distribution, add these lines to your values.yaml:

```yaml
image:
  repository: "otel/opentelemetry-collector-contrib"
```

For more details see [#1135](https://github.com/open-telemetry/opentelemetry-helm-charts/issues/1135).

## 0.84.0 to 0.85.0

The `loggingexporter` has been removed from the default configuration. Use the `debugexporter` instead.

## 0.78.2 to 0.78.3

[Update Health Check Extension's endpoints to use Pod IP Instead of 0.0.0.0](https://github.com/open-telemetry/opentelemetry-helm-charts/pull/1012)

The [Collector's security guidelines were updated](https://github.com/open-telemetry/opentelemetry-collector/pull/6959) to include containerized environments when discussing safeguards against denial of service attacks.
To be in compliance with the Collector's security best practices the chart has been updated to use the Collector's pod IP in place of `0.0.0.0`.

The chart will continue to allow complete configuration of the Collector via the `config` field in the values.yaml.  If pod IP does not suite your needs you can use `config` to set something different.

See [Security Best Practices docummentation](https://github.com/open-telemetry/opentelemetry-collector/blob/main/docs/security-best-practices.md#safeguards-against-denial-of-service-attacks) for more details.

## 0.75.1 to 0.76.0

Enable the `useGOMEMLIMIT` feature flag by default. This means by default the chart now does not use the Memory Ballast Extension and any custom configuraiton applied to the Memory Ballast Extension is ignored.

**If you're still interested in using the Memory Ballast Extension set this back to false.**

## 0.69.3 to 0.70.0

The following deprecated fields have been removed.  Please use the new values:

- `extraConfigMapMounts` -> `extraVolumes`
- `extraHostPathMounts` -> `extraVolumes`
- `secretMounts` -> `extraVolumes`
- `containerLogs` -> `presets.logsCollection`

## 0.69.0 to 0.69.1 & 0.69.2

The `loggingexporter` was replaced with the `debugexporter`. This ended up being an accidental breaking change for any user that depended on the default logging exporter config when explicitly listing the logging exporter in an exporter list.

When using versions `0.69.1` or `0.69.2` you should explicitly list the debugging exporter instead of the logging exporter. You other option is to skip these version and use `0.69.3` or newer, which includes the logging exporter configuration.

**The logging exporter will be removed in a future version.** We highly recommend switching to the debug exporter.

## 0.67 to 0.68

The `preset.kubernetesEvents` preset now excludes `DELETED` watch types so that an log is not ingested when Kubernetes deletes an event.
The intention behind this change is to cleanup the data ingested by the preset as the `DELETED` updated for a Kubernetes Events is
uninteresting. If you want to keep ingesting `DELETED` updates for Kubernetes Events you will need to configure the `k8sobjectsreceiver` manually.

## 0.62 to 0.63

The `kubernetesAttributes` preset now respects order of processors in logs, metrics and traces pipelines.
This implicitly might break your pipelines if you relied on having the `k8sAttributes` processor rendered as the first processor but also explicitly listed it in the signal's pipeline somewhere else.

## 0.55.2 to 0.56

The `tpl` function has been added to references of pod labels and ingress hosts. This adds the ability to add some reusability in
charts values through referencing global values. If you are currently using any `{{ }}` syntax in pod labels or ingress hosts it will now be rendered. To escape existing instances of {{ }}, use {{` <original content> `}}.

```yaml
global:
  region: us-east-1
  environment: stage

# Tests `tpl` function reference used in pod labels and
# ingress.hosts[*]
podLabels:
  environment: "{{ .Values.global.environment }}"

ingress:
  enabled: true
  hosts:
    - host: "otlp-collector-{{ .Values.global.region }}-{{ .Values.global.environment }}-example.dev"
      paths:
        - path: /
          pathType: Prefix
          port: 4318
```

Note that only global Helm values can be referenced as the Helm Chart schema currently does not allow `additionalValues`.

## 0.55.0 to 0.55.1

As of v0.55.1 Collector chart use `${env:ENV}` style syntax when getting environment variables and that $`{env:ENV}` syntax is not supported before collector 0.71. If you upgrade collector chart to v0.55.1, you need to make sure your collector version is after than 0.71 (default is v0.76.1).

## 0.53.1 to 0.54.0

As of v0.54.0 Collector chart, the default resource limits are removed. If you want to keep old values you can use the following configuration:

```
resources:
  limits:
    # CPU units are in fractions of 1000; memory in powers of 2
    cpu: 250m
    memory: 512Mi
```

See [the 644 issue](https://github.com/open-telemetry/opentelemetry-helm-charts/issues/644) for more information.

## 0.46.0 to 0.47.0

[Update Collector Endpoints to use Pod IP Instead of 0.0.0.0](https://github.com/open-telemetry/opentelemetry-helm-charts/pull/603)

The [Collector's security guidelines were updated](https://github.com/open-telemetry/opentelemetry-collector/pull/6959) to include containerized environments when discussing safeguards against denial of service attacks.
To be in compliance with the Collector's security best practices the chart has been updated to use the Collector's pod IP in place of `0.0.0.0`.

The chart will continue to allow complete configuration of the Collector via the `config` field in the values.yaml.  If pod IP does not suite your needs you can use `config` to set something different.

See [Security Best Practices docummentation](https://github.com/open-telemetry/opentelemetry-collector/blob/main/docs/security-best-practices.md#safeguards-against-denial-of-service-attacks) for more details.

The new default of binding to the pod IP, rather than `0.0.0.0`, will cause `kubectl port-forward` to fail. If port-forwarding is desired, the following `value.yaml` snippet will allow the Collector bind to `127.0.0.1` inside the pod, in addition to the pod's IP:

```yaml
config:
  receivers:
    jaeger/local:
      protocols:
        grpc:
          endpoint: 127.0.0.1:14250
        thrift_compact:
          endpoint: 127.0.0.1:6831
        thrift_http:
          endpoint: 127.0.0.1:14268
    otlp/local:
      protocols:
        grpc:
          endpoint: 127.0.0.1:4317
        http:
          endpoint: 127.0.0.1:4318
    zipkin/local:
      endpoint: 127.0.0.1:9411
  service:
    pipelines:
      traces:
        receivers:
        - otlp
        - otlp/local
        - jaeger
        - jaeger/local
        - zipkin
        - zipkin/local
```

## 0.40.7 to 0.41.0

[Require Kubernetes version 1.23 or later](https://github.com/open-telemetry/opentelemetry-helm-charts/pull/541)

If you enable use of a _HorizontalPodAutoscaler_ for the collector when running in the "deployment" mode by way of `.Values.autoscaling.enabled`, the manifest now uses the "autoscaling/v2" API group version, which [is available only as recently as Kubernetes version 1.23](https://kubernetes.io/blog/2021/12/07/kubernetes-1-23-release-announcement/#horizontalpodautoscaler-v2-graduates-to-ga). As [all previous versions of this API group are deprecated and removed as of Kubernetes version 1.26](https://kubernetes.io/docs/reference/using-api/deprecation-guide/#horizontalpodautoscaler-v126), we don't offer support for Kubernetes versions older than 1.23.

## 0.34.0 to 0.34.0

[config supports templating](TBD)

The chart now supports templating in `.Values.config`.  If you are currently using any `{{ }}` syntax in `.Values.yaml` it will now be rendered.  To escape existing instances of `{{ }}`, use ``` {{` <original content> `}} ```.  For example, `{{ REDACTED_EMAIL }}` becomes ``` {{` {{ REDACTED_EMAIL }} `}} ```.

## 0.28.0 to 0.29.0

[Reduce requested resources](https://github.com/open-telemetry/opentelemetry-helm-charts/pull/273)

Resource `limits` have been reduced. Upgrades/installs of chart 0.29.0 will now use fewer resources. In order to set the resources back to what they were, you will need to override the `resources` section in the `values.yaml`.

*Example*:

```yaml
resources:
  limits:
    cpu: 1
    memory: 2Gi
```

## 0.23.1 to 0.24.0

[Remove containerLogs in favor of presets.logsCollection]()

The ability to enable logs collection from the collector has been moved from `containerLogs.enabled` to `presets.logsCollection.enabled`. If you are currently using `containerLogs.enabled`, you should instead use the preset:

```yaml
presets:
  logsCollection:
    enabled: true
```

If you are using `containerLogs.enabled` and also enabling collection of the collector logs you can use `includeCollectorLogs`

```yaml
presets:
  logsCollection:
    enabled: true
    includeCollectorLogs: true
```

You no longer need to update `config.service.pipelines.logs` to include the filelog receiver yourself as the preset will automatically update the logs pipeline to include the filelog receiver.

The filelog's preset configuration can modified by `config.receivers`, but preset configuration cannot be removed.  If you need to remove any filelog receiver configuration generated by the preset you should not use the preset.  Instead, configure the filelog receiver manually in `config.receivers` and set any other necessary fields in the values.yaml to modify k8s as needed.

See the [daemonset-collector-logs example](https://github.com/open-telemetry/opentelemetry-helm-charts/tree/main/charts/opentelemetry-collector/examples/daemonset-collector-logs) to see an example of the preset in action.

## 0.18.0 to 0.19.0

[Remove agentCollector and standaloneCollector settings](https://github.com/open-telemetry/opentelemetry-helm-charts/pull/216)

The `agentCollector` and `standaloneCollector` config sections have been removed.  Upgrades/installs of chart 0.19.0 will fail if `agentCollector` or `standaloneCollector` are in the values.yaml.  See the [Migrate to mode](#migrate-to-mode) steps for instructions on how to replace `agentCollector` and `standaloneCollector` with `mode`.

## 0.13.0 to 0.14.0

[Remove two-deployment mode](https://github.com/open-telemetry/opentelemetry-helm-charts/pull/159)

The ability to install both the agent and standalone collectors simultaneous with the chart has been removed.  Installs/upgrades where both  `.Values.agentCollector.enabled` and `.Values.standloneCollector.enables` are true will fail.  `agentCollector` and `standloneCollector` have also be deprecated, but backward compatibility has been maintained.

### To run both a deployment and daemonset

Install a deployment version of the collector. This is done by setting `.Values.mode` to `deployment`

```yaml
mode: deployment
```

Next, install an daemonset version of the collector that is configured to send traffic to the previously installed deployment.  This is done by setting `.Values.mode` to `daemonset` and updating `.Values.config` so that data is exported to the deployment.

```yaml
mode: daemonset

config:
  exporters:
    otlp:
      endpoint: example-opentelemetry-collector:4317
      tls:
        insecure: true
  service:
    pipelines:
      logs:
        exporters:
         - otlp
         - logging
      metrics:
        exporters:
         - otlp
         - logging
      traces:
        exporters:
         - otlp
         - logging
```

See the [daemonset-and-deployment](examples/daemonset-and-deployment) example to see the rendered config.

### Migrate to `mode`:

The `agentCollector` and `standaloneCollector` sections in values.yaml have been deprecated. Instead there is a new field, `mode`, that determines if the collector is being installed as a daemonset or deployment.

```yaml
# Valid values are "daemonset" and "deployment".
# If set, agentCollector and standaloneCollector are ignored.
mode: <daemonset|deployment>
```

The following fields have also been added to the root-level to replace the depracated `agentCollector` and `standaloneCollector` settings.

```yaml
containerLogs:
  enabled: false

resources:
  limits:
    cpu: 1
    memory: 2Gi

podAnnotations: {}

podLabels: {}

# Host networking requested for this pod. Use the host's network namespace.
hostNetwork: false

# only used with deployment mode
replicaCount: 1

annotations: {}
```

When using `mode`, these settings should be used instead of their counterparts in `agentCollector` and `standaloneCollector`.

Set `mode` to `daemonset` if `agentCollector` was being used.  Move all `agentCollector` settings to the corresponding root-level setting.  If `agentCollector.configOverride` was being used, merge the settings with `.Values.config`.

Example agentCollector values.yaml:

```yaml
agentCollector:
  resources:
    limits:
      cpu: 3
      memory: 6Gi
  configOverride:
    receivers:
      hostmetrics:
        scrapers:
          cpu:
          disk:
          filesystem:
    service:
      pipelines:
        metrics:
          receivers: [otlp, prometheus, hostmetrics]
```

Example mode values.yaml:

```yaml
mode: daemonset

resources:
  limits:
    cpu: 3
    memory: 6Gi

config:
  receivers:
    hostmetrics:
      scrapers:
        cpu:
        disk:
        filesystem:
  service:
    pipelines:
      metrics:
        receivers: [otlp, prometheus, hostmetrics]
```

Set `mode` to `deployment` if `standaloneCollector` was being used.  Move all `standaloneCollector` settings to the corresponding root-level setting.  If `standaloneCollector.configOverride` was being used, merge the settings with `.Values.config`.

Example standaloneCollector values.yaml:

```yaml
standaloneCollector:
  enabled: true
  replicaCount: 2
  configOverride:
    receivers:
      podman_stats:
        endpoint: unix://run/podman/podman.sock
        timeout: 10s
        collection_interval: 10s
    service:
      pipelines:
        metrics:
          receivers: [otlp, prometheus, podman_stats]
```

Example mode values.yaml:

```yaml
mode: deployment

replicaCount: 2

config:
  receivers:
    receivers:
      podman_stats:
        endpoint: unix://run/podman/podman.sock
        timeout: 10s
        collection_interval: 10s
  service:
    pipelines:
      metrics:
        receivers: [otlp, prometheus, podman_stats]
```

Default configuration in `.Values.config` can now be removed with `null`.  When changing a pipeline, you must explicitly list all the components that are in the pipeline, including any default components.

*Example*: Disable metrics and logging pipelines and non-otlp receivers:

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
