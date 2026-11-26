# Frontend service

The frontend is a [Next.js](https://nextjs.org/) application that is composed
by two layers.

1. Client side application. Which renders the components for the OTEL webstore.
2. API layer. Connects the client to the backend services by exposing REST endpoints.

## Build Locally

By running `docker compose up` at the root of the project you'll have access to
the frontend client by going to <http://localhost:8080/>.

## Local development

Currently, the easiest way to run the frontend for local development is to execute

```shell
docker compose run --service-ports -e NODE_ENV=development --volume $(pwd)/src/frontend:/app --volume $(pwd)/pb:/app/pb --user node --entrypoint sh frontend
```

from the root folder.

It will start all of the required backend services
and within the container simply run `npm run dev`.
After that the app should be available at <http://localhost:8080/>.

## Shop assistant

`make start-agentic` enables the **Ask the assistant** button in the storefront.
Open it to ask a question, then send a follow-up to continue the conversation.
Conversation history stays in the current page and is cleared on reload.
The separate Gradio chatbot remains available.

The demo agent uses recorded model responses by default. Try
`Show all available products in the store.` for a recorded question. Free-form
questions and follow-ups require a live model if they miss the recordings.

The panel is off by default. With `make start`, the button is hidden and
`POST /api/assistant` returns 404. The agentic Compose overlay sets
`ASSISTANT_ENABLED=true` and passes `AGENT_ADDR` to the frontend at runtime.
When running the frontend outside Compose, set both variables and restart the
frontend to enable it. For example, use `AGENT_ADDR=localhost:8010` for a local agent.

The route accepts `{ "message": "Show products", "history": [] }` and returns
`{ "reply": "..." }`. Only user and assistant text entries are forwarded in
history. Answers are buffered, with a two-minute timeout. Connection failures or
invalid agent responses return 502, and a timeout returns 504. Failed questions
stay in the input for retry and are excluded from subsequent history.

Each submitted question starts an `assistant.submit` span on the existing browser
tracer. The same-origin fetch and server instrumentation provide the frontend
hops. The panel does not add prompt text, replies or conversation history to span
attributes. Streaming and changes to MCP trace propagation are separate work.

Run the assistant API tests locally with `npm run test:assistant` from
`src/frontend`. They use Node's test runner and a local HTTP stand-in for the agent.
