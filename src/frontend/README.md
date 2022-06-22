# Frontend service

The **frontend** service is responsible for rendering the UI for the store's website.
It serves as the main entry point for the application routing requests to their
appropriate backend services.
The application uses Server Side Rendering (SSR) to generate HTML consumed by
the clients, which could be web browsers, web crawlers, mobile clients or something
else.

## OpenTelemetry features

### Emoji Legend

- Completed: :100:
- Not Present (Yet): :red_circle:

### Traces

- [Instrumentation
  Libraries](https://opentelemetry.io/docs/concepts/instrumenting-library/):
  :100:
- [Manual Span
  Creation](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/glossary.md#manual-instrumentation):
  :red_circle:
- [Span Data
  Enrichment](https://opentelemetry.io/docs/instrumentation/net/manual/#add-tags-to-an-activity):
  :100:
- Interprocess Context Propagation: :100:
- [Intra-service Context
  Propagation](https://opentelemetry.io/docs/instrumentation/java/manual/#context-propagation):
  :red_circle:
- [Trace
  Links](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/overview.md#links-between-spans):
  :red_circle:
- [Baggage](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/baggage/api.md#overview):
  :red_circle:

### Metrics

- [Instrumentation
  Libraries](https://opentelemetry.io/docs/concepts/instrumenting-library/):
  :red_circle:
- [Manual Metric
  Creation](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/glossary.md#manual-instrumentation):
  :red_circle:
- [Collector Agent Metric
  Transformation](https://opentelemetry.io/docs/collector/deployment/#agent)::red_circle:
- [Push
  Metrics](https://opentelemetry.io/docs/reference/specification/metrics/sdk/#push-metric-exporter):
  :red_circle:
- [SLO Metrics](https://github.com/openslo/openslo#slo): :red_circle:
- [Multiple Manual Metric
  Instruments](https://opentelemetry.io/docs/reference/specification/metrics/api/#synchronous-and-asynchronous-instruments):
  :red_circle:

## OpenTelemetry instrumentation

### Initialization

The OpenTelemetry SDK is initialized in `main` using the `InitTraceProvider` function.

```go
func InitTracerProvider() *sdktrace.TracerProvider {
    ctx := context.Background()

    exporter, err := otlptracegrpc.New(ctx)
    if err != nil {
        log.Fatal(err)
    }
    tp := sdktrace.NewTracerProvider(
        sdktrace.WithSampler(sdktrace.AlwaysSample()),
        sdktrace.WithBatcher(exporter),
    )
    otel.SetTracerProvider(tp)
    otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(propagation.TraceContext{}, propagation.Baggage{}))
    return tp
}
```

Services should call `TraceProvider.Shutdown()` when the service is shutdown to
ensure all spans are exported.
This service makes that call as part of a deferred function in `main`.

```go
    // Initialize OpenTelemetry Tracing
    tp := InitTracerProvider()
    defer func() {
        if err := tp.Shutdown(context.Background()); err != nil {
            log.Printf("Error shutting down tracer provider: %v", err)
        }
    }()
```

### HTTP instrumentation

This service receives HTTP requests, controlled by the gorilla/mux Router.
The following routes are defined by the frontend:

| Path              | Method | Use                               |
|-------------------|--------|-----------------------------------|
| `/`               | GET    | Main index page                   |
| `/cart`           | GET    | View Cart                         |
| `/cart`           | POST   | Add to Cart                       |
| `/cart/checkout`  | POST   | Place Order                       |
| `/cart/empty`     | POST   | Empty Cart                        |
| `/logout`         | GET    | Logout                            |
| `/product/{id}`   | GET    | View Product                      |
| `/setCurrency`    | POST   | Set Currency                      |
| `/static/`        | *      | Static resources                  |
| `/robots.txt`     | *      | Search engine response (disallow) |
| `/_healthz`       | *      | Health check (ok)                 |

These requests are instrumented in the main function as part of the router's definition.

```go
    // Add OpenTelemetry instrumentation to incoming HTTP requests controlled by the gorilla/mux Router.
    r.Use(otelmux.Middleware("server"))
```

### gRPC instrumentation

This service will issue several outgoing gRPC calls, which have instrumentation
hooks added in the `mustConnGRPC` function.

```go
func mustConnGRPC(ctx context.Context, conn **grpc.ClientConn, addr string) {
    // Add OpenTelemetry instrumentation to outgoing gRPC requests
    var err error
    ctx, cancel := context.WithTimeout(ctx, time.Second*3)
    defer cancel()
    *conn, err = grpc.DialContext(ctx, addr,
        grpc.WithTransportCredentials(insecure.NewCredentials()),
        grpc.WithUnaryInterceptor(otelgrpc.UnaryClientInterceptor()),
        grpc.WithStreamInterceptor(otelgrpc.StreamClientInterceptor()),
    )
    if err != nil {
        panic(errors.Wrapf(err, "grpc: failed to connect %s", addr))
    }
}
```

### Service specific instrumentation attributes

All requests incoming to the frontend service will receive the following attributes:

- `app.session.id`
- `app.request.id`
- `app.currency`
- `app.user.id` (when the user is present)

These attributes are added in the `instrumentHandler` function (defined in the
middleware.go file) which wraps all HTTP routes specified within the
gorilla/mux router.
Additional attributes are added within each handler's function as appropriate
(ie: `app.cart.size`, `app.cart.total.price`).

Adding attributes to existing auto-instrumented spans can be accomplished by
getting the current span from context, then adding attributes to it.

```go
    span := trace.SpanFromContext(r.Context())
    span.SetAttributes(
        attribute.Int(instr.AppPrefix+"cart.size", cartSize(cart)),
        attribute.Int(instr.AppPrefix+"cart.items.count", len(items)),
        attribute.Float64(instr.AppPrefix+"cart.shipping.cost", shippingCostFloat),
        attribute.Float64(instr.AppPrefix+"cart.total.price", totalPriceFloat),
    )
```

When an error is encountered, the current span's status code and error message
are set.

```go
    // set span status on error
    span := trace.SpanFromContext(r.Context())
    span.SetStatus(codes.Error, errMsg)
```
