# Upgrade guidelines

> [!NOTE]
> The OpenTelemetry Demo does not support being upgraded from one version to
> another. If you need to upgrade the chart, you must first delete the existing
> release and then install the new version.

## To 0.36

The Demo 2.0 release removed the `service` suffix from many components names,
and renamed some components based on a naming standard defined in
the [#1788](https://github.com/open-telemetry/opentelemetry-demo/issues/1788)
issue in the OpenTelemetry Demo repository. Any custom configuration for a Demo
component that was renamed will need to be updated to use the new name. The
following table shows the old and new names for each component:

| Old Name               | New Name        |
|------------------------|-----------------|
| accountingservice      | accounting      |
| adservice              | ad              |
| cartservice            | cart            |
| checkoutservice        | checkout        |
| currencyservice        | currency        |
| emailservice           | email           |
| flagd                  | flagd           |
| flagd-ui               | flagd-ui        |
| frauddetectionservice  | fraud-detection |
| frontend               | frontend        |
| frontendproxy          | frontend-proxy  |
| frontend-web           | frontend-web    |
| grafana                | grafana         |
| imageprovider          | image-provider  |
| jaeger                 | jaeger          |
| kafka                  | kafka           |
| loadgenerator          | load-generator  |
| opensearch             | opensearch      |
| otelcollector          | otel-collector  |
| paymentservice         | payment         |
| productcatalogservice  | product-catalog |
| prometheus             | prometheus      |
| quotesservice          | quote           |
| recommendationsservice | recommendation  |
| shippingservice        | shipping        |
| valkey-cart            | valkey-cart     |

## To 0.35

The Helm chart release name prefix has been removed from all resources. If you
have any custom configuration that depend on the release name, you will need to
update it accordingly.

## To 0.33

The Helm prerequisite version has been updated to Helm 3.14+. Please upgrade your
Helm client to the latest version.

## To 0.28

The `configuration` property for components has been removed in favor of the new `mountedConfigMaps` property.
This new property allows you to specify the contents of the configuration using the `data` sub-property. You will also
need to specify the `mountPath` to use, and give the configuration a name. The old `configuration` property used
`/etc/config` and `config` as values for these respectively. The following example shows how to migrate from the old
`configuration` property to the new `mountedConfigMaps` property:

```yaml
# Old configuration property
configuration:
  my-config.yaml: |
    # Contents of my-config.yaml

# New mountedConfigMaps property
mountedConfigMaps:
  - name: config
    mountPath: /etc/config
    data:
      my-config.yaml: |
        # Contents of my-config.yaml
```

## To 0.24

This release uses the [kubernetes attributes processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/processor/k8sattributesprocessor)
to add kubernetes metadata as resource attributes. If you override the processors array in your config, you will
need to add the k8s attributes processor manually to restore `service.instance.id`
resource attribute.

## To 0.23

The Prometheus sub-chart dependency made updates to pod labels. You may need to
use the `--force` option with your Helm upgrade command, or delete the release
and re-install it.

## To 0.22

This release moves to using the `connectors` functionality in the OpenTelemetry
Collector. The `spanmetrics` processor has been moved to use `connectors`
which results in an additional required exporter in the `traces` pipeline.
Existing releases that override `exporters` in the `traces` pipeline, will
need to add `spanmetrics` to the list of exporters before upgrading. The
OpenTelemetry Collector will fail to start otherwise.

## To 0.21

The deployment labelSelector `app.kubernetes.io/name` has been renamed to
individual workload naming. If you upgrade it from charts <= 0.20, you
will have to delete all existing opentelemetry-demo deployments before running
`helm upgrade` command.

## To 0.20

The `observability.<sub chart>.enabled` parameters have been moved to an
`enabled` parameter within the sub chart itself. If you had changes to these
parameters, you will need to update your changes to work with the new structure.

## To 0.18

The `serviceType` and `servicePort` parameters have been moved under a `service`
parameter with names of `type` and `port` respectively. If you had changes to
these parameters for any demo component, you will need to update your changes
to work with the new structure for the `service` parameter.

## To 0.13

Jaeger was moved to a Helm sub-chart instead of a local chart deployment. If you
had changes specified to the `observability.jaeger` parameter, those changes
will need to be re-implemented as sub-chart parameters under the top level
`jaeger` parameter instead.
