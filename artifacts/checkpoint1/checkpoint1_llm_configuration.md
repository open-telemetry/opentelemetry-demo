# Checkpoint 1 LLM configuration and limitations

## Verified configuration

The external observer used **Ollama / qwen2.5:3b** through `http://127.0.0.1:11434/api/chat`. The local model inventory and actual response identity are retained in each run's `E010.json` and `E011.json`. The scoped run is `eyes-20261023T094107764041Z`. No model was downloaded. No cloud request was made.

The installed local inventory also includes `qwen3:4b-instruct`, `llama3.2:3b`, and `llama3.2-vision:latest`. Availability in the inventory is not an inference benchmark or a guarantee of sufficient resources. Only `qwen2.5:3b` was exercised here.

The existing application's host Python environment lacks `httpx`, `openai`, and `langchain_openai`; its container Dockerfile installs its own pinned requirements. Those files and dependencies were not changed or installed into the host. Existing Pillow was used to render the architecture, and the external observer uses Python 3.11's standard library.

## Existing agent: actual supported controls

`src/agent/run.py` loads dotenv, initialises feature flags and telemetry, and starts `Agent`. `src/agent/src/agents/agents.py` constructs `ChatLLM()` and a LangChain agent for `POST /prompt`. Its built-in and MCP tool sets are shopping operations. They do not include log, metric, trace, or deployment-history tools.

| Existing setting | Implemented meaning | Limitation |
| --- | --- | --- |
| `LLM_BASE_URL` | Passed to `ChatOpenAI` as `openai_api_base`. | Requires an endpoint compatible with that installed client. Provider branding does not establish native provider API support. |
| `LLM_MODEL` | Model identifier for one `ChatLLM` instance. | No per-incident selector or fallback chain in the existing code. |
| `API_KEY` | Explicit key passed to the client; code substitutes `sk-dummy` when absent. | Dummy authentication is not cloud access. No configured usable key was found in process environment or repository env files. |
| `LLM_TLS_VERIFY` | Controls TLS verification for the async HTTP client; default true. | Keep verification enabled. It is not an authentication or network-policy workaround. |
| `USE_VCR` | Enables fixture matching/recording. The current `.env` has `True`. | Fixtures are not fresh inference or incident evidence. Set false in the launching process for a live model run; do not edit existing env files. |
| `GRAPH_RECURSION_LIMIT` | Bounds LangChain graph recursion; current configured value 25. | It is not a model context window, request timeout, or retry count. |
| `MCP_ENABLED`, `MCP_ENDPOINT`, `MCP_PORT` | Select the existing shopping MCP service. | No configurable arbitrary telemetry tool registry is exposed. |

The current checked-in model string is `claude-opus-4-7`, with a configured base URL and no usable API key. This is a configuration value, **not evidence that a cloud provider is connected or that this model ran**. The implementation imports `langchain_openai.ChatOpenAI`; native Anthropic Messages and Azure-specific authentication/routing were not found.

The constructor can accept keyword arguments, but the existing `Agent` calls it without them. Context size, temperature, output limits, inference timeout, retry policy, and multi-provider fallback do not have explicit operator environment bindings in the inspected application. SDK defaults cannot be claimed as tested because the client dependencies are not installed in the host environment. No replacement module, monkey patch, or copied `tools.py` was introduced.

Process environment variables take precedence over dotenv's default non-overriding load. Existing Compose maps the listed variables into the shopping agent. Changing those process values can select one compatible endpoint/model, but it does not add observability tools, safe routing, or model failover to that agent.

## Separate external configuration area

All new operator settings are in [checkpoint1_observe.toml](./checkpoint1_observe.toml). This is a separate artifact configuration file; the existing application does not read it. It configures [checkpoint1_observe.py](./checkpoint1_observe.py), an external read-only collector and summariser, not a replacement for application source.

