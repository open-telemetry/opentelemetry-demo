# Product Catalog Service

This service is responsible to return information about products. The service
can be used to get all products, search for specific products, or return details
about any single product.

[Product Catalog service source](../../src/productcatalogservice/)

## Traces

### Initializing Tracing

The OpenTelemetry SDK is initialized from `main` using the `initTracerProvider`
function.

```go
func initTracerProvider() *sdktrace.TracerProvider {
    ctx := context.Background()

    exporter, err := otlptracegrpc.New(ctx)
    if err != nil {
        log.Fatalf("OTLP Trace gRPC Creation: %v", err)
    }
    tp := sdktrace.NewTracerProvider(sdktrace.WithBatcher(exporter))
    otel.SetTracerProvider(tp)
    otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(propagation.TraceContext{}, propagation.Baggage{}))
    return tp
}
```

You should call `TracerProvider.Shutdown()` when your service is shutdown to
ensure all spans are exported. This service makes that call as part of a
deferred function in main

```go
    tp := InitTracerProvider()
    defer func() {
        if err := tp.Shutdown(context.Background()); err != nil {
            log.Fatalf("Tracer Provider Shutdown: %v", err)
        }
    }()
```

### Adding gRPC auto-instrumentation

This service receives gRPC requests, which are instrumented in the main function
as part of the gRPC server creation.

```go
    srv := grpc.NewServer(
        grpc.UnaryInterceptor(otelgrpc.UnaryServerInterceptor()),
        grpc.StreamInterceptor(otelgrpc.StreamServerInterceptor()),
    )
```

This service will issue outgoing gRPC calls, which are all instrumented by
wrapping the gRPC client with instrumentation.

```go
func createClient(ctx context.Context, svcAddr string) (*grpc.ClientConn, error) {
    return grpc.DialContext(ctx, svcAddr,
        grpc.WithTransportCredentials(insecure.NewCredentials()),
        grpc.WithUnaryInterceptor(otelgrpc.UnaryClientInterceptor()),
        grpc.WithStreamInterceptor(otelgrpc.StreamClientInterceptor()),
    )
}
```

### Add attributes to auto-instrumented spans

Within the execution of auto-instrumented code you can get current span from
context.

```go
    span := trace.SpanFromContext(ctx)
```

Adding attributes to a span is accomplished using `SetAttributes` on the span
object. In the `GetProduct` function an attribute for the product id is added
to the span.

```go
    span.SetAttributes(
        attribute.String("app.product.id", req.Id),
    )
```

### Setting span status

This service can catch and handle an error condition based on a feature flag.
In an error condition, the span status is set accordingly using `SetStatus` on
the span object. You can see this in the `GetProduct` function.

```go
    msg := fmt.Sprintf("Error: ProductCatalogService Fail Feature Flag Enabled")
    span.SetStatus(otelcodes.Error, msg)
```

### Add span events

Adding span events is accomplished using `AddEvent` on the span object. In the
`GetProduct` function a span event is added when an error condition is handled,
or when a product is successfully found.

```go
    span.AddEvent(msg)
```

## Metrics

### Initializing Metrics

The OpenTelemetry SDK is initialized from `main` using the `initMeterProvider`
function.

```go
func initMeterProvider() *sdkmetric.MeterProvider {
    ctx := context.Background()

    exporter, err := otlpmetricgrpc.New(ctx)
    if err != nil {
        log.Fatalf("new otlp metric grpc exporter failed: %v", err)
    }

    mp := sdkmetric.NewMeterProvider(sdkmetric.WithReader(sdkmetric.NewPeriodicReader(exporter)))
    global.SetMeterProvider(mp)
    return mp
}
```

You should call `initMeterProvider.Shutdown()` when your service is shutdown to
ensure all records are exported. This service makes that call as part of a
deferred function in main.

```go
    mp := initMeterProvider()
    defer func() {
        if err := mp.Shutdown(context.Background()); err != nil {
            log.Fatalf("Error shutting down meter provider: %v", err)
        }
    }()
```

### Adding golang runtime auto-instrumentation

Golang runtime is instrumented in the main function

```go
    err := runtime.Start(runtime.WithMinimumReadMemStatsInterval(time.Second))
    if err != nil {
        log.Fatal(err)
    }
```

## Logs

TBD
