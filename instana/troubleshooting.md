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

## No OpenTelemetry traces are received via the agent

- Make sure the agent configuration includes correct settings to enable OpenTelemetry for both gRPC and HTTP enpoints. The reference configuration is [instana/agent/configuration.yaml](../instana/agent/configuration.yaml)
- Double check the Kubernetes service for Instana agent and the OTLP endpoint environment variables in `.env` or in the Helm values file.
