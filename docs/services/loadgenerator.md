# Load Generator

The load generator is based on the Python load testing framework [Locust](https://locust.io).
By default it will simulate users requesting several different routes from the
frontend.

[Load generator source](../../src/loadgenerator/)

## Traces

### Initializing Tracing

Since this service is a [locustfile](https://docs.locust.io/en/stable/writing-a-locustfile.html),
the The OpenTelemetry SDK is initialized after the import statements. This code
will create a tracer provider, and establish a Span Processor to use. Export
endpoints, resource attributes, and service name are automatically set using
[OpenTelemetry environment variables](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/sdk-environment-variables.md).

```python
tracer_provider = TracerProvider()
trace.set_tracer_provider(tracer_provider)
tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
```

### Adding instrumentation libraries

To add instrumentation libraries you need to import the Instrumentors for each
library in your Python code. Locust uses the `Requests` and`URLLib3` libraries,
so we will import their Instrumentors.

```python
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
```

In your code before the library is leveraged, the Instrumentor needs to be
initialized by calling `instrument()`.

```python
RequestsInstrumentor().instrument()
URLLib3Instrumentor().instrument()
```

Once initialized, every Locust requests for this load generator will have their
own trace with a span for each of the `Requests` and `URLLib3` libraries.

## Metrics

TBD

## Logs

TBD

## Baggage

OpenTelemetry Baggage is used by the load generator to indicate that the traces
are synthetically generated. This is done in the `on_start` function by creating
a context object containing the baggage item, and associating that context for
all tasks by the load generator.

```python
    ctx = baggage.set_baggage("synthetic_request", "true")
    context.attach(ctx)
```
