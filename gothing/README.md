
## Usage
- apply environment variables for keys
- update the otel-configmap yaml

```
# initial install command
helm install my-otel-demo -n otel-demo open-telemetry/opentelemetry-demo

# upgrade command to set vars
helm upgrade -f values.yaml my-otel-demo -n otel-demo open-telemetry/opentelemetry-demo

# configmap from here and write to file if necessary
k get configmap -n otel-demo my-otel-demo-otelcol -oyaml

# apply changes to configmap
k apply -f otel-configmap.yaml

# delete old pod to make it read the new config
k delete -n otel-demo $(k get po -A -l component=standalone-collector -o name)

# port-forward for Grafana and friends
# The following services are available at these paths once the proxy is exposed:
# Webstore             http://localhost:8080/
# Grafana              http://localhost:8080/grafana/
# Load Generator UI    http://localhost:8080/loadgen/
# Jaeger UI            http://localhost:8080/jaeger/ui/
kubectl --namespace otel-demo port-forward svc/my-otel-demo-frontendproxy 8080:8080



```

# configmap

Add exporter. It should be an environment variable, but I just hardcoded it to make it easy.

Connector
- The connector is required to do APM metrics 
    - [Send OTEL to Datadog](https://docs.datadoghq.com/opentelemetry/guide/migration/)
- Export traces to the connector. Import the traces to metrics.

Configuration
- [Getting Started](https://docs.datadoghq.com/getting_started/opentelemetry/)
- [Adding K8s Metrics](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/exporter/datadogexporter/examples/collector.yaml)

# repo settings
I cloned it from the otel repo and made changes.
[StackOverflow about how to fork after clone](https://stackoverflow.com/questions/33817118/github-how-to-fork-after-cloning)

upstream: https://github.com/open-telemetry/opentelemetry-demo.git
origin: https://github.com/dongothing-dd/opentelemetry-demo.git
