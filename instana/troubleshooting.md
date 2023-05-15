# Troubleshooting tips

## Kubernetes pods or containers are crashing
If some containers are crashing (CrashLoopBackOff) check the logs first to find any possible clues:
```sh
kubectl logs <pod_name>
```

Next, check the pod status:
```sh
kubectl describe <pod_name>
```

If the above commands aren't helpful to explain the pod/container crashes try to increase the container memory allocation limits, as this is one of the most common isues in some environments
```sh
kubectl edit deployment <deployment_name>
```

## Pods are in ImagePullBackOff
This might happen because you've reached your DockerHub pull rate limits. You can increase the limits by authenticating to Docker. Create a new secret in the demo namespace with your Docker credentials and attach the secret to the demo service account:
```sh
kubectl create secret docker-registry my-docker-hub --docker-username <username> --docker-password <password> --docker-server docker.io
kubectl patch serviceaccount my-otel-demo -p '{"imagePullSecrets": [{"name": "my-docker-hub"}]}'
```

## No OpenTelemetry traces are received via the agent

- Make sure the agent configuration includes correct settings to enable OpenTelemetry for both gRPC and HTTP enpoints. The reference configuration is [instana/agent/configuration.yaml](../instana/agent/configuration.yaml)
- Double check the Kubernetes service for Instana agent and the OTLP endpoint environment variables in `.env` or in the Helm values file.

## Why do I see "Unspecified" service in Instana dependency graph?
Some calls reported by OTel spans don't have a downstream counterpart or correlation hints to classify a service. This is also the case of calls originating at Instana sensors (used for infrastructure monitoring) reporting back to the Instana backend. We can effectively treat these calls as 'synthetic' and suppress the respective endpoints via Services -> Configure Services -> synthetic Endpoints -> "endpoint.name containts com.instana"

## Website tracing data is not visible in Instana even though I've properly set both INSTANA_EUM URL and INSTANA_EUM_KEY
Your browser may be blocking cross-site content. The resource at “https://instana_eum_url:446/eum/eum.min.js” that is requested during the webpage load was probably blocked by the browser's security policy. Disable the content blocking by adding a tracking exception for the Instana domain (see [here](https://developer.mozilla.org/en-US/docs/Web/Privacy/Firefox_tracking_protection) for Firefox)
