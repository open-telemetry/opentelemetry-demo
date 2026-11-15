# Chatbot Service

The Chatbot service provides a browser-based chat UI for the OpenTelemetry
Astronomy Shop demo. It uses [Gradio](https://www.gradio.app/) to render the
 interface and forwards user messages to the Agent service.

## Overview

- Runtime: Python 3.14
- UI framework: Gradio
- HTTP client: Requests
- Observability: OpenTelemetry traces exported with OTLP/gRPC
- Default port: `7860` exposed outside docker via `http://localhost:8080/chatbot/`
- If chatbot service is running access chatbot UI from [Chatbot UI](http://localhost:8080/chatbot/)

The service starts from `run.py`, configures OpenTelemetry tracing, creates
a `ChatAgentUI`, and launches a Gradio `ChatInterface`.

## How It Works

1. A user submits a message in the Gradio chat UI.
2. The chatbot sends a request to the Agent service at:

   ```text
   http://${AGENT_ENDPOINT}:${AGENT_PORT}/prompt
   ```

3. The Agent service returns a response object.
4. The chatbot displays the final message from the response in the UI.

Request body sent to the Agent service:

```json
{
    "message": "List available products",
    "session_id": "<gradio-session-id>",
    "history": [<Past interactions with agent in the same session. Empty list for the first request>]
}
```

## Default Requests

To omit the requirement of LLM access, we provide responses for a limited number
 of requests.
Requests users can try out are:

1. Show all available products in the store.
2. What currencies are supported by the Astronomy Shop?
3. What current promotions are available on binoculars?

## Configuration

The service is configured with environment variables. Values can be supplied
 through Docker Compose, `.env`, `.env.override`, or the local shell environment.

| Variable | Default | Description |
| --- | --- | --- |
| `CHATBOT_ENDPOINT` | `0.0.0.0` | Host/interface where the Gradio server binds. |
| `CHATBOT_HOST` | `chatbot` in `.env` | Hostname used by other services, such as the frontend proxy. |
| `CHATBOT_PORT` | `7860` | Port used by the Gradio server. |
| `CHATBOT_ROOT_PATH` | empty, `/chatbot` in `.env` | Root path used when the UI is served behind the frontend proxy. |
| `AGENT_ENDPOINT` | `0.0.0.0` in code, `agent` in `.env` | Hostname of the Agent service. |
| `AGENT_PORT` | `8010` | Port of the Agent service. |
| `AGENT_CHAT_INTERFACE_TIMEOUT` | `300` | Timeout, in seconds, for calls from the chatbot to the Agent service. |
| `OTEL_SERVICE_NAME` | `chatbot` in Compose | Service name used in telemetry. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | otel-collector | OTLP endpoint used by the OpenTelemetry exporter. In Compose this points to the OpenTelemetry Collector. |
| `OTEL_RESOURCE_ATTRIBUTES` | inherited | Additional OpenTelemetry resource attributes. |

## Docker Compose Configuration

In `compose.agent.yml`, the service is named `chatbot` and is built from `src/chatbot/Dockerfile`.

Important Compose settings:

- Image: `${IMAGE_NAME}:${DEMO_VERSION}-chatbot`
- Container name: `chatbot`
- Dockerfile: `${CHATBOT_DOCKERFILE}`
- Memory limit: `500M`
- Restart policy: `unless-stopped`
- Exposed port: `${CHATBOT_PORT}`
- Depends on:
  - `agent`

The frontend proxy receives `CHATBOT_HOST` and `CHATBOT_PORT`, so the chatbot
 can be exposed through the demo UI, usually under `/chatbot`.

## Observability

`run.py` configures a `TracerProvider` with the service name from
 `OTEL_SERVICE_NAME`, defaulting to `chatbot`.

The service instruments outbound HTTP calls made with:

- `requests`
- `httpx`

Spans are exported through `opentelemetry-exporter-otlp-proto-grpc` to the
configured OTLP endpoint.

## Local Development

From the repository root, create or activate a Python environment, then install
 dependencies:

```sh
pip install -r src/chatbot/requirements.txt
```

Run the Agent service first, then start the chatbot:

```sh
cd src/chatbot
CHATBOT_PORT=7860 \
AGENT_ENDPOINT=localhost \
AGENT_PORT=8010 \
python run.py
```

Open the UI at:

```text
http://localhost:7860
```

If running behind the frontend proxy, set `CHATBOT_ROOT_PATH=/chatbot`.

## Docker Build and Run

From the repository root, build and run the service with Docker Compose:

```sh
docker compose build chatbot
docker compose up chatbot
```

## File Layout

```text
src/chatbot/
|-- Dockerfile
|-- README.md
|-- requirements.txt
|-- requirements.in
|-- run.py
`-- src/
  `-- chat_interface/
    `-- chat_interface.py  # Gradio UI and Agent service client
```

## Troubleshooting

- **The UI loads but responses fail**: Verify `AGENT_ENDPOINT`, `AGENT_PORT`, and
 that the Agent service is running.
- **Requests time out**: Increase `AGENT_CHAT_INTERFACE_TIMEOUT` or check the
 LLM/Agent backend configuration.
- **The UI does not load behind the proxy**: Verify `CHATBOT_ROOT_PATH`,
 `CHATBOT_HOST`, and `CHATBOT_PORT`.
- **No telemetry appears**: Verify `OTEL_EXPORTER_OTLP_ENDPOINT`, collector
 availability, and `OTEL_SERVICE_NAME`.
- **Port conflicts locally**: Change `CHATBOT_PORT` or stop the process already
using port `7860`.
