<?php
declare(strict_types=1);

use OpenTelemetry\API\Trace\AbstractSpan;
use Psr\Http\Message\ResponseInterface as Response;
use Psr\Http\Message\ServerRequestInterface as Request;
use Slim\App;

return function (App $app) {
    $app->get('/getquote', function (Request $request, Response $response) {
        $span = AbstractSpan::getCurrent();

        # do the math here
        $data = ['quote' => 32.50];

        $span->addEvent('Received get quote request, processing it.');
        $span->setAttribute('app.quote.cost.total', $data['quote']);

        $payload = json_encode($data);
        $response->getBody()->write($payload);

        $span->addEvent('Quote processed, response sent back');

        return $response
            ->withHeader('Content-Type', 'application/json');
    });
};
