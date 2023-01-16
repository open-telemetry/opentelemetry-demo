# Accounting Service

This service calculates the total amount of sold products.
This is only mocked and received orders are printed out.

[Accounting Service](../../src/accountingservice/)

## Traces

### Initializing Tracing

The OpenTelemetry SDK is initialized from `main` using the `initTracerProvider`
function.

```go
func initTracerProvider() (*sdktrace.TracerProvider, error) {
    ctx := context.Background()

    exporter, err := otlptracegrpc.New(ctx)
    if err != nil {
        return nil, err
    }
    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exporter),
        sdktrace.WithResource(initResource()),
    )
    otel.SetTracerProvider(tp)
    otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(propagation.TraceContext{}, propagation.Baggage{}))
    return tp, nil
}
```

You should call `TracerProvider.Shutdown()` when your service is shutdown to
ensure all spans are exported. This service makes that call as part of a
deferred function in main

```go
    tp, err := initTracerProvider()
    if err != nil {
        log.Fatal(err)
    }
    defer func() {
        if err := tp.Shutdown(context.Background()); err != nil {
            log.Printf("Error shutting down tracer provider: %v", err)
        }
    }()
```

### Adding Kafka ( Sarama ) auto-instrumentation

This service will receive the processed results of the Checkout Service via a
Kafka topic.
To instrument the Kafka client the ConsumerHandler implemented by the developer
has to be wrapped.

```go
    handler := groupHandler{} // implements sarama.ConsumerGroupHandler
    wrappedHandler := otelsarama.WrapConsumerGroupHandler(&handler)
```
