# Cart Service

This service maintains items placed in the shopping cart by users. It interacts
with a Redis caching service for fast access to shopping cart data.

[Cart service source](../../src/cartservice/)

## Traces

### Initialize TracerProvider

`TracerProvider` is initialized in the application startup. The required
instrumentation libraries, the exporter to use (OTLP), etc. are enabled as part
of this initialization. Resource attributes and exporter endpoint are
automatically read from OpenTelemetry standard environment variables.

```cs
services.AddOpenTelemetryTracing((builder) => builder
    .ConfigureResource(r => r.AddTelemetrySdk())
    .AddRedisInstrumentation(
        cartStore.GetConnection(),
        options => options.SetVerboseDatabaseStatements = true)
    .AddAspNetCoreInstrumentation()
    .AddGrpcClientInstrumentation()
    .AddHttpClientInstrumentation()
    .AddOtlpExporter());
```

Note:
OpenTelemetry Tracing in .NET leverages the existing `Activity` class to
represent OpenTelemetry Span.

### Add attributes to auto-instrumented spans

Within the execution of auto-instrumented code you can get current span
(activity) from context.

```cs
    var activity = Activity.Current;
```

Adding attributes (tags in .NET) to a span (activity) is accomplished using
`SetTag` on the activity object. In the `AddItem` function from
`services/CartService.cs` several attributes are added to the auto-instrumented
span.

```cs
    activity?.SetTag("app.user.id", request.UserId);
    activity?.SetTag("app.product.quantity", request.Item.Quantity);
    activity?.SetTag("app.product.id", request.Item.ProductId);
```

### Add span events

Adding span (activity) events is accomplished using `AddEvent` on the activity
object. In the `GetCart` function from `services/CartService.cs` a span event is
added.

```cs
    activity?.AddEvent(new("Fetch cart"));
```

## Metrics

### Initialize MeterProvider

`MeterProvider` is initialized in the application startup. The required
instrumentation libraries, the exporter to use (OTLP), etc. are enabled as part
of this initialization. Resource attributes and exporter endpoint are
automatically read from OpenTelemetry standard environment variables.

```cs
services.AddOpenTelemetryMetrics(builder => builder
    .ConfigureResource(r => r.AddTelemetrySdk())
    .AddRuntimeInstrumentation()
    .AddAspNetCoreInstrumentation()
    .AddOtlpExporter());
```

## Logs

TBD
