# OpenTelemetry Demo Helm Chart

The helm chart installs [OpenTelemetry Demo](https://github.com/open-telemetry/opentelemetry-demo)
in kubernetes cluster.

## Prerequisites

- Kubernetes 1.24+
- Helm 3.14+

## Installing the Chart

Add OpenTelemetry Helm repository:

```console
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
```

To install the chart with the release name my-otel-demo, run the following command:

```console
helm install my-otel-demo open-telemetry/opentelemetry-demo
```

## Upgrading

See [UPGRADING.md](UPGRADING.md).

## OpenShift

Installing the chart on OpenShift requires the following additional steps:

1. Create a new project:

```console
oc new-project opentelemetry-demo
```

2. Create a new service account:

```console
oc create sa opentelemetry-demo
```

3. Add the service account to the `anyuid` SCC (may require cluster admin):

```console
oc adm policy add-scc-to-user anyuid -z opentelemetry-demo
```

4. Add `view` role to the service account to allow Prometheus seeing the services pods:

```console
oc adm policy add-role-to-user view -z opentelemetry-demo
```

5. Add `privileged` SCC to the service account to allow Grafana to run:

```console
oc adm policy add-scc-to-user privileged -z opentelemetry-demo
```

6. Install the chart with the following command:

```console
helm install my-otel-demo charts/opentelemetry-demo \
    --namespace opentelemetry-demo \
    --set serviceAccount.create=false \
    --set serviceAccount.name=opentelemetry-demo \
    --set prometheus.rbac.create=false \
    --set prometheus.serviceAccounts.server.create=false \
    --set prometheus.serviceAccounts.server.name=opentelemetry-demo \
    --set grafana.rbac.create=false \
    --set grafana.serviceAccount.create=false \
    --set grafana.serviceAccount.name=opentelemetry-demo
```

## Chart Parameters

Chart parameters are separated in 4 general sections:
* Default - Used to specify defaults applied to all demo components
* Components - Used to configure the individual components (microservices) for
the demo
* Observability - Used to enable/disable dependencies
* Sub-charts - Configuration for all sub-charts

### Default parameters (applied to all demo components)

| Property                               | Description                                                                               | Default                                              |
|----------------------------------------|-------------------------------------------------------------------------------------------|------------------------------------------------------|
| `default.env`                          | Environment variables added to all components                                             | Array of several OpenTelemetry environment variables |
| `default.envOverrides`                 | Used to override individual environment variables without re-specifying the entire array. | `[]`                                                 |
| `default.image.repository`             | Demo components image name                                                                | `otel/demo`                                          |
| `default.image.tag`                    | Demo components image tag (leave blank to use app version)                                | `nil`                                                |
| `default.image.pullPolicy`             | Demo components image pull policy                                                         | `IfNotPresent`                                       |
| `default.image.pullSecrets`            | Demo components image pull secrets                                                        | `[]`                                                 |
| `default.replicas`                     | Number of replicas for each component                                                     | `1`                                                  |
| `default.schedulingRules.nodeSelector` | Node labels for pod assignment                                                            | `{}`                                                 |
| `default.schedulingRules.affinity`     | Man of node/pod affinities                                                                | `{}`                                                 |
| `default.schedulingRules.tolerations`  | Tolerations for pod assignment                                                            | `[]`                                                 |
| `default.securityContext`              | Demo components container security context                                                | `{}`                                                 |
| `serviceAccount.annotations`           | Annotations for the serviceAccount                                                        | `{}`                                                 |
| `serviceAccount.create`                | Whether to create a serviceAccount or use an existing one                                 | `true`                                               |
| `serviceAccount.name`                  | The name of the ServiceAccount to use for demo components                                 | `""`                                                 |

### Component parameters

The OpenTelemetry demo contains several components (microservices). Each
component is configured with a common set of parameters. All components will
be defined within `components.[NAME]` where `[NAME]` is the name of the demo
component.

> **Note**
> The following parameters require a `components.[NAME].` prefix where `[NAME]`
> is the name of the demo component


| Parameter                              | Description                                                                                                | Default                                                       |
|----------------------------------------|------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------|
| `enabled`                              | Is this component enabled                                                                                  | `true`                                                        |
| `useDefault.env`                       | Use the default environment variables in this component                                                    | `true`                                                        |
| `imageOverride.repository`             | Name of image for this component                                                                           | Defaults to the overall default image repository              |
| `imageOverride.tag`                    | Tag of the image for this component                                                                        | Defaults to the overall default image tag                     |
| `imageOverride.pullPolicy`             | Image pull policy for this component                                                                       | `IfNotPresent`                                                |
| `imageOverride.pullSecrets`            | Image pull secrets for this component                                                                      | `[]`                                                          |
| `service.type`                         | Service type used for this component                                                                       | `ClusterIP`                                                   |
| `service.port`                         | Service port used for this component                                                                       | `nil`                                                         |
| `service.nodePort`                     | Service node port used for this component                                                                  | `nil`                                                         |
| `service.annotations`                  | Annotations to add to the component's service                                                              | `{}`                                                          |
| `ports`                                | Array of ports to open for deployment and service of this component                                        | `[]`                                                          |
| `env`                                  | Array of environment variables added to this component                                                     | Each component will have its own set of environment variables |
| `envOverrides`                         | Used to override individual environment variables without re-specifying the entire array                   | `[]`                                                          |
| `replicas`                             | Number of replicas for this component                                                                      | `1` for kafka, and redis ; `nil` otherwise       |
| `resources`                            | CPU/Memory resource requests/limits                                                                        | Each component will have a default memory limit set           |
| `schedulingRules.nodeSelector`         | Node labels for pod assignment                                                                             | `{}`                                                          |
| `schedulingRules.affinity`             | Man of node/pod affinities                                                                                 | `{}`                                                          |
| `schedulingRules.tolerations`          | Tolerations for pod assignment                                                                             | `[]`                                                          |
| `securityContext`                      | Container security context to define user ID (UID), group ID (GID) and other security policies             | `{}`                                                          |
| `podSecurityContext`                   | Pod security context to define user ID (UID), group ID (GID) and other security policies                   | `{}`                                                          |
| `podAnnotations`                       | Pod annotations for this component                                                                         | `{}`                                                          |
| `ingress.enabled`                      | Enable the creation of Ingress rules                                                                       | `false`                                                       |
| `ingress.annotations`                  | Annotations to add to the ingress rule                                                                     | `{}`                                                          |
| `ingress.ingressClassName`             | Ingress class to use. If not specified default Ingress class will be used.                                 | `nil`                                                         |
| `ingress.hosts`                        | Array of Hosts to use for the ingress rule.                                                                | `[]`                                                          |
| `ingress.hosts[].paths`                | Array of paths / routes to use for the ingress rule host.                                                  | `[]`                                                          |
| `ingress.hosts[].paths[].path`         | Actual path route to use                                                                                   | `nil`                                                         |
| `ingress.hosts[].paths[].pathType`     | Path type to use for the given path. Typically this is `Prefix`.                                           | `nil`                                                         |
| `ingress.hosts[].paths[].port`         | Port to use for the given path                                                                             | `nil`                                                         |
| `ingress.additionalIngresses`          | Array of additional ingress rules to add. This is handy if you need to differently annotated ingress rules | `[]`                                                          |
| `ingress.additionalIngresses[].name`   | Each additional ingress rule needs to have a unique name                                                   | `nil`                                                         |
| `command`                              | Command & arguments to pass to the container being spun up for this service                                | `[]`                                                          |
| `mountedConfigMaps[].name`             | Name of the Volume that will be used for the ConfigMap mount                                               | `nil`                                                         |
| `mountedConfigMaps[].mountPath`        | Path where the ConfigMap data will be mounted                                                              | `nil`                                                         |
| `mountedConfigMaps[].subPath`          | SubPath within the mountPath. Used to mount a single file into the path.                                   | `nil`                                                         |
| `mountedConfigMaps[].existingConfigMap` | Name of the existing ConfigMap to mount                                                                    | `nil`                                                         |
| `mountedConfigMaps[].data`             | Contents of a ConfigMap. Keys should be the names of the files to be mounted.                              | `{}`                                                          |
| `initContainers`                       | Array of init containers to add to the pod                                                                 | `[]`                                                          |
| `initContainers[].name`                | Name of the init container                                                                                 | `nil`                                                         |
| `initContainers[].image`               | Image to use for the init container                                                                        | `nil`                                                         |
| `initContainers[].command`             | Command to run for the init container                                                                      | `nil`                                                         |
| `sidecarContainers`                    | Array of sidecar containers to add to the pod                                                              | `[]`                                                          |
| `additionalVolumes`                    | Array of additional volumes to add to the pod                                                              | `[]`                                                          |

### Sub-charts

The OpenTelemetry Demo Helm chart depends on 5 sub-charts:
* OpenTelemetry Collector
* Jaeger
* Prometheus
* Grafana
* OpenSearch

Parameters for each sub-chart can be specified within that sub-chart's
respective top level. This chart will override some of the dependent sub-chart
parameters by default. The overriden parameters are specified below.

#### OpenTelemetry Collector

> **Note**
> The following parameters have a `opentelemetry-collector.` prefix.

| Parameter        | Description                                        | Default                                                  |
|------------------|----------------------------------------------------|----------------------------------------------------------|
| `enabled`        | Install the OpenTelemetry collector                | `true`                                                   |
| `nameOverride`   | Name that will be used by the sub-chart release    | `otel-collector`                                                |
| `mode`           | The Deployment or Daemonset mode                   | `deployment`                                             |
| `resources`      | CPU/Memory resource requests/limits                | 100Mi memory limit                                       |
| `service.type`   | Service Type to use                                | `ClusterIP`                                              |
| `ports`          | Ports to enabled for the collector pod and service | `metrics` is enabled and `prometheus` is defined/enabled |
| `podAnnotations` | Pod annotations                                    | Annotations leveraged by Prometheus scrape               |
| `config`         | OpenTelemetry Collector configuration              | Configuration required for demo                          |

#### Jaeger

> **Note**
> The following parameters have a `jaeger.` prefix.

| Parameter                      | Description                                        | Default                                                               |
|--------------------------------|----------------------------------------------------|-----------------------------------------------------------------------|
| `enabled`                      | Install the Jaeger sub-chart                       | `true`                                                                |
| `provisionDataStore.cassandra` | Provision a cassandra data store                   | `false` (required for AllInOne mode)                                  |
| `allInOne.enabled`             | Enable All in One In-Memory Configuration          | `true`                                                                |
| `allInOne.args`                | Command arguments to pass to All in One deployment | `["--memory.max-traces", "10000", "--query.base-path", "/jaeger/ui"]` |
| `allInOne.resources`           | CPU/Memory resource requests/limits for All in One | 275Mi memory limit                                                    |
| `storage.type`                 | Storage type to use                                | `none` (required for AllInOne mode)                                   |
| `agent.enabled`                | Enable Jaeger agent                                | `false` (required for AllInOne mode)                                  |
| `collector.enabled`            | Enable Jaeger Collector                            | `false` (required for AllInOne mode)                                  |
| `query.enabled`                | Enable Jaeger Query                                | `false` (required for AllInOne mode)                                  |

#### Prometheus

> **Note**
> The following parameters have a `prometheus.` prefix.

| Parameter                            | Description                                    | Default                                                   |
|--------------------------------------|------------------------------------------------|-----------------------------------------------------------|
| `enabled`                            | Install the Prometheus sub-chart               | `true`                                                    |
| `alertmanager.enabled`               | Install the alertmanager                       | `false`                                                   |
| `configmapReload.prometheus.enabled` | Install the configmap-reload container         | `false`                                                   |
| `kube-state-metrics.enabled`         | Install the kube-state-metrics sub-chart       | `false`                                                   |
| `prometheus-node-exporter.enabled`   | Install the Prometheus Node Exporter sub-chart | `false`                                                   |
| `prometheus-pushgateway.enabled`     | Install the Prometheus Push Gateway sub-chart  | `false`                                                   |
| `server.extraFlags`                  | Additional flags to add to Prometheus server   | `["enable-feature=exemplar-storage"]`                     |
| `server.persistentVolume.enabled`    | Enable persistent storage for Prometheus data  | `false`                                                   |
| `server.global.scrape_interval`      | How frequently to scrape targets by default    | `5s`                                                      |
| `server.global.scrap_timeout`        | How long until a scrape request times out      | `3s`                                                      |
| `server.global.evaluation_interval`  | How frequently to evaluate rules               | `30s`                                                     |
| `service.servicePort`                | Service port used                              | `9090`                                                    |
| `serverFiles.prometheus.yml`         | Prometheus configuration file                  | Scrape config to get metrics from OpenTelemetry collector |

#### Grafana

> **Note**
> The following parameters have a `grafana.` prefix.

| Parameter             | Description                                        | Default                                                              |
|-----------------------|----------------------------------------------------|----------------------------------------------------------------------|
| `enabled`             | Install the Grafana sub-chart                      | `true`                                                               |
| `grafana.ini`         | Grafana's primary configuration                    | Enables anonymous login, and proxy through the frontend-proxy service |
| `adminPassword`       | Password used by `admin` user                      | `admin`                                                              |
| `rbac.pspEnabled`     | Enable PodSecurityPolicy resources                 | `false`                                                              |
| `datasources`         | Configure grafana datasources (passed through tpl) | Prometheus and Jaeger data sources                                   |
| `dashboardProviders`  | Configure grafana dashboard providers              | Defines a `default` provider based on a file path                    |
| `dashboardConfigMaps` | ConfigMaps reference that contains dashboards      | Dashboard config map deployed with this Helm chart                   |

#### OpenSearch
> **Note**
> The following parameters have a `opensearch.` prefix.

| Parameter             | Description                                       | Default                                  |
|-----------------------|---------------------------------------------------|------------------------------------------|
| `enabled`             | Install the OpenSearch sub-chart                  | `true`                                   |
| `fullnameOverride`    | Name that will be used by the sub-chart release   | `otel-demo-opensearch`                   |
| `clusterName`         | Name of the OpenSearch cluster                    | `demo-cluster`                           |
| `nodeGroup`           | OpenSearch Node group configuration               | `otel-demo`                              |
| `singleNode`          | Deploy a single node OpenSearch cluster           | `true`                                   |
| `opensearchJavaOpts`  | Java options for OpenSearch JVM                   | `-Xms300m -Xmx300m`                      |
| `persistence.enabled` | Enable persistent storage for OpenSearch data     | `false`                                  |
| `extraEnvs`           | Additional environment variables for OpenSearch   | Disables demo config and security plugin |
