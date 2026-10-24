# Declarations

Required by the hackathon rules: every AI tool, model and library used, declared from the first commit.

## AI tools and models

| Tool | Model | Used for |
|---|---|---|
| Claude Code (CLI coding assistant) | Claude Sonnet 5.5 (`claude-sonnet-5-5`) | Writing and editing the code and docs in this repo, under the driver's direction |
| Claude (chat assistant) | model version not recorded here, the driver to fill in | Planning: `plan.md` and `CONTEXT.md` |

The LLM that the on-call agent itself calls at run time is not chosen yet (no key received). It will be added here once known.

## Review

The driver reviews every change made by an AI tool before committing it, and can explain and change every line.
Nothing is committed by the assistant.

## Libraries

Added as the code needs them. Versions are the ones installed in `.venv` on 2026-10-23.

| Library | Version | Why |
|---|---|---|
| requests | 2.34.2 | HTTP calls to Prometheus, Jaeger and OpenSearch |
| python-dotenv | 1.2.4 | Read `.env.incident` from an explicit path |
| pytest | 9.1.1 | Tests |

The LLM provider SDK will be added when the provider is known.
- Runtime LLM for the agent: Anthropic Claude Haiku (claude-haiku-5-5) via the `anthropic` Python SDK 2.2.0, using the driver's own API key.
