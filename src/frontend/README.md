# Frontend service

The frontend is a [Next.js](https://nextjs.org/) application that is composed
by two layers.

1. Client side application. Which renders the components for the OTEL webstore.
2. API layer. Connects the client to the backend services by exposing REST endpoints.

## OpenTelemetry Instrumentation

The frontend application has been configured to **not bundle the OpenTelemetry SDK**. Instead, it relies on external instrumentation attached at runtime via environment variables.

### Server-Side (Node.js/Next.js)

To enable OpenTelemetry on the Node.js server:

**Option 1: Using environment variables**
```shell
export OTEL_SERVICE_NAME=frontend
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
export OTEL_TRACES_EXPORTER=otlp
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
npm run start
```

**Option 2: Using Node.js auto-instrumentation**
```shell
node --require @opentelemetry/auto-instrumentations-node/register server.js
```

**Option 3: Via Docker with environment variables**
Set the environment variables in your `docker-compose.yml` or deployment configuration.

### Client-Side (Browser)

Browser-side instrumentation requires:
- OpenTelemetry JavaScript SDK loaded via a `<script>` tag
- Browser extension or RUM solution
- Proxy-injected instrumentation

The application uses OpenTelemetry API calls that will only emit signals when an external SDK is present.

## Build Locally

By running `docker compose up` at the root of the project you'll have access to the
frontend client by going to <http://localhost:8080/>.

## Local development

Currently, the easiest way to run the frontend for local development is to execute

```shell
docker compose run --service-ports -e NODE_ENV=development --volume $(pwd)/src/frontend:/app --volume $(pwd)/pb:/app/pb --user node --entrypoint sh frontend
```

from the root folder.

It will start all of the required backend services
and within the container simply run `npm run dev`.
After that the app should be available at <http://localhost:8080/>.
