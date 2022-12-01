# Shipping Service

This service is responsible for providing shipping information including pricing
and tracking information, when requested from Checkout Service.

Shipping service is built primarily with Tonic, Reqwest, and OpenTelemetry
Libraries/Components. Other sub-dependencies are included in `Cargo.toml`.

Depending on your framework and runtime, you may consider consulting
[rust docs](https://opentelemetry.io/docs/instrumentation/rust/) to supplement.
You'll find examples of async and sync spans in quote requests and tracking ID's
respectively.

The `build.rs` supports development outside docker, given a rust installation.
Otherwise, consider building with `docker compose` to edit / assess changes as needed.

[Shipping service source](../../src/shippingservice/)

## Traces

### Initializing Tracing

The OpenTelemetry SDK is initialized from `main`.

```rust
fn init_tracer() -> Result<sdktrace::Tracer, TraceError> {
    global::set_text_map_propagator(TraceContextPropagator::new());
    let os_resource = OsResourceDetector.detect(Duration::from_secs(0));
    let process_resource = ProcessResourceDetector.detect(Duration::from_secs(0));
    let sdk_resource = SdkProvidedResourceDetector.detect(Duration::from_secs(0));
    let env_resource = EnvResourceDetector::new().detect(Duration::from_secs(0));
    opentelemetry_otlp::new_pipeline()
        .tracing()
        .with_exporter(
            opentelemetry_otlp::new_exporter()
                .tonic()
                .with_endpoint(format!(
                    "{}{}",
                    env::var("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
                        .unwrap_or_else(|_| "http://otelcol:4317".to_string()),
                    "/v1/traces"
                )), // TODO: assume this ^ is true from config when opentelemetry crate > v0.17.0
                    // https://github.com/open-telemetry/opentelemetry-rust/pull/806 includes the environment variable.
        )
        .with_trace_config(
            sdktrace::config()
                .with_resource(os_resource.merge(&process_resource).merge(&sdk_resource).merge(&env_resource)),
        )
        .install_batch(opentelemetry::runtime::Tokio)
}
```

Spans and other metrics are created in this example throughout `tokio` async
runtimes found within [`tonic` server
functions](https://github.com/hyperium/tonic/blob/master/examples/helloworld-tutorial.md#writing-our-server).
Be mindful of async runtime, [context
guards](https://docs.rs/opentelemetry/latest/opentelemetry/struct.ContextGuard.html),
and inability to move and clone `spans` when replicating from these samples.

### Adding gRPC instrumentation

This service receives gRPC requests, which are instrumented in the middleware.

The root span is started and passed down as reference in the same thread
to another closure where we call `quoteservice`.

```rust
    let tracer = global::tracer("shippingservice");
    let mut span = tracer.span_builder("hipstershop.ShippingService/GetQuote").with_kind(SpanKind::Server).start_with_context(&tracer, &parent_cx);
    span.set_attribute(semcov::trace::RPC_SYSTEM.string(RPC_SYSTEM_GRPC));

    span.add_event("Processing get quote request".to_string(), vec![]);

    let cx = Context::current_with_span(span);
    let q = match create_quote_from_count(itemct)
        .with_context(cx.clone())
        .await
//-> create_quote_from_count()...
    let f = match request_quote(count).await {
        Ok(float) => float,
        Err(err) => {
            let msg = format!("{}", err);
            return Err(tonic::Status::unknown(msg));
        }
    };

    Ok(get_active_span(|span| {
        let q = create_quote_from_float(f);
        span.add_event(
            "Received Quote".to_string(),
            vec![KeyValue::new("app.shipping.cost.total", format!("{}", q))],
        );
        span.set_attribute(KeyValue::new("app.shipping.items.count", count as i64));
        span.set_attribute(KeyValue::new("app.shipping.cost.total", format!("{}", q)));
        q
    }))
//<- create_quote_from_count()...
    cx.span().set_attribute(semcov::trace::RPC_GRPC_STATUS_CODE.i64(RPC_GRPC_STATUS_CODE_OK));
```

Note that we create a context around the root span and send a clone to the
async function create_quote_from_count(). After create_quote_from_count()
completes, we can add additional attributes to the root span as appropriate.

You may also notice the `attributes` set on the span in this example, and
`events` propogated similarly. With any valid `span` pointer (attached to
context) the [OpenTelemetry API](https://docs.rs/opentelemetry/0.17.0/opentelemetry/trace/struct.SpanRef.html)
will work.

### Adding HTTP instrumentation

A child *client* span is also produced for the outoing HTTP call to
`quoteservice` via the `reqwest` client. This span pairs up with the
corresponding `quoteservice` *server* span. The tracing instrumentation is
implemented in the client middleware making use of the available
`reqwest-middleware`, `reqwest-tracing` and `tracing-opentelementry` libraries:

```rust
    let reqwest_client = reqwest::Client::new();
    let client = ClientBuilder::new(reqwest_client)
        .with(TracingMiddleware::<SpanBackendWithUrl>::new())
        .build();
```

### Add span attributes

Provided you are on the same thread, or in a context passed from a
span-owning thread, or a `ContextGuard` is in scope, you can get
an active span with `get_active_span`. You can find examples of all of these
in the demo, with context available in `shipping_service` for sync/async runtime.
You should consult `quote.rs` and/or the example above to see
context-passed-to-async runtime.

See below for a snippet from `shiporder` that holds context and a span in scope.
This is appropriate in our case of a sync runtime.

```rust
    let parent_cx =
    global::get_text_map_propagator(|prop| prop.extract(&MetadataMap(request.metadata())));
    // in this case, generating a tracking ID is trivial
    // we'll create a span and associated events all in this function.
    let tracer = global::tracer("shippingservice");
    let mut span = tracer
        .span_builder("hipstershop.ShippingService/ShipOrder").with_kind(SpanKind::Server).start_with_context(&tracer, &parent_cx);
```

You must add attributes to a span in context with `set_attribute`, followed by a
`KeyValue` object, containing a key, and value.

```rust
    let tid = create_tracking_id();
    span.set_attribute(KeyValue::new("app.shipping.tracking.id", tid.clone()));
    info!("Tracking ID Created: {}", tid);
```

### Add span events

Adding span events is accomplished using `add_event` on the span object. Both
server routes, for `ShipOrderRequest` (sync) and `GetQuoteRequest` (async),
have events on spans. Attributes are not included here, but are [simple to include](https://docs.rs/opentelemetry/latest/opentelemetry/trace/trait.Span.html#method.add_event).

Adding a span event:

```rust
    let tid = create_tracking_id();
    span.set_attribute(KeyValue::new("app.shipping.tracking.id", tid.clone()));
    info!("Tracking ID Created: {}", tid);
```

## Metrics

TBD

## Logs

TBD
