# Load Generator

The load generator creates simulated traffic to the demo using
[k6](https://k6.io/).

## Modifying the Load Generator

The load test script lives at [`script.js`](./script.js). See the [k6
documentation](https://grafana.com/docs/k6/latest/) for more on writing k6
scripts.

Tracing and log correlation are provided by a custom k6 extension,
[`xk6-otel`](./xk6-otel), which exposes a `Tracer` to the script (imported as
`k6/x/otel`) for creating OTel spans and injecting `traceparent` headers into
outgoing HTTP requests.

The extension also emits Go runtime metrics (memory, GC, goroutines) via the
OTel contrib `runtime` instrumentation. These are separate from k6's own
built-in test metrics, which are exported via the `--out opentelemetry` output
enabled in [`entrypoint.sh`](./entrypoint.sh)'s `k6 run` invocation; the OTLP
endpoint and protocol for that output are configured via the `K6_OTEL_*` env
vars in `compose.yaml`.

## Traffic mix

Each `httpScenario` iteration picks one task at random, weighted so browsing
dominates over checkout:

| Task                  | Weight |
| --------------------- | -----: |
| `index`               |      1 |
| `browseProduct`       |     10 |
| `getRecommendations`  |      3 |
| `getAds`              |      3 |
| `viewCart`            |      3 |
| `addToCart`           |      2 |
| `checkout`            |      1 |
| `checkoutMulti`       |      1 |
| `floodHome`           |      5 |

## Controlling traffic and concurrency via feature flags

* `loadGeneratorTraffic` - pauses all synthetic traffic (both scenarios) when
  turned off, checked every iteration with no restart required.
* `loadGeneratorVUs` - sets the number of concurrent virtual users the HTTP
  scenario runs. k6 v2's `constant-vus` executor can't resize its VU pool at
  runtime - it dropped the externally-controlled executor, and its REST API
  now rejects live VU changes outright - so
  [`entrypoint.sh`](./entrypoint.sh) polls flagd and restarts k6 with the new
  VU count only when this flag's value actually changes, rather than on a
  fixed timer.
`entrypoint.sh` passes the VU count to k6 through the `LOAD_GENERATOR_VUS`
env var, which `script.js` reads directly via `__ENV` to set the HTTP
scenario's `vus`. It is deliberately not named `K6_VUS`: a `K6_VUS` env var
(or `--vus` flag) makes k6 discard the script's `scenarios` config entirely in
favor of a single implicit scenario, the same way `K6_DURATION`/
`K6_ITERATIONS`/`K6_STAGES` do - so none of those reserved names should ever
be set as a container env var here.

The browser scenario runs a single headless browser session alongside the HTTP
traffic, so it always runs one browser VU. It is opt-in via `K6_BROWSER_ENABLED`
(default off), since headless Chromium requires a relaxed pod security context
that most Kubernetes clusters don't grant by default. When enabled, Chromium's
executable path and launch args come from the `K6_BROWSER_EXECUTABLE_PATH` and
`K6_BROWSER_ARGS` env vars (comma-separated, no `--` prefix) rather than the
scenario's own `browser` options field, which k6 ignores for these.

## Agentic load

When the agent layer (`compose.agent.yaml`) is running, the HTTP scenario can
divert a share of its iterations to *agentic* traffic: instead of a native REST
call, the iteration POSTs a natural-language prompt to the agent's `/prompt`
endpoint (`http://${AGENT_ENDPOINT}:${AGENT_PORT}/prompt`). The agent is
OTel-instrumented, so the injected `traceparent` stitches k6 -> agent ->
MCP -> backend services into a single trace.
Prompts are read from [`prompts.json`](./prompts.json).

Two feature flags control this, both read live on every iteration (like
`loadGeneratorTraffic`), so changes take effect with **no restart**:

* `loadGeneratorNativeFraction` - the fraction of HTTP-scenario iterations that
  run native REST traffic, from `1.0` (100% native, the default) down to `0.0`
  (100% agentic). The agentic share is `1 - value`; e.g. `0.6` yields ~60%
  native and ~40% agentic iterations. On a flagd read error the script falls
  back to `1.0` (all-native) so an outage can't accidentally overload the agent.
* `loadGeneratorDisabledPromptClasses` - a comma-separated list of prompt
  classes to skip when choosing an agentic prompt. Empty (the default) enables
  every class. Classes are the atomic service names (`accounting`, `ad`,
  `cart`, `checkout`, `currency`, `email`, `fraud-detection`, `payment`,
  `product-catalog`, `quote`, `recommendation`, `shipping`) plus
  `multi-category` and `complex-scenarios`. If the list disables every class,
  the iteration falls back to native traffic.

## Note

* **Fraction of iterations, not throughput.** An agentic call includes an LLM
  round-trip and takes seconds, while a native call takes milliseconds. So at
  `0.5` roughly half the *iterations* are agentic, but they consume far more
  than half the wall-clock time.
