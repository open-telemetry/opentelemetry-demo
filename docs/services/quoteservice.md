# Quote Service

This service is responsible for calculating shipping costs, based on
the number of items to be shipped. The quote service is called from
Shipping Service via HTTP.

The Quote Service is implemented using the Slim framework and
php-di for managing the Dependency Injection.

The PHP instrumentation may vary when using a different framework.

[Quote service source](../../src/quoteservice/)

## Traces

### Initializing Tracing

In this demo, the OpenTelemetry SDK has been automatically created as part
of SDK autoloading, which happens as part of composer autoloading.

This is enabled by setting the environment variable `OTEL_PHP_AUTOLOAD_ENABLED=true`.

```php
    require __DIR__ . '/../vendor/autoload.php';
```

There are multiple ways to create or obtain a `Tracer`, in this example we
obtain one from the global tracer provider which was initialized above, as
part of SDK autoloading:

```php
    $tracer = Globals::tracerProvider()->getTracer('manual-instrumentation');
```

### Manually creating spans

Creating a span manually can be done via a `Tracer`. The span will be default
be a child of the active span in the current execution context:

```php
    $span = Globals::tracerProvider()
        ->getTracer('manual-instrumentation')
        ->spanBuilder('calculate-quote')
        ->setSpanKind(SpanKind::KIND_INTERNAL)
        ->startSpan();
    /* calculate quote */
    $span->end();
```

### Add span attributes

You can obtain the current span using `OpenTelemetry\API\Trace\Span`.

```php
    $span = Span::getCurrent();
```

Adding attributes to a span is accomplished using `setAttribute` on the span
object. In the `calculateQuote` function 2 attributes are added to the `childSpan`.

```php
    $childSpan->setAttribute('app.quote.items.count', $numberOfItems);
    $childSpan->setAttribute('app.quote.cost.total', $quote);
```

### Add span events

Adding span events is accomplished using `addEvent` on the span object. In the
`getquote` route span events are added. Some events have
additional attributes, others do not.

Adding a span event without attributes:

```php
    $span->addEvent('Received get quote request, processing it');
```

Adding a span event with additional attributes:

```php
    $span->addEvent('Quote processed, response sent back', [
        'app.quote.cost.total' => $payload
    ]);
```

## Metrics

TBD

## Logs

TBD