| Profile field | Local Ollama | Cloud / compatible endpoint |
| --- | --- | --- |
| `enabled` | True for the demonstrated local profile. | False by default; operator must explicitly enable it. |
| `provider` | Audit label `ollama`. | Audit label for the actual operator-selected provider. |
| `backend` | `ollama`, using native `/api/chat`. | `openai-compatible`, using `/chat/completions`. No native Anthropic, Azure, or other protocol is assumed. |
| `endpoint` | Local base URL, without `/api/chat`. | HTTPS API base URL, typically ending in `/v1`, without `/chat/completions`. No embedded credentials/query string. |
| `model` | Exact installed model name. | Model available to the configured authenticated account; must be supplied by the operator. |
| `model_path` | Blank: Ollama manages model files by name. | Not applicable for hosted models. This informational field does not load a model file. |
| `api_key_env` | Blank for this local Ollama installation. | Environment variable name, default `CHECKPOINT1_CLOUD_API_KEY`; no key value in TOML. |
| `context_window` | 8192, sent as Ollama `options.num_ctx`. | Prompt-budget setting only; it cannot enlarge the provider/model context window. |
| `max_output_tokens` | 512, sent as `options.num_predict`. | Sent using `generation_field`, default `max_tokens`; `max_completion_tokens` is also supported. Match the actual provider/model contract. |
| `temperature` | 0.0. | Sent only when `send_temperature=true`; disable it for models that reject this field. |
| `timeout_seconds` | 120 per inference request. | 60 per inference request by default. |
| `max_retries` | 0 by default. | 1 by default, only for HTTP 429/500/502/503/504. Network errors are recorded and may proceed to an explicitly configured fallback; they are not blindly retried. |
| `requests_per_minute` | 6; spaces requests in this process. | Same process-local limiter. It is not a distributed account-wide rate-limit guarantee. |
| `num_thread`, `num_gpu` | Four CPU threads, zero GPU layers requested. | Not sent to a cloud endpoint. |
| `keep_alive` | `0s`, requests unloading after completion. | Not sent to compatible cloud endpoints. |

CPU/thread/output/time limits are resource controls, not a hard operating-system memory quota. Prompt evidence is bounded by a conservative character budget with explicit omitted-result markers; an exact provider tokenizer is not installed. The full evidence stays in run files.

`llama.cpp` and other local servers were not detected or installed. A pre-existing server exposing a compatible Chat Completions endpoint can use the external profile's `openai-compatible` backend, with its server managed independently. Model file paths and server startup flags belong to that actual backend; the observer does not start an inference server or silently download weights.

Ollama documents its [chat API](https://docs.ollama.com/api/chat) and [OpenAI-compatible subset](https://docs.ollama.com/api/openai-compatibility). Compatibility is a subset, so do not infer support for every provider-specific parameter from the endpoint name.

## Operator model selection and fallback

The external `route` accepts:

| Value | Attempt order |
| --- | --- |
| `local-only` | Local only; used in the recorded real inference. |
| `cloud-only` | Cloud only. |
| `local-first` | Local, then cloud if local fails. |
| `cloud-first` | Cloud, then local if cloud fails. |

A disabled or incomplete profile is recorded as unavailable. The successful response records both requested and returned model names and preceding failed attempts. A structured-response/citation validation failure also permits trying the next configured profile. Fallback may disclose the same sanitised evidence to the enabled cloud profile; use `local-only` when that is not authorised. No cloud route is enabled implicitly.

These routes are implemented in the external observer only. The existing shopping agent has no runtime fallback control that can be enabled without code changes. Selecting one endpoint/model in its existing environment is the closest native alternative.

To use cloud inference, put a new endpoint, actual model, and provider label in the **new** TOML profile, enable it, and supply the key through its named process environment variable or an existing secret manager that populates that variable. The observer does not fetch secret-manager credentials itself. Choose the route explicitly. No endpoint or model is preselected as a connected cloud account, and no credentials should be pasted into the execution log.

Examples of observer execution from Windows PowerShell:

```powershell
python -B artifacts/checkpoint1/checkpoint1_recon.py
python -B artifacts/checkpoint1/checkpoint1_observe.py
python -B artifacts/checkpoint1/checkpoint1_observe.py --verify-only
```

An alternate new TOML profile can be selected with `--config <path>`. Re-running creates another evidence directory and updates the new report artifact. The current Docker transport is explicitly `wsl -d Ubuntu -- docker`; it does not depend on Docker Desktop.

## Verification and remaining limits

- Local inventory discovery and real `qwen2.5:3b` inference: verified.
- Local-only route and returned model identity: verified in actual API responses.
- External route order, disabled/missing profiles, and rejection of invented evidence IDs: checked separately in [routing_validation.json](./routing_validation.json). Simulated failures in that file are labelled tests, not cloud execution.
- Cloud authentication, rate limits, native provider behaviour, and real cross-provider fallback: not verified; no usable cloud key was found, and no cloud request was made.
- First inference hallucinated a running MinIO service using unrelated inventory. It was rejected in the first run's `operator_review.json`; subsequent collection is scoped to the demo project. Citation existence alone is not semantic evidence validation.
- The scoped inference removed that invented service, but loosely grouped trace failures under metrics. The final report records that correction and uses directly observed facts for its findings.
- No practice injection or successful Eyes demonstration is claimed. The inspector's connection errors do not substitute for incident telemetry.
