<?php
// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0



declare(strict_types=1);

use DI\Bridge\Slim\Bridge;
use DI\ContainerBuilder;
use OpenTelemetry\API\Globals;
use OpenTelemetry\SDK\Common\Configuration\Configuration;
use OpenTelemetry\SDK\Common\Configuration\Variables;
use OpenTelemetry\SDK\Logs\LoggerProviderInterface;
use OpenTelemetry\SDK\Metrics\MeterProviderInterface;
use OpenTelemetry\SDK\Trace\TracerProviderInterface;
use Psr\Http\Message\ServerRequestInterface;
use React\EventLoop\Loop;
use React\Http\HttpServer;
use React\Socket\SocketServer;
use Slim\Factory\AppFactory;

require __DIR__ . '/../vendor/autoload.php';

// Instantiate PHP-DI ContainerBuilder
$containerBuilder = new ContainerBuilder();

// Set up settings
$settings = require __DIR__ . '/../app/settings.php';
$settings($containerBuilder);

// Set up dependencies
$dependencies = require __DIR__ . '/../app/dependencies.php';
$dependencies($containerBuilder);

// Build PHP-DI Container instance
$container = $containerBuilder->build();

// Instantiate the app
AppFactory::setContainer($container);
$app = Bridge::create($container);

// Register middleware
$app->addRoutingMiddleware();

// Register routes
$routes = require __DIR__ . '/../app/routes.php';
$routes($app);

// Add Body Parsing Middleware
$app->addBodyParsingMiddleware();

// Add Error Middleware
$errorMiddleware = $app->addErrorMiddleware(true, true, true);
Loop::get()->addSignal(SIGTERM, function() {
    exit;
});

/* workaround for non-async batch processors */
if (($tracerProvider = Globals::tracerProvider()) instanceof TracerProviderInterface) {
    Loop::addPeriodicTimer(Configuration::getInt(Variables::OTEL_BSP_SCHEDULE_DELAY)/1000, function() use ($tracerProvider) {
        $tracerProvider->forceFlush();
    });
}
if (($loggerProvider = Globals::loggerProvider()) instanceof LoggerProviderInterface) {
    Loop::addPeriodicTimer(Configuration::getInt(Variables::OTEL_BLRP_SCHEDULE_DELAY)/1000, function() use ($loggerProvider) {
        $loggerProvider->forceFlush();
    });
}
if (($meterProvider = Globals::meterProvider()) instanceof MeterProviderInterface) {
    Loop::addPeriodicTimer(Configuration::getInt(Variables::OTEL_METRIC_EXPORT_INTERVAL)/1000, function() use ($meterProvider) {
        $meterProvider->forceFlush();
    });
}

$server = new HttpServer(function (ServerRequestInterface $request) use ($app) {
    $response = $app->handle($request);
    echo sprintf('[%s] "%s %s HTTP/%s" %d %d %s',
        date('Y-m-d H:i:sP'),
        $request->getMethod(),
        $request->getUri()->getPath(),
        $request->getProtocolVersion(),
        $response->getStatusCode(),
        $response->getBody()->getSize(),
        PHP_EOL,
    );

    return $response;
});
// Configure IPv4 or IPv6 address based on environment variable
$ipv6_enabled = strtolower(getenv('IPV6_ENABLED')) === 'true' || getenv('IPV6_ENABLED') === '1';
$host = $ipv6_enabled ? '[::]' : '0.0.0.0';
$address = $host . ':' . getenv('QUOTE_PORT');

echo "DEBUG: IPV6_ENABLED = " . (getenv('IPV6_ENABLED') ?: 'not set') . PHP_EOL;
echo "DEBUG: Binding to {$address} (IPv6 " . ($ipv6_enabled ? 'ENABLED' : 'DISABLED') . ")" . PHP_EOL;

$socket = new SocketServer($address);
$server->listen($socket);

echo "Listening on: {$address}" . PHP_EOL;
