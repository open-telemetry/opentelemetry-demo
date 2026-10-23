# Incident Zero: architecture (Day 1)

An AI on-call engineer for the OpenTelemetry Demo. It is given a symptom, investigates with
read-only tools, and proposes a root cause with evidence and a confidence. Day 1 is read-only
and ends at a **candidate** diagnosis; validation, confidence caps, escalation and reports are
planned, not built.

```mermaid
flowchart TD
    subgraph DEMO["OpenTelemetry Demo (running)"]
        SVC["~20 services + load generator"]
    end
    SVC --> PROM["Prometheus: metrics"]
    SVC --> JAEG["Jaeger: traces"]
    SVC --> OS["OpenSearch: logs"]
    SVC -.-> DOCK["Docker engine: container state"]

    PROM & JAEG & OS & DOCK --> TOOLS["tools/: read-only<br/>container_health, query_metrics, query_traces,<br/>query_logs, deploy_history"]
    TOOLS --> SAN["sanitiser<br/>flag data removed"]
    SAN --> LEDGER["evidence ledger<br/>every result gets an ID: C1, M1, T1, L1, D1"]
    LEDGER --> VIEW["compact view<br/>subset of the ledger entry, strings verbatim"]
    VIEW --> LOOP["oncall/loop.py<br/>LLM picks the next tool<br/>step, token and repeat limits"]
    LOOP -->|"tool call"| TOOLS
    LOOP --> CAND["candidate diagnosis<br/>reports/runs/ID/candidate.json"]
    LEDGER --> SUM["symptom summary<br/>built from the ledger"]

    CAND -.-> VAL["validator<br/>quotes must match the ledger exactly"]
    VAL -.-> CONF{"confidence caps<br/>and threshold"}
    CONF -.->|"high"| DIAG["diagnosis report<br/>json + md"]
    CONF -.->|"low"| ESC["escalation<br/>findings, no guess"]
    DIAG -.-> ACT["Action API + human approval<br/>Day 2"]

    subgraph DEV["dev/: never imported by the agent"]
        FC["faultctl"] -->|"inject / reset"| SVC
        FC --> GT["tests/ground_truth.md"]
    end

    classDef built fill:#d9f2d9,stroke:#2b7a2b,color:#000;
    classDef planned fill:#fff,stroke:#999,stroke-dasharray: 5 4,color:#555;
    class TOOLS,SAN,LEDGER,VIEW,LOOP,CAND,SUM,FC,GT built;
    class VAL,CONF,DIAG,ESC,ACT planned;
```

Solid green = built and tested. Dashed grey = planned (P6 and Day 2), not in the code yet.

## Components

| Part | Where | What it does |
|---|---|---|
| Tools | `tools/` | Five read-only functions. Each returns one result shape with three states: `data`, `no_data`, `backend_error`. An error or an empty answer is never reported as healthy. |
| Sanitiser | `tools/sanitize.py` | Removes feature-flag data from every result before anyone sees it. The only file that names the flag service. |
| Ledger | `tools/ledger.py` | Stores each sanitised result under an ID (`C1`, `M2`, ...). Saved as `ledger.json` with every run. |
| Tool box | `oncall/toolbox.py` | Turns each tool's typed signature into a JSON schema, checks the model's arguments, and builds the compact view the model is shown. |
| Loop | `oncall/loop.py` | The tool-calling loop and its budgets. |
| LLM adapter | `oncall/llm.py` | One interface over the Anthropic SDK (or any OpenAI-compatible one). Reports token usage. |
| Prompt | `oncall/prompts.py` | Generic on-call guidance. No faults, flags or service behaviours. |
| CLI | `oncall/investigate.py` | `python -m oncall.investigate [--summary]` |
| Fault injector | `dev/faultctl/` | Creates practice incidents and logs ground truth. Separate package, never imported by `oncall/` or `tools/`. |

## The tools

| Tool | Source | Shows |
|---|---|---|
| `container_health` | Docker | Status, health, restarts, exit code, OOM, CPU, memory. The only way to see a stopped container. |
| `query_metrics` | Prometheus | Per-service request rate, error rate, p95 latency, top erroring spans. |
| `query_traces` | Jaeger | Real trace IDs, root service, and the deepest erroring span (where an error starts). |
| `query_logs` | OpenSearch | Top error lines, verbatim, grouped, with counts and first/last seen. |
| `deploy_history` | Docker | Container start and restart times. |

## How the agent decides

1. The model starts with the symptom text and the tool list. Nothing is pre-loaded.
2. Each turn it picks one tool and arguments. The loop runs it, stores the full result in the ledger, and shows the model a **compact view**: counts and only the abnormal rows, with every string and number copied unchanged from the ledger entry.
3. The next tool is chosen from the findings so far. The step list records each call, a one-line finding built from the result, and the ledger ID.
4. The model ends by calling `submit_diagnosis`: component, cause, stated confidence, evidence (ledger ID plus an exact quote), alternatives and limitations. "unknown" with low confidence is a valid answer.
5. Limits: 10 tool calls, 60,000 tokens (input + output), a small token cap per reply, and a stop on an identical repeated call. When a limit is hit, the model is asked once to conclude from what it has. If it cannot, the candidate is an explicit `unknown` with confidence 0 and the reason, never an invented diagnosis.

## Safety controls

| Control | Status |
|---|---|
| Read-only: tools only run queries and `docker ps`, `inspect`, `stats`. There is no tool that changes anything. | Built |
| Flag isolation: the sanitiser strips flag attributes, flag-evaluation spans and the flag services' logs, metrics and containers. Tests scan tool output and everything sent to the model for flag names. | Built |
| The agent never sees the injected incident: the symptom is generic, `oncall/` cannot import `dev/` (tested), and the run ID is generated by the run. | Built |
| Evidence ledger: every result the model can quote is stored with an ID. | Built |
| Budgets: tool calls, tokens, repeats, LLM timeouts and malformed answers all end in a recorded partial result. | Built |
| Validator: every cited ID must exist and every quote must match the ledger exactly. | Planned (P6) |
| Confidence caps and escalation to a human below a threshold. | Planned (P6) |
| Action API, dry run, kill switch and human approval before any change. | Planned (Day 2) |

## Known limits

- The candidate is **not validated**. The model's quotes are not yet checked against the ledger.
- The symptom summary is built from the ledger without a second model call. It lists what the tools showed and does not name a cause.
- `deploy_history` is only container start times. After `make start` every container looks recently started, so it says little.
- Token counts for the budget come from the provider; cache reads count in full.
