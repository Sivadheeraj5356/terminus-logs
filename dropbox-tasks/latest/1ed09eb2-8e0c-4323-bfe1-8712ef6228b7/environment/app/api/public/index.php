<?php

declare(strict_types=1);

require __DIR__ . '/../vendor/autoload.php';

use Psr\Http\Message\ResponseInterface as Response;
use Psr\Http\Message\ServerRequestInterface as Request;
use Psr\Http\Server\RequestHandlerInterface as Handler;
use Slim\Factory\AppFactory;

const PRIVATE_DIR = '/opt/api-private';
const ACCESS_LOG = '/var/log/linkreg-api/access.log';

/**
 * Load one of the private metadata documents backing this service.
 */
function loadDocument(string $name): array
{
    $raw = file_get_contents(PRIVATE_DIR . '/' . $name);
    if ($raw === false) {
        throw new RuntimeException('missing metadata document: ' . $name);
    }

    return json_decode($raw, true, 512, JSON_THROW_ON_ERROR);
}

function jsonResponse(Response $response, array $payload, int $status = 200): Response
{
    $response->getBody()->write(
        json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n"
    );

    return $response
        ->withHeader('Content-Type', 'application/json')
        ->withStatus($status);
}

$app = AppFactory::create();

// Every request is recorded so operators can audit which clients actually
// pulled the interface list and shaping adjustments from the service.
$app->add(function (Request $request, Handler $handler): Response {
    @mkdir(dirname(ACCESS_LOG), 0o755, true);
    @file_put_contents(
        ACCESS_LOG,
        $request->getMethod() . ' ' . $request->getUri()->getPath() . "\n",
        FILE_APPEND
    );

    return $handler->handle($request);
});

$app->get('/health', function (Request $request, Response $response): Response {
    return jsonResponse($response, ['status' => 'ok']);
});

$app->get('/links', function (Request $request, Response $response): Response {
    return jsonResponse($response, loadDocument('links.json'));
});

$app->get('/links/{id}', function (Request $request, Response $response, array $args): Response {
    foreach (loadDocument('links.json')['links'] as $link) {
        if ($link['iface_id'] === $args['id']) {
            return jsonResponse($response, $link);
        }
    }

    return jsonResponse($response, ['error' => 'unknown interface'], 404);
});

$app->get('/shaping/{id}', function (Request $request, Response $response, array $args): Response {
    $shaping = loadDocument('shaping.json');
    if (array_key_exists($args['id'], $shaping)) {
        return jsonResponse($response, $shaping[$args['id']]);
    }

    return jsonResponse($response, ['error' => 'unknown interface'], 404);
});

$app->addRoutingMiddleware();
$app->addErrorMiddleware(false, false, false);
$app->run();
