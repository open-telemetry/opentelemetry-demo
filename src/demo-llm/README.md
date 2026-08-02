# Demo LLM Service

The Demo LLM service serves a small language model over an OpenAI-compatible
HTTP API, so the [Agent](../agent/README.md) can run without an external LLM
provider, an API key, or outbound network access.

The model is a ~5M parameter decoder-only transformer trained on agent
trajectories recorded from this demo. It is a domain model, not a general one:
it handles the astronomy shop's tools and phrasings and nothing else.

## Overview

- Runtime: Python 3.12
- Web framework: FastAPI served by Uvicorn
- Inference: PyTorch (CPU)
- Default port: `8012`
- Model: 5,263,360 parameters, ~21MB, vocab 2048, context 2048

## Service API

### `POST /v1/chat/completions`

OpenAI chat completions. Accepts `messages`, `tools`, `temperature`,
`max_tokens` and `stream`, and returns a standard completion object with
`tool_calls` when the model calls a tool.

### `GET /v1/models`

Lists the single served model.

### `GET /health`

Liveness plus counters for requests served, generations resampled, and tool
calls dropped.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `DEMO_LLM_PORT` | `8012` | Port used by the FastAPI/Uvicorn server. |
| `DEMO_LLM_MODEL_NAME` | `demo-llm` | Model id reported by the API. |
| `DEMO_LLM_ARTIFACTS` | `artifacts` | Directory holding the tokenizer, conditioning and weights. |
| `DEMO_LLM_CHECKPOINT` | `artifacts/model.pt` | Trained weights to load. |
| `DEMO_LLM_DEVICE` | `cpu` | Torch device. |
| `DEMO_LLM_THREADS` | `2` | Torch intra-op threads, bounded so one container cannot take the host. |
| `DEMO_LLM_MAX_RETRIES` | `3` | Resamples allowed when a generated tool call is invalid. |

## How the Agent uses it

The Agent defaults to this service. With `LLM_BASE_URL` empty it builds
`http://${DEMO_LLM_ENDPOINT}:${DEMO_LLM_PORT}/v1` and sends a dummy API key.

Setting `LLM_BASE_URL` switches the Agent to any OpenAI-compatible provider and
`API_KEY` is sent with the request:

```sh
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
API_KEY=sk-...
```

The same applies to Azure OpenAI, vLLM, Ollama and LiteLLM, since all of them
expose the OpenAI chat completions shape.

## Two behaviours worth knowing

### Generation stops at a tool call

The model was trained on transcripts that contain tool *results*, so left to
run it will happily invent one. In an agent loop that output would be fiction.
Generation therefore stops at the `<|result|>` marker: the service returns the
tool call, and the Agent executes the real tool.

### Invalid tool calls are resampled, then dropped

A request lists the tools the caller offers, so a call naming anything else is
provably wrong. The service resamples up to `DEMO_LLM_MAX_RETRIES` times, and
if the call is still invalid it is dropped rather than returned - handing the
Agent a call it cannot execute is worse than handing it none. `/health` reports
how often this happens.

## Observability

The service emits spans named `chat demo-llm` carrying the upstream
`gen_ai.*` semantic convention attributes (`gen_ai.operation.name`,
`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`,
`gen_ai.usage.output_tokens`, `gen_ai.response.finish_reasons`), plus
`demo.llm.sample_attempts` and `demo.llm.dropped_tool_calls`.

FastAPI request spans come from `opentelemetry-instrumentation-fastapi`.

## Local Development

```sh
pip install -r src/demo-llm/requirements.in
cd src/demo-llm
PYTHONPATH=src DEMO_LLM_PORT=8012 python run.py
```

Then send a request:

```sh
curl -X POST http://localhost:8012/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Show all available products in the store."}]}'
```

## Docker Build and Run

```sh
docker compose build demo-llm
docker compose up demo-llm
```

The image installs the CPU-only PyTorch wheel; the CUDA build would add several
gigabytes for no benefit at this model size.

## Updating the model

`artifacts/` holds everything the service loads:

```text
artifacts/tokenizer.json      byte-level BPE, vocab 2048
artifacts/conditioning.json   system prompts and tool sets seen in training
artifacts/model.pt            trained weights
```

All three must come from the same training run. The tokenizer and the weights
are coupled: retraining the tokenizer changes what each vocabulary id means, so
a checkpoint paired with a different `tokenizer.json` will load without error
and produce nonsense.
