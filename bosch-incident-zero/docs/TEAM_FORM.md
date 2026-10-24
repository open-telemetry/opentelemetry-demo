# Team form draft

Draft answers for the organisers' team form. Fill in every `<!-- TODO -->` before submitting; do not guess
names or contributions.

## Team

| Member | Main contributions |
|---|---|
| <!-- TODO: name --> | <!-- TODO: who built what --> |
| <!-- TODO: name --> | <!-- TODO --> |
| <!-- TODO: name --> | <!-- TODO --> |
| <!-- TODO: name --> | <!-- TODO --> |

Team repository: `kirthang/opentelemetry-demo-team8`, project folder `bosch-incident-zero/`.

## Approach

A custom Python agent loop. No agent framework (no Google ADK) and no MCP server. The LLM picks which
read-only tool to call and writes the diagnosis. Deterministic code validates every citation, sets the
confidence ceiling, decides escalation, and owns the approval gate, kill switch and action allowlist.
See [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md).

## AI models used by the agent at runtime

| Model | Provider / access | Used for | Notes |
|---|---|---|---|
| `nvidia/nemotron-3-ultra-550b-a55b:free` | OpenRouter (provider `openrouter`), free tier | Tool selection and diagnosis (main model) | <!-- TODO: confirm with mentors that our own key is allowed --> |
| `nvidia/nemotron-3.5-super-vl:free`, `poolside/laguna-s-2.1:free`, `nvidia/nemotron-3.5-lightning:free`, `dots-studio/dots-3-note-preview:free` | OpenRouter, free tier | Fallbacks, tried in order only on 402/404/429/5xx/timeouts | The model that answered is recorded in each transcript |
| `gemini-3.5-flash` | Google Gemini, OpenAI-compatible endpoint | Day 1 development runs | Dropped as the main model after daily quota limits |

Free-tier limits: about 20 requests a minute and about 50 a day without credits, so tests and the
Checkpoint 3 rehearsal replay recorded real transcripts (labelled `REPLAY`; never claimed as a live verified
recovery). Free providers may log prompts: only demo telemetry is sent, and keys are never put in prompts.

The provider is configurable (`LLM_PROVIDER`, `LLM_MODEL` in the git-ignored `.env`); `src/agent/llm.py` is
the only provider-specific file.

## AI assistants used to write code and docs

| Assistant | Used for |
|---|---|
| Claude Code (Anthropic), sessions running Claude Sonnet 5.5 and Claude Opus 5.5 | Code, tests and docs; AI-assisted commits carry an `Assisted-by:` trailer |
| <!-- TODO: any other assistant a member used --> | <!-- TODO --> |

## Libraries

From `requirements.txt` and the LLM SDKs installed alongside it:

| Library | Purpose |
|---|---|
| `pydantic` | Data models |
| `requests` | HTTP clients for Prometheus, Jaeger and OpenSearch |
| `pyyaml` | Configuration files |
| `jsonschema` | Report and diagnosis validation |
| `rich` | Terminal output |
| `pytest`, `pytest-mock` | Tests |
| `openai` | OpenAI-compatible client (OpenRouter, Gemini, OpenAI) |
| `anthropic` | Anthropic client (optional provider) |

## Tools and data sources

- The OpenTelemetry Astronomy Shop demo: Prometheus, Jaeger, OpenSearch and the Docker CLI, all read-only.
- The organisers' `faultctl` for fault injection and reset. <!-- TODO: confirm once supplied; BLOCKED as of 2026-10-24 -->
- The organisers' Action API for remediation. <!-- TODO: confirm once the contract is supplied -->

## Declarations

- No tool reads or edits flagd, `demo.flagd.json` or the Feature Flags UI.
- No pre-trained or fine-tuned model of our own was used. <!-- TODO: confirm -->
- <!-- TODO: anything else the form asks for -->
