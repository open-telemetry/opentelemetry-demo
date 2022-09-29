# quote service

This service is responsible for calculating shipping costs, based on
the number of items to be shipped. The quote service is called from
Shipping Service via HTTP.

The Quote Service is implemented using the Slim framework and
php-di for managing the Dependency Injection.

The PHP instrumentation may vary when using a different framework.

[Quote service source](../../src/quoteservice/)

## Traces

### Initialize tracer provider

The OpenTelemetry SDK is initialized from `index`.

```php
    $tracerProvider = (new TracerProviderFactory('quoteservice'))->create();
    ShutdownHandler::register([$tracerProvider, 'shutdown']);
    $tracer = $tracerProvider->getTracer('io.opentelemetry.contrib.php');

    $containerBuilder->addDefinitions([
        Tracer::class => $tracer
    ]);
```

You should call `$tracerProvider->shutdown()` when your service is shutdown to
ensure all spans are exported.

### Adding HTTP instrumentation

This service receives HTTP requests, which are instrumented in the middleware.

The middleware starts root span based on route pattern, sets span status
from http code.

```php
    $app->add(function (Request $request, RequestHandler $handler) use ($tracer) {
        $parent = TraceContextPropagator::getInstance()->extract($request->getHeaders());
        $routeContext = RouteContext::fromRequest($request);
        $route = $routeContext->getRoute();
        $root = $tracer->spanBuilder($route->getPattern())
            ->setStartTimestamp((int) ($request->getServerParams()['REQUEST_TIME_FLOAT'] * 1e9))
            ->setParent($parent)
            ->setSpanKind(SpanKind::KIND_SERVER)
            ->startSpan();
        $scope = $root->activate();

        try {
            $response = $handler->handle($request);
            $root->setStatus($response->getStatusCode() < 500 ? StatusCode::STATUS_OK : StatusCode::STATUS_ERROR);
        } finally {
            $root->end();
            $scope->detach();
        }

        return $response;
    });
```

This is enough to get a new span every time a new request is received by the service.

Note that the `root` span is created with `setParent($parent)` which is coming from
the request headers. This is required to ensure Context Propagation.

### Add span attributes

Within the definition of routes, you can get current span using
`OpenTelemetry\API\Trace\AbstractSpan`.

```php
    $span = AbstractSpan::getCurrent();
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
