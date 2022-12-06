# Frontend Proxy(Envoy)

The frontend proxy is used as a reverse proxy for user-facing web
interfaces such as the frontend, Jaeger, Grafana, load generator,
and feature flag service.

## Enabling OpenTelemetry

**NOTE: Only non-synthetic requests will trigger the envoy tracing.**

In order to enable Envoy to produce spans whenever receiving a request,
the following configuration is required:

```yaml
static_resources:
  listeners:
    - address:
        socket_address:
          address: 0.0.0.0
          port_value: ${ENVOY_PORT}
      filter_chains:
        - filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                codec_type: AUTO
                stat_prefix: ingress_http
                tracing:
                  provider:
                    name: envoy.tracers.opentelemetry
                    typed_config:
                      "@type": type.googleapis.com/envoy.config.trace.v3.OpenTelemetryConfig
                      grpc_service:
                        envoy_grpc:
                          cluster_name: opentelemetry_collector
                        timeout: 0.250s
                      service_name: frontend-proxy

  clusters:
    - name: opentelemetry_collector
      type: STRICT_DNS
      lb_policy: ROUND_ROBIN
      typed_extension_protocol_options:
        envoy.extensions.upstreams.http.v3.HttpProtocolOptions:
          "@type": type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions
          explicit_http_config:
            http2_protocol_options: {}
      load_assignment:
        cluster_name: opentelemetry_collector
        endpoints:
          - lb_endpoints:
              - endpoint:
                  address:
                    socket_address:
                      address: ${OTEL_COLLECTOR_HOST}
                      port_value: ${OTEL_COLLECTOR_PORT}
```

Where `OTEL_COLLECTOR_HOST` and `OTEL_COLLECTOR_PORT` are passed via
environment variables.
