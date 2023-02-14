# How to build and deploy the Instana demo

## Run the demo in Docker

Refer to the main demo [documentation](https://opentelemetry.io/docs/demo/docker-deployment/). This is basically:
```sh
git clone https://github.com/instana/opentelemetry-demo.git
cd opentelemetry-demo
docker compose build up --no-build -d
```

> **Note:**
> The `--no-build` flag is used to fetch released docker images instead of building from source. Removing the `--no-build` command line option will rebuild all images from source. The image repository is defined in [`.env`](../.env) file. See below for details on building the images.

> **Tip:**
> You can run the demo in the foreground  by omitting the `-d` parameter (`docker compose up`) to get the container logs dumped out to the terminal so you can check for any errors.

#### Deploy Instana agent
Create a new docker-compose environment file with your Instana backend connection settings. Use the template:
```sh
cd instana-agent
cp instana-agent.env.template .env
```

Run the agent (inside `instana-agent` directory):
```sh
docker compose up -d
```

## Deploy in Kubernetes

Create a namespace/project:
```sh
kubectl create namespace otel-demo

# or equivalently in OpenShift:
oc new-project otel-demo
```

In OpenShift, also make sure you have sufficient privileges to run the pods in the namespace (this step my be no longer necessary as the demo containers can now run as non-root):
```sh
oc adm policy -n otel-demo add-scc-to-user anyuid -z default
```

Deploy the Instana agent via Helm or using an operator: use a standard installation according to Instana documentation. Next, apply the demo-specific agent configuration as in `instana-agent/configuration-otel.yaml`

The demo assumes that an Instana [agent Kubernetes service](https://www.ibm.com/docs/en/instana-observability/current?topic=requirements-installing-host-agent-kubernetes#instana-agent-service) `instana-agent` is present in `instana-agent` namespace. The agent service, besides exposing the standard Instana agent API endpoint, also provides the common OTLP endpoint for both gRPC (port 4317) and HTTP (port 4318) protocols across all nodes. Be aware that at time of writing, the HTTP endpoint definition wasn't yet included in the public Instana agent Helm chart (and likely neither in the Operator). You can better create the service manually using the following manifest that is tested to work well with the demo.
```yaml
cat <<EOF | kubectl create -f-
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

We use custom values file with additional settings for the Instana agent to act as the default OTel traces and metrics receiver, to suppress native Instana tracing so it doesn't clash with the OTel instrumentation, and to enable Instana infrastructure monitoring including the databases.
```sh
cd instana
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm install my-otel-demo open-telemetry/opentelemetry-demo -f values-instana-agent.yaml
```

In OpenShift, you can create a route for the `frontendproxy` service for easy access to the demo frontpage and featureflags services instead of the `kubectl port-forward` way that Helm prompts you after installation.

## Build the demo images from source

To build your local Docker images from source, run
```sh
docker compose build
```

If you plan to push your built images to a remote container registry you should specify your registry domain in the `IMAGE_NAME` variable in [`.env`](../.env) file. 

To push the images to a remote container registry, login to the registry first (`docker login` or `oc registry login` for OpenShift's internal registry) and run:
```sh
make push
```

#### If you are behind an HTTP proxy
Configure the proxy settings for the Docker daemon systemd service according to the [guide](https://docs.docker.com/config/daemon/systemd/#httphttps-proxy).

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

Build the demo with `http_proxy` and `https_proxy` build arguments passed to `docker-compose`:
```sh
docker compose build \ 
    --build-arg 'https_proxy=http://192.168.31.253:3128' \
    --build-arg 'http_proxy=http://192.168.31.253:3128' 
```
