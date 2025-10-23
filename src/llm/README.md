# LLM

The LLM service is used by the Product Review service to provide
AI-generated summaries of product reviews.

While it's not an actual Large Language Model, the LLM pretends to be one
by following the [OpenAI API format for chat completions](https://platform.openai.com/docs/api-reference/chat/create).

The Product Review service is then instrumented with the
[opentelemetry-instrumentation-openai-v2](https://pypi.org/project/opentelemetry-instrumentation-openai-v2/)
package, allowing us to capture Generative AI related span attributes when
it interacts with the LLM service.

The first request to the `/v1/chat/completions` endpoint should include a
database tool. The LLM service then responds with a request to execute the
tool.

The second request to the `/v1/chat/completions` endpoint should include the
results of the database tool call (which is the list of product reviews for
the specified product).  It then responds with the summary of product reviews
for that product.  Note that the summaries were pre-generated using
an LLM, and are stored in a JSON file to avoid calling an actual LLM each time.

The service supports two feature flags:

* `llmInaccurateResponse`: when this feature flag is enabled the LLM service
returns an inaccurate product summary for product ID L9ECAV7KIM
* `llmRateLimitError`: when this feature flag is enabled, the LLM service
intermittently returns a RateLimitError with HTTP status code 429

Note that the LLM service itself is not instrumented with OpenTelemetry.
This is intentional, as we're treating it like a black box, just like
most 3rd party LLMs would be treated.
