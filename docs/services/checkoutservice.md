# Checkout Service

This service is responsible to process a checkout order from the user. The
checkout service will call many other services in order to process an order.

[Checkout service source](../../src/checkoutservice/)

## Traces

### Initializing Tracing

The OpenTelemetry SDK is initialized from `main` using the `initTracerProvider`
function.

```go
func initTracerProvider() *sdktrace.TracerProvider {
    ctx := context.Background()

    exporter, err := otlptracegrpc.New(ctx)
    if err != nil {
        log.Fatal(err)
    }
    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exporter),
        sdktrace.WithResource(initResource()),
    )
    otel.SetTracerProvider(tp)
    otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(propagation.TraceContext{}, propagation.Baggage{}))
    return tp
}
```

You should call `TracerProvider.Shutdown()` when your service is shutdown to
ensure all spans are exported. This service makes that call as part of a
deferred function in main

```go
    tp := initTracerProvider()
    defer func() {
        if err := tp.Shutdown(context.Background()); err != nil {
            log.Printf("Error shutting down tracer provider: %v", err)
        }
    }()
```

### Adding gRPC auto-instrumentation

This service receives gRPC requests, which are instrumented in the main function
as part of the gRPC server creation.

```go
    var srv = grpc.NewServer(
        grpc.UnaryInterceptor(otelgrpc.UnaryServerInterceptor()),
        grpc.StreamInterceptor(otelgrpc.StreamServerInterceptor()),
    )
```

This service will issue several outgoing gRPC calls, which are all instrumented
by wrapping the gRPC client with instrumentation

```go
func createClient(ctx context.Context, svcAddr string) (*grpc.ClientConn, error) {
    return grpc.DialContext(ctx, svcAddr,
        grpc.WithTransportCredentials(insecure.NewCredentials()),
        grpc.WithUnaryInterceptor(otelgrpc.UnaryClientInterceptor()),
        grpc.WithStreamInterceptor(otelgrpc.StreamClientInterceptor()),
    )
}
```

### Adding Kafka ( Sarama ) auto-instrumentation

This service will write the processed results onto a Kafka topic which will then
be in turn be processed by other microservices.
To instrument the Kafka client the Producer has to be wrapped after it has been created.

```go
    saramaConfig := sarama.NewConfig()
    producer, err := sarama.NewAsyncProducer(brokers, saramaConfig)
    if err != nil {
        return nil, err
    }
    producer = otelsarama.WrapAsyncProducer(saramaConfig, producer)
```

### Add attributes to auto-instrumented spans

Within the execution of auto-instrumented code you can get current span from
context.

```go
    span := trace.SpanFromContext(ctx)
```

Adding attributes to a span is accomplished using `SetAttributes` on the span
object. In the `PlaceOrder` function several attributes are added to the span.

```go
    span.SetAttributes(
        attribute.String("app.order.id", orderID.String()), shippingTrackingAttribute,
        attribute.Float64("app.shipping.amount", shippingCostFloat),
        attribute.Float64("app.order.amount", totalPriceFloat),
        attribute.Int("app.order.items.count", len(prep.orderItems)),
    )
```

### Add span events

Adding span events is accomplished using `AddEvent` on the span object. In the
`PlaceOrder` function several span events are added. Some events have
additional attributes, others do not.

Adding a span event without attributes:

```go
    span.AddEvent("prepared")
```

Adding a span event with additional attributes:

```go
    span.AddEvent("charged",
        trace.WithAttributes(attribute.String("app.payment.transaction.id", txID)))
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

You should call `MeterProvider.Shutdown()` when your service is shutdown to
ensure all records are exported. This service makes that call as part of a
deferred function in main

```go
    mp := initMeterProvider()
    defer func() {
        if err := mp.Shutdown(context.Background()); err != nil {
            log.Printf("Error shutting down meter provider: %v", err)
        }
    }()
```

### Adding golang runtime auto-instrumentation

Golang runtime are instrumented in the main function

```go
    err := runtime.Start(runtime.WithMinimumReadMemStatsInterval(time.Second))
    if err != nil {
        log.Fatal(err)
    }
```

## Logs

TBD
