# OpenSearch OTEL Demo with kubernetes
This short tutorial explains how to generate the k8s templates for the kubernetes based deployment of the OpenSearch demo
Use [Kompose](https://github.com/kubernetes/kompose) to convert fron Docker Compose to container orchestrators such as Kubernetes.

### Using Kompose command
Since the docker-compose is using an `.env` file - the next command will transform the templated docker-compose into a resolved one
Once its resolved the `kompose` command can convert it into the list of k8s specification files

`docker-compose config > docker-compose-resolved.yaml && kompose convert -f docker-compose-resolved.yaml`

Once all the files are created, you can use `kubectl apply -f /path/to/your/yaml/files/` to apply them to your local / remote k8s env. 

### Using `opentelemetry-demo.yaml` file
Another option would be just applying the supplied `opentelemetry-demo.yaml` which represents the OpenSearch modified version of the original k8s otel-demo yaml file.

- First create the namespace: `kubectl create namespace otel-demo`
- Next apply the k8s file using this specific namespace: `kubectl apply -f opentelemetry-demo.yaml -n otel-demo
  `

