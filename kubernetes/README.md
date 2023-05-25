# OpenSearch OTEL Demo with kubernetes
This short tutorial explains how to generate the k8s templates for the kubernetes based deployment of the OpenSearch demo

## Using helm charts
Another option is to use helm to introduce the [specific OpenSearch changes](https://opentelemetry.io/docs/demo/kubernetes-deployment/) to support O/S Observability in the original OTEL demo

#### Install OpenSearch helm:
```text
helm repo add opensearch https://opensearch-project.github.io/helm-charts/
helm repo update

```
Once the charts repository reference is added, you can run the following command to see the charts.

```text
helm search repo opensearch
```

#### Deploy charts with this command.
First create the namespace:
`kubectl create namespace otel-demo`

Next install the opensearch cluster & dashboards under that namespace
```text
helm install opensearch opensearch/opensearch -n otel-demo
helm install dashboards opensearch/opensearch-dashboards -n otel-demo

```

#### Install otel demo helm:
Install the [OTEL Demo](https://github.com/open-telemetry/opentelemetry-helm-charts/blob/main/charts/opentelemetry-demo/README.md)

Add OpenTelemetry Helm repository:

`helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts`

You can then run `helm search repo open-telemetry` to see the charts.

To install the chart with the release name my-otel-demo, run the following command:

`helm install otel-demo open-telemetry/opentelemetry-demo`

---

### Using Kompose command
Use [Kompose](https://github.com/kubernetes/kompose) to convert fron Docker Compose to container orchestrators such as Kubernetes.

Since the docker-compose is using an `.env` file - the next command will transform the templated docker-compose into a resolved one
Once its resolved the `kompose` command can convert it into the list of k8s specification files

`docker-compose config > docker-compose-resolved.yaml && kompose convert -f docker-compose-resolved.yaml`

Once all the files are created, you can use `kubectl apply -f /path/to/your/yaml/files/` to apply them to your local / remote k8s env. 

---

### Using `opentelemetry-demo.yaml` file
Another option would be just applying the supplied `opentelemetry-demo.yaml` which represents the OpenSearch modified version of the original k8s otel-demo yaml file.

- First create the namespace: `kubectl create namespace otel-demo`
- Next apply the k8s file using this specific namespace: `kubectl apply -f opentelemetry-demo.yaml -n otel-demo`
  
