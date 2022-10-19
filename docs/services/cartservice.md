# Cart Service

This service maintains items placed in the shopping cart by users. It interacts
with a Redis caching service for fast access to shopping cart data.

[Cart service source](../../src/cartservice/)

## SDK Initialization

The OpenTelemetry .NET SDK should be initialized in your application's
`Startup.cs` as part of the `ConfigureServices` function. When initializing,
optionally specify which instrumentation libraries to leverage. The SDK is
initialized using a builder pattern, where you add each instrumentation library
(with options), and the OTLP Exporter to be used. The SDK will make use of
OpenTelemetry standard environment variables to configure the export endpoints,
resource attributes, and service name.

```cs
    services.AddOpenTelemetryTracing((builder) => builder
        .AddRedisInstrumentation(
            cartStore.GetConnection(),
            options => options.SetVerboseDatabaseStatements = true)
        .AddAspNetCoreInstrumentation()
        .AddGrpcClientInstrumentation()
        .AddHttpClientInstrumentation()
        .AddOtlpExporter());
```

## Traces

OpenTelemetry Tracing in .NET, leverages the existing `Activity` classes as
part of the core runtime.

### Add attributes to auto-instrumented spans

Within the execution of auto-instrumented code you can get current span
(activity) from context.

```cs
    var activity = Activity.Current;
```

Adding attributes to a span (activity) is accomplished using `SetTag` on the
activity object. In the `AddItem` function from `services/CartService.cs`
several attributes are added to the auto-instrumented span.

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

TBD

## Logs

TBD
