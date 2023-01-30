# Ad Service

This service determines appropriate ads to serve to users based on context
keys. The ads will be for products available in the store.

[Ad service source](../../src/adservice/)

## Auto-instrumentation

This service relies on the OpenTelemetry Java Agent to automatically instrument
libraries such as gRPC, and to configure the OpenTelemetry SDK. The agent is
passed into the process using the `-javaagent` command line argument. Command
line arguments are added through the `JAVA_TOOL_OPTIONS` in the `Dockerfile`,
and leveraged during the automatically generated Gradle startup script.

```dockerfile
ENV JAVA_TOOL_OPTIONS=-javaagent:/app/opentelemetry-javaagent.jar
```

## Traces

### Add attributes to auto-instrumented spans

Within the execution of auto-instrumented code you can get current span from
context.

```java
    Span span = Span.current();
```

Adding attributes to a span is accomplished using `setAttribute` on the span
object. In the `getAds` function multiples attribute are added to the span.

```java
    span.setAttribute("app.ads.contextKeys", req.getContextKeysList().toString());
    span.setAttribute("app.ads.contextKeys.count", req.getContextKeysCount());
```

### Add span events

Adding an event to a span is accomplished using `addEvent` on the span object.
In the `getAds` function an event with an attribute is added when an exception
is caught.

```java
    span.addEvent("Error", Attributes.of(AttributeKey.stringKey("exception.message"), e.getMessage()));
```

### Setting span status

If the result of the operation is an error, the span status should be set
accordingly using `setStatus` on the span object. In the `getAds` function the
span status is set when an exception is caught.

```java
    span.setStatus(StatusCode.ERROR);
```

### Create new spans

New spans can be created and started using
`Tracer.spanBuilder("spanName").startSpan()`. Newly created spans should be set
into context using `Span.makeCurrent()`. The `getRandomAds` function will
create a new span, set it into context, perform an operation, and finally end
the span.

```java
    // create and start a new span manually
    Tracer tracer = GlobalOpenTelemetry.getTracer("adservice");
    Span span = tracer.spanBuilder("getRandomAds").startSpan();

    // put the span into context, so if any child span is started the parent will be set properly
    try (Scope ignored = span.makeCurrent()) {

      Collection<Ad> allAds = adsMap.values();
      for (int i = 0; i < MAX_ADS_TO_SERVE; i++) {
        ads.add(Iterables.get(allAds, random.nextInt(allAds.size())));
      }
      span.setAttribute("app.ads.count", ads.size());

    } finally {
      span.end();
    }
```

## Metrics

### Initializing Metrics

Similar to creating spans, the first step in creating metrics is initializing a
`Meter` instance, e.g. `GlobalOpenTelemetry.getMeter("adservice")`.  From
there, use the various builder methods available on the `Meter` instance to
create the desired metric instrument, e.g.:

```java
meter
  .counterBuilder("app.ads.ad_requests")
  .setDescription("Counts ad requests by request and response type")
  .build();
```

### Current Metrics Produced

Note that all the metric names below appear in Prometheus/Grafana with `.`
characters transformed to `_`.

#### Custom metrics

The following custom metrics are currently available:

* `app.ads.ad_requests`: A counter of ad requests with dimensions describing
whether the request was targeted with context keys or not, and whether the
response was targeted or random ads.

#### Auto-instrumented metrics

The following auto-instrumented metrics are available for the application:

* [Runtime metrics for the JVM](https://opentelemetry.io/docs/reference/specification/metrics/semantic_conventions/runtime-environment-metrics/#jvm-metrics).
* [Latency metrics for RPCs](https://opentelemetry.io/docs/reference/specification/metrics/semantic_conventions/rpc-metrics/#rpc-server)

## Logs

TBD
