# Demo customizations

## Link calls from FeatureFlag to Postgres database
**Problem:** FeatureFlag service calls to downstream PostgreSQL database aren't linked.  
**Reason:** The reason for the missing downstream database link is that the current v1.0 release of Erlang/Elix [OpentelemetryEcto instrumentation library](https://github.com/open-telemetry/opentelemetry-erlang-contrib/tree/main/instrumentation/opentelemetry_ecto) doesn't yet add the OTel peer attributes `net.peer.host` and `net.peer.port`. These standardized attributes are used by Instana to correlate downstream services.  
**Solution:** Although the instrumentation library provides other attributes with the downstream link details, it isn't possible to use plain OTel attributes for creating custom service mapping via [manual service configuration](https://www.ibm.com/docs/en/instana-observability/current?topic=applications-services#link-calls-to-an-existing-database-or-messaging-service-that-is-created-from-a-monitored-infrastructure-entity). Therefore, in order to inject the required attributes into the generated spans it was necessary to modify the OpentelemetryEcto library source and use the custom-built library in place of the default distribution package.

The [patched](https://github.com/styblope/opentelemetry_ecto/commit/0bc71d465621e6f76d71bc8d6d336011661eb754) OpenTelemetryEcto library is available at https://github.com/styblope/opentelemetry_ecto. The rest of the solution involved changing the FeatureFlag service Elixir code dependencies and building a new custom image.

## Adding W3C context propagation to Envoy the enable cross-tracer trace continuity
To demonstrate the context propagation across Instana and OTel tracing implementations, we chose to instrument the `frontendproxy` service with the Instana native tracer. The Instana sensor supports W3C propagation headers, which is the default propagation header format used by OpenTelemetry. We use a custom build of the Instana envoy sensor which supports W3C context propagation (public release of the W3C enabled sensor is due soon).
