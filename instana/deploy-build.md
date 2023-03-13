# How to build and deploy the Instana demo

## Run the demo in Docker

Clone the repo:
```sh
git clone https://github.com/instana/opentelemetry-demo.git
cd opentelemetry-demo
```

#### Deploy Instana agent
Create a new docker-compose environment file with your Instana backend connection and EUM website monitoring settings. The configuration values are also re-used in building and running the demo containers. Use the template:
```sh
cd instana/agent
cp instana-agent.env.template .env
```

Run the agent (inside the `instana/agent` directory):
```sh
docker compose up -d
```

#### Launch the demo
Refer to the main demo [documentation](https://opentelemetry.io/docs/demo/docker-deployment/). This is basically:
```sh
docker compose up --no-build -d
```

> **Notes:**
> - The `--no-build` flag is used to fetch released docker images instead of building from source. Removing the `--no-build` command line option will rebuild all images from source. The image repository is defined in [`.env`](../.env) file. See below for details on building the images.
> - You can configure the pre-injected Instana EUM Javascript in Frontend service by setting and exporting `INSTANA_EUM_URL` and `INSTANA_EUM_KEY` environment varables in the shell before running the demo.

> **Tip:**
> You can run the demo in the foreground  by omitting the `-d` parameter (`docker compose up`) to get the container logs dumped out to the terminal so you can check for any errors.

## Deploy in Kubernetes

Create a namespace/project:
```sh
kubectl create namespace otel-demo

# or equivalently in OpenShift:
oc new-project otel-demo
```

In OpenShift, you must provide sufficient security privileges to allow the demo pods to rune in the namespace under the demo's service account (the service accounht name equals is the same as the Helm release name). 
```sh
oc get sa -n otel-demo
oc adm policy -n otel-demo add-scc-to-user anyuid -z my-otel-demo
```

Deploy the Instana agent via Helm or using an operator: use a standard installation according to Instana documentation. Apply the demo-specific agent configuration as in `instana-agent/configuration-otel.yaml`. These settings enable the OpenTelemetry ports, add specific service settings for infrastructure monitoring and suppression of native Instana tracing.

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

> **Note:**
> We use custom values file ([`values-instana-agent.yaml`](../instana/values-instana-agent.yaml)) with additional settings for the Instana agent to act as the default OTel traces and metrics receiver. There is no need to change the default values except when you want to use Instana website EUM; in this case edit the values file and fill-in the corresponding values for `INSTANA_EUM_URL` and `INSTANA_EUM_KEY` environment variables in the Frontend service component section (you could also add these variables later by editing the frontend service deployment)

```sh
cd instana
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm install my-otel-demo open-telemetry/opentelemetry-demo -f values-instana-agent.yaml
```

In OpenShift, you can create a route for the `frontendproxy` service for easy access to the demo frontpage and featureflags services instead of the `kubectl port-forward` way that Helm prompts you after installation.

## Build the demo images from source

Before building the project you need to export your Instana instance `INSTANA_AGENT_KEY` and `INSTANA_DOWNLOAD_KEY` values within the shell or, alternatively, if you have already configured your agent `.env` file run:
```sh
export $(cat ./instana/agent/.env | xargs)`
# don't mind the errors
```

Build the demo:
```sh
docker compose build
```

If you plan to push the built images to a remote container registry you should specify your registry domain in the `IMAGE_NAME` variable in [`.env`](../.env) file. 

To push the images to a remote registry, login to the registry first (`docker login` or `oc registry login` for OpenShift's internal registry) and run:
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
