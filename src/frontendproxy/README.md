# Frontend Proxy

The frontend proxy is Envoy, configured to route traffic to public-facing
services including the frontend, Grafana, Jaeger, and the Feature Flag service.

## Modifying the Envoy configuration

The Envoy configuration is located at `envoy.tmpl.yaml`. This configuration file
can accept environment variables, which are then replaced at deploy time via the
Dockerfile and `envsubst`.
