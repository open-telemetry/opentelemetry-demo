# Product Reviews Service

This service returns product reviews for a specific product, along with an
AI-generated summary of the product reviews.

## Local Build

To build the protos, run from the root directory:

```sh
make docker-generate-protobuf
```

## Docker Build

From the root directory, run:

```sh
docker compose build product-reviews
```

## Docker Run

From the root directory, run:

```sh
docker compose up product-reviews
```

This starts the service and its dependencies (`astronomy-db`, `llm`,
`product-catalog`, and `otel-collector`).

## Database Instrumentation

PostgreSQL queries are instrumented with
[opentelemetry-instrumentation-psycopg2](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/psycopg2/psycopg2.html),
with SQLCommenter enabled to append trace context to SQL statements (for example,
`traceparent` and `db_driver` key-value pairs in query comments).

The instrumentor is configured in `database.py`:

```python
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor

Psycopg2Instrumentor().instrument(enable_commenter=True)
```

When running with `opentelemetry-instrument`, auto-instrumentation for psycopg2
must be disabled so the manual configuration above takes effect. The demo sets
this in `compose.yaml`:

```yaml
OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=psycopg2
```

Set the same environment variable when deploying outside Docker Compose.

## LLM Configuration

By default, this service uses a mock LLM service, as configured in
the `.env` file:

``` yaml
LLM_BASE_URL=http://${LLM_HOST}:${LLM_PORT}/v1
LLM_MODEL=astronomy-llm
OPENAI_API_KEY=dummy
```

If desired, the configuration can be changed to point to a real, OpenAI API
compatible LLM in the file `.env.override`. For example, the following
configuration can be used to utilize OpenAI's gpt-4o-mini model:

``` yaml
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=<replace with API key>
```
