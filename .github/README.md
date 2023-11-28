<!-- markdownlint-disable-next-line -->
# <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" alt="OTel logo" width="32"> :heavy_plus_sign: <img src="https://images.contentstack.io/v3/assets/bltefdd0b53724fa2ce/blt601c406b0b5af740/620577381692951393fdf8d6/elastic-logo-cluster.svg" alt="OTel logo" width="32"> OpenTelemetry Demo with Elastic Observability

The following guide describes how to setup the OpenTelemetry demo with Elastic Observability using [Docker compose](#docker-compose) or [Kubernetes](#kubernetes).

## Docker compose

1. Start a free trial on [Elastic Cloud](https://cloud.elastic.co/) and copy the `endpoint` and `secretToken` from the Elastic APM setup instructions in your Kibana.
1. Open the file `src/otelcollector/otelcol-config-extras.yml` in an editor and replace the following two placeholders:
   - `YOUR_APM_ENDPOINT_WITHOUT_HTTPS_PREFIX`: your Elastic APM endpoint (*without* `https://` prefix) that *must* also include the port (example: `1234567.apm.us-west2.gcp.elastic-cloud.com:443`).
   - `YOUR_APM_SECRET_TOKEN`: your Elastic APM secret token.
1. Start the demo with the following command from the repository's root directory:
   ```
   docker-compose up -d
   ```

## Kubernetes
### Prerequisites:
- Create a Kubernetes cluster. There are no specific requirements, so you can create a local one, or use a managed Kubernetes cluster, such as [GKE](https://cloud.google.com/kubernetes-engine), [EKS](https://aws.amazon.com/eks/), or [AKS](https://azure.microsoft.com/en-us/products/kubernetes-service).
- Set up [kubectl](https://kubernetes.io/docs/reference/kubectl/).
- Set up [Helm](https://helm.sh/).

### Start the Demo
1. Setup Elastic Observability on Elastic Cloud.
1. Create a secret in Kubernetes with the following command.
   ```
   kubectl create secret generic elastic-secret \
     --from-literal=elastic_apm_endpoint='YOUR_APM_ENDPOINT_WITHOUT_HTTPS_PREFIX' \
     --from-literal=elastic_apm_secret_token='YOUR_APM_SECRET_TOKEN'
   ```
   Don't forget to replace
   - `YOUR_APM_ENDPOINT_WITHOUT_HTTPS_PREFIX`: your Elastic APM endpoint (*without* `https://` prefix) that *must* also include the port (example: `1234567.apm.us-west2.gcp.elastic-cloud.com:443`).
   - `YOUR_APM_SECRET_TOKEN`: your Elastic APM secret token
1. Execute the following commands to deploy the OpenTelemetry demo to your Kubernetes cluster:
   ```
   # switch to the kubernetes/elastic-helm directory
   cd kubernetes/elastic-helm

   # !(when running it for the first time) add the open-telemetry Helm repostiroy
   helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts

   # !(when an older helm open-telemetry repo exists) update the open-telemetry helm repo
   helm repo update open-telemetry

   # deploy the demo through helm install
   helm install -f values.yaml my-otel-demo open-telemetry/opentelemetry-demo
   ```

#### Kubernetes monitoring

This demo already enables cluster level metrics collection with `clusterMetrics` and
Kubernetes events collection with `kubernetesEvents`.

In order to add Node level metrics collection and autodiscovery for Redis Pods
we can run an additional Otel collector Daemonset with the following:

`helm install daemonset open-telemetry/opentelemetry-collector --values daemonset.yaml`

## Explore and analyze the data With Elastic

### Service map
![Service map](service-map.png "Service map")

### Traces
![Traces](trace.png "Traces")

### Correlation
![Correlation](correlation.png "Correlation")

### Logs
![Logs](logs.png "Logs")
