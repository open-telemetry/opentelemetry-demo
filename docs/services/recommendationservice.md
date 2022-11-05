# Recommendation Service

This service is responsible to get a list of recommended products for the user
based on existing product ids the user is browsing.

[Recommendation service source](../../src/recommendationservice/)

## Auto-instrumentation

This Python based service, makes use of the OpenTelemetry auto-instrumentor
for Python, accomplished by leveraging the `opentelemetry-instrument` Python
wrapper to run the scripts. This can be done in the `ENTRYPOINT` command for the
service's `Dockerfile`.

```dockerfile
ENTRYPOINT [ "opentelemetry-instrument", "python", "recommendation_server.py" ]
```

## Traces

### Initializing Tracing

The OpenTelemetry SDK is initialized in the `__main__` code block. This code
will create a tracer provider, and establish a Span Processor to use. Export
endpoints, resource attributes, and service name are automatically set by the
OpenTelemetry auto instrumentor based on environment variables.

```python
    tracer = trace.get_tracer_provider().get_tracer("recommendationservice")
```

### Add attributes to auto-instrumented spans

Within the execution of auto-instrumented code you can get current span from
context.

```python
    span = trace.get_current_span()
```

Adding attributes to a span is accomplished using `set_attribute` on the span
object. In the `ListRecommendations` function an attribute is added to the span.

```python
    span.set_attribute("app.products_recommended.count", len(prod_list))
```

### Create new spans

New spans can be created and placed into active context using
`start_as_current_span` from an OpenTelemetry Tracer object. When used in
conjunction with a `with` block, the span will automatically be ended when the
block ends execution. This is done in the `get_product_list` function.

```python
    with tracer.start_as_current_span("get_product_list") as span:
```

## Metrics

### Initializing Metrics

The OpenTelemetry SDK is initialized in the `__main__` code block. This code
will create a meter provider. Export
endpoints, resource attributes, and service name are automatically set by the
OpenTelemetry auto instrumentor based on environment variables.

```python
    meter = metrics.get_meter_provider().get_meter("recommendationservice")
```

### Custom metrics

The following custom metrics are currently available:

* `app_recommendations_counter`: Cumulative count of # recommended
 products per service call

### Auto-instrumented metrics

The following metrics are available through auto-instrumentation, courtesy of
the `opentelemetry-instrumentation-system-metrics`, which is installed as part
of `opentelemetry-bootstrap` on building the recommendationservice Docker image:

* `runtime.cpython.cpu_time`
* `runtime.cpython.memory`
* `runtime.cpython.gc_count`

## Logs

TBD
