<?php
declare(strict_types=1);

use DI\Bridge\Slim\Bridge;
use DI\ContainerBuilder;
use GuzzleHttp\Client;
use GuzzleHttp\HandlerStack;
use GuzzleHttp\Promise\PromiseInterface;
use OpenTelemetry\API\Trace\Propagation\TraceContextPropagator;
use OpenTelemetry\API\Trace\SpanKind;
use OpenTelemetry\API\Trace\StatusCode;
use OpenTelemetry\Context\Context;
use OpenTelemetry\SDK\Trace\Tracer;
use OpenTelemetry\SDK\Trace\TracerProviderFactory;
use OpenTelemetry\SDK\Common\Util\ShutdownHandler;
use Psr\Http\Message\RequestInterface;
use Psr\Http\Message\ResponseInterface as Response;
use Psr\Http\Message\ServerRequestInterface as Request;
use Psr\Http\Server\RequestHandlerInterface as RequestHandler;
use Slim\Factory\AppFactory;
use Slim\Factory\ServerRequestCreatorFactory;
use Slim\Routing\RouteContext;

require __DIR__ . '/../vendor/autoload.php';

// Instantiate PHP-DI ContainerBuilder
$containerBuilder = new ContainerBuilder();

// Set up settings
$settings = require __DIR__ . '/../app/settings.php';
$settings($containerBuilder);

// Set up dependencies
$dependencies = require __DIR__ . '/../app/dependencies.php';
$dependencies($containerBuilder);

// Add OTel
$tracerProvider = (new TracerProviderFactory('example'))->create();
ShutdownHandler::register([$tracerProvider, 'shutdown']);
$tracer = $tracerProvider->getTracer('io.opentelemetry.contrib.php');

$containerBuilder->addDefinitions([
    Tracer::class => $tracer,
    Client::class => function () use ($tracer) {
        $stack = HandlerStack::create();
        //a guzzle middleware to wrap http calls in a span, and inject trace headers
        $stack->push(function (callable $handler) use ($tracer) {
            return function (RequestInterface $request, array $options) use ($handler, $tracer): PromiseInterface {
                $span = $tracer
                    ->spanBuilder(sprintf('%s %s', $request->getMethod(), $request->getUri()))
                    ->setSpanKind(SpanKind::KIND_CLIENT)
                    ->setAttribute('http.method', $request->getMethod())
                    ->setAttribute('http.url', $request->getUri())
                    ->startSpan();

                $ctx = $span->storeInContext(Context::getCurrent());
                $carrier = [];
                TraceContextPropagator::getInstance()->inject($carrier, null, $ctx);
                //inject traceparent and tracestate headers
                foreach ($carrier as $name => $value) {
                    $request = $request->withAddedHeader($name, $value);
                }

                $promise = $handler($request, $options);
                $promise->then(function (Response $response) use ($span) {
                    $span->setAttribute('http.status_code', $response->getStatusCode())
                        ->setAttribute('http.response_content_length', $response->getHeaderLine('Content-Length') ?: $response->getBody()->getSize())
                        ->setStatus($response->getStatusCode() < 500 ? StatusCode::STATUS_OK : StatusCode::STATUS_ERROR)
                        ->end();

                    return $response;
                }, function (\Throwable $t) use ($span) {
                    $span->recordException($t)->setStatus(StatusCode::STATUS_ERROR)->end();

                    throw $t;
                });

                return $promise;
            };
        });

        return new Client(['handler' => $stack, 'http_errors' => false]);
    },
]);

// Build PHP-DI Container instance
$container = $containerBuilder->build();

// Instantiate the app
AppFactory::setContainer($container);
$app = Bridge::create($container);
$callableResolver = $app->getCallableResolver();

// Register middleware
//middleware starts root span based on route pattern, sets status from http code
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
$app->addRoutingMiddleware();

// Register routes
$routes = require __DIR__ . '/../app/routes.php';
$routes($app);

// Create Request object from globals
$serverRequestCreator = ServerRequestCreatorFactory::create();
$request = $serverRequestCreator->createServerRequestFromGlobals();

// Create Error Handler
$responseFactory = $app->getResponseFactory();

// Add Body Parsing Middleware
$app->addBodyParsingMiddleware();

// Add Error Middleware
$errorMiddleware = $app->addErrorMiddleware(true, true, true);

// Run App
$app->run();
$tracerProvider->shutdown();
