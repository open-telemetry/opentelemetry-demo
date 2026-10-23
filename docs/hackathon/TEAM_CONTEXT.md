# Team Context Prompt — "Incident Zero: Build an AI On-Call Engineer"

> Paste this whole file into your coding agent (Claude, Cursor, Copilot chat, etc.) as project context before you start working, or read it end to end yourself. It is the single source of truth for what we are building, the rules, and how we'll be scored.

---

## 0. Your role (for the AI assistant reading this)

You are helping a member of a 5-person student team at the **Bosch "Incident Zero" AI hackathon at PES University**. Help them design, write, and debug code for the project described below. Follow these rules:

- **Respect the hackathon rules in Section 6 at all times.** If a request would break one (for example reading feature-flag settings to "cheat" a diagnosis, or changing the demo outside the Action API), refuse and explain why.
- Every team member must be able to **explain and modify** any code they commit. Prefer simple, readable code over clever code, and explain what you write.
- Never invent telemetry, evidence, or API responses. If you don't know how the starter kit's API works, say so and ask the user to paste the relevant README or code.
- Keep work inside the user's assigned module (Section 9) unless asked otherwise, and keep interfaces stable so teammates' code keeps working.

---

## 1. The theme in one line

**Agentic AI for IT Operations: from alert to a safe, approved fix.**

## 2. Problem statement

Build an **AI On-Call Engineer**: an agent that responds to a production incident in a cloud-native application, **investigates it using real tools**, **identifies the root cause with evidence**, and **resolves it safely with human approval**.

Why: when production breaks, an on-call engineer gets paged (often at 2 a.m.), reads logs, checks dashboards, looks at recent deploys, guesses the cause, and applies a fix under pressure. Most of that first hour is searching and correlating. Our agent automates that first hour.

The agent must:
1. Receive an alert.
2. Decide **which tools to call and in what order**.
3. Reason over **logs, metrics, traces, and deployment history**.
4. Name the root cause **with the evidence behind it**.
5. Propose a fix from an **approved runbook**.
6. **Ask a human for approval.**
7. Apply it and **verify the system actually recovered**.

**Guiding principle (this is literally how we're judged):**
> A good agent is not the one that always acts. It is the one that acts when it has evidence, and says "I am not sure, here is what I found" when it does not.
> **Escalating to a human with findings when not confident scores BETTER than a confident wrong fix.**

---

## 3. The application we operate on

**OpenTelemetry Demo ("Astronomy Shop")** — https://github.com/open-telemetry/opentelemetry-demo

- An open-source microservices e-commerce store written in about a dozen languages, running **on our own laptops via Docker Compose** (Kubernetes optional).
- Services include: frontend, cart, checkout, payment, product catalog, recommendation, ad, shipping, email, currency, quote, fraud detection, accounting, plus Kafka, a cache (Valkey/Redis) and a Postgres database, depending on version.
- A **Locust load generator** produces constant realistic traffic.
- It already emits **traces, metrics, and logs** from every service through the **OpenTelemetry Collector**, with bundled viewers (typically Jaeger for traces, Prometheus/Grafana for metrics, OpenSearch for logs — verify against the version in the starter kit).
- It has **built-in failure switches managed by flagd** (feature flags) that cause realistic failures.

### What the organisers provide (starter kit)

| Provided | What it is | Notes |
|---|---|---|
| OpenTelemetry Demo | The microservices store + Locust, run with Docker Compose | Open source |
| Telemetry | Traces, metrics, logs through the OTel Collector + bundled viewers | Comes with the demo |
| Failure flags | Built-in realistic failure switches, managed by flagd | **Our agent may NOT read these to diagnose** |
| `faultctl` | CLI to inject a practice incident (a flag or an infrastructure fault) and reset everything | For us humans to set up test scenarios |
| **Action API** | **The ONLY allowed way for our agent to change the system**: restart a service, toggle a feature flag, throttle the load generator, scale a service (Kubernetes only). Every call is logged | |
| Offline incident bundles | Recorded telemetry for every practice incident, for laptops that can't run the full demo | Great for developing the reasoning layer without Docker |
| LLM access | An API key with a spend limit; open-source/local models also allowed | Watch token spend |
| Template repository | Agent skeleton, **required output format (JSON schema)**, README template, team form | **We must fork this.** The JSON schema is mandatory for incident reports |

---

## 4. Incidents the agent may face

**10 practice incidents are published at kickoff.** The final evaluation uses **unseen incidents**, including infrastructure faults and **combinations** of faults. So the agent must **reason from telemetry**, not memorise the 10 answers and not peek at flag settings.

**Application faults (demo's built-in flags):**
- Payment service fails when charging
- Cart service fails intermittently
- Product catalog fails for one specific product
- Memory leak in the recommendation service from a runaway cache
- High CPU or heavy garbage collection in the ad service
- Traffic flood on the homepage

**Infrastructure faults (injected by organisers):**
- A service container is stopped or keeps restarting
- The cache or a database becomes unavailable
- Network latency or packet loss between two services
- A service starved of CPU or memory

---

## 5. What our solution must do (the 7-step loop)

1. **Detect** — Receive an alert (error-rate or latency threshold on the demo's metrics) and start investigating automatically.
2. **Investigate with tools** — Tools to query **traces, metrics, logs, and container health**. The agent decides which tool to call next based on what it has found so far, **rather than pasting all the data into one prompt**.
3. **Diagnose with evidence** — Name the **failing component** and the **cause**, with a **confidence level** and the **exact traces, log lines, or metric values** that support it. Evidence must exist in the data; **invented evidence is penalised.**
4. **Propose a safe fix** — Pick a remedy **only from the allowlisted runbook actions in the Action API** (restart service, toggle feature flag, throttle load generator, scale service on K8s), with a short reason.
5. **Ask for human approval** — Show the diagnosis and plan to a human and wait. **Nothing changes without an explicit yes.** Provide a **dry-run mode** and a **kill switch**.
6. **Act and verify** — Execute the approved action, then check health metrics to confirm recovery. **If not recovered, roll back and escalate.**
7. **Report** — Short incident report: timeline, root cause, evidence, action taken, and what would prevent a repeat. Must follow the **provided JSON schema** plus a readable form.

### Optional stretch goals (only after the core loop works)
1. **Incident memory** — reuse earlier incident reports to diagnose repeats faster.
2. **Reviewer agent** — a second agent tries to disprove the diagnosis before the human sees it.
3. **Calibrated confidence** — show stated confidence matches how often the agent is actually right on the practice set.
4. **Chat-style approval** — approve/reject from a simple chat UI or dashboard.
5. **Prevention** — after fixing, suggest a code, config, or alerting change that would stop recurrence.

---

## 6. Rules (non-negotiable — breaking 4 or 6 can disqualify us)

1. Teams of 5. **All code is written during the event, from 09:15; commits before then are not allowed.**
2. Open-source libraries and agent frameworks are allowed. **AI coding assistants are allowed if declared in the team form**; every member must be able to explain and change the code they submit.
3. **Every team member must commit code** (use your own git identity).
4. **The agent changes the demo ONLY through the Action API, and ONLY after human approval.**
5. Mentors help us get unblocked; they do **not** write code for us. No outside help.
6. **Reading feature-flag settings to diagnose, or tampering with the demo, `faultctl`, the hidden incidents, or the scoring harness = disqualification.** (Never let the agent query flagd / the flag config / the flagd UI as a diagnostic tool.)
7. **Be honest about what does not work.** Stating a limitation costs nothing; hiding a failure in the demo loses points.

---

## 7. Scoring (out of 100)

| Part | Points |
|---|---|
| Checkpoint 1: Eyes | 10 |
| Checkpoint 2: Brain | 20 |
| Checkpoint 3: Hands | 20 |
| **Checkpoint 4: Hidden test (unseen incidents, scored automatically)** | **30** |
| Judges: safety & human approval, agent design & tool use, explainability, testing & honesty, demo | 20 |

**Plus individual assessment:** each student is assessed individually through the checkpoints and a short one-to-one technical conversation. Know your module and the overall architecture.

The hidden test is the biggest single chunk → the agent must generalise and must output the JSON schema correctly every time.

---

## 8. Timeline & checkpoints

### Day 1 (11:30 – 18:45)
| Time | Milestone | Expected outcome |
|---|---|---|
| 11:30–12:00 | Kickoff | Problem reveal, starter kit walkthrough, rules |
| 12:00–13:00 | Setup | OTel demo running with load; `faultctl` injects and resets an incident; LLM key works; repo forked; all members have committed |
| 13:00 | **Checkpoint 0: Setup** | Mentor confirms setup |
| 13:00–15:30 | The agent can see | Tools for logs, metrics, traces, deploy history; agent summarises symptoms of one practice incident; 1-page architecture sketch |
| 15:30 | **Checkpoint 1: Eyes** | Live run on one practice incident + the sketch |
| 15:30–18:30 | The agent can diagnose | Root cause with evidence and confidence; output in the JSON schema |
| 18:30 | **Checkpoint 2: Brain** | Correct diagnosis on ≥3 practice incidents chosen by the mentor |
| 18:45 | Day 1 wrap-up | Code state saved; mentors review |

**Minimum by end of Day 1:** an agent that uses tools and correctly diagnoses practice incidents with real evidence.

### Day 2 (09:00 – 18:45)
| Time | Milestone | Expected outcome |
|---|---|---|
| 09:00–09:30 | Day 2 alignment | Review Day 1 feedback |
| 09:30–12:00 | The agent can act safely | Allowlisted action proposed; approval gate; execute; recovery verified; dry run and kill switch; incident report generated |
| 12:00 | **Checkpoint 3: Hands** | One full run, alert → verified recovery, with the action log |
| 12:00–13:30 | Harden, document, prep | No new features; fix bugs; clean run from scratch; finish README, evaluation note, team form |
| 13:30–14:00 | Final verification | Final push; verify schema compliance and deliverables |
| **14:00** | **CODE FREEZE — hard cutoff** | Later commits are ignored |
| 14:00–15:30 | **Checkpoint 4: Hidden test** | Organisers run unseen incidents on our setup; automated scoring |
| 15:30–16:30 | Evaluation & elimination | Qualifying teams selected |
| 16:30–18:45 | Finalist demos & interviews | 5-min live demo + 3 min Q&A; one-to-one technical conversations |

**Minimum by code freeze:** a full loop on at least one incident (diagnose, approve, act, verify, report), a working kill switch, and all deliverables in the repo.

> ⚠️ Slide inconsistencies to confirm with a mentor: one slide says "16:30 code freeze", the milestones say **Day 2, 14:00** — treat **14:00** as the real deadline. One slide says "teams of 5", another says "all three members must commit" — assume **everyone commits**.

---

## 9. Deliverables (in our repo by code freeze; no demo video, we demo live)

| Deliverable | Details |
|---|---|
| Source code | Repo forked from the template, with a README covering setup, how to run, **how the approval gate and kill switch work**, and known limitations |
| Architecture overview | One page: components, tools the agent uses, how it decides, safety controls (a photo of a whiteboard sketch is fine) |
| Incident reports | Reports produced by our agent for the practice incidents it handled, **in the provided JSON schema** plus readable form |
| Evaluation note | Which practice incidents our agent got right and wrong in our own testing, and why |
| Team form | Team name, members, who built which part, tools and AI models used (**including AI coding assistants**), third-party libraries |

---

## 10. Proposed architecture (design architect's draft — adjust after we see the template repo)

```
 Alert (threshold on Prometheus metrics)
        │
        ▼
 ┌──────────────────────────────────────────────┐
 │  ORCHESTRATOR (agent loop, LLM tool-calling) │
 │  state: alert, findings[], hypotheses[],     │
 │         tool_budget, confidence              │
 └──────┬───────────────────────────────┬───────┘
        │ read-only tools               │ proposal
        ▼                               ▼
  ┌───────────────┐              ┌──────────────────┐
  │ get_metrics   │ PromQL       │ SAFETY LAYER     │
  │ search_traces │ Jaeger API   │ - allowlist check│
  │ search_logs   │ OpenSearch   │ - dry-run mode   │
  │ container_    │ docker ps /  │ - kill switch    │
  │   health      │ inspect/stats│ - approval gate  │
  │ deploy_history│ starter kit  │   (CLI → chat UI)│
  └───────────────┘              └────────┬─────────┘
                                          │ only after explicit "yes"
                                          ▼
                                    Action API ──► Verify (re-query metrics)
                                                    │ recovered? ─ no ─► rollback + escalate
                                                    ▼ yes
                                              Report (JSON schema + markdown)
```

Design principles:
- **Iterative investigation, not data dumping.** Each tool returns a compact, summarised result (top error spans, top log lines, metric deltas vs. baseline), never raw megabytes. The LLM picks the next tool.
- **Evidence is referenced, not paraphrased.** Every claim in the diagnosis cites a concrete artefact the tool returned (trace ID + span, exact log line + timestamp, metric query + value). Validate in code that cited evidence actually appears in tool outputs before reporting — this directly protects against the "invented evidence" penalty.
- **Confidence + escalation are first-class.** If confidence is below a threshold, or evidence is contradictory, or several components look broken, the agent escalates with findings instead of acting.
- **Safety in code, not in the prompt.** The allowlist, approval gate, dry run, and kill switch are enforced by plain Python, so the LLM physically cannot call the Action API without approval.
- **Never touch flagd.** No tool reads flag state. Toggling a flag back off is allowed **only as an Action API remediation after approval**, not as a way to read answers.
- **Develop against offline incident bundles** so reasoning work isn't blocked on Docker.

Suggested module split (5 people):
1. **Platform & tooling** — demo + `faultctl` setup, alert detector, `container_health`, `deploy_history`.
2. **Telemetry tools** — `get_metrics` (Prometheus), `search_traces` (Jaeger), `search_logs`, each with compact summaries and baseline comparison.
3. **Agent brain** — orchestrator loop, system prompt, hypothesis tracking, confidence and escalation logic, JSON-schema output + validation.
4. **Safety & action** — Action API client, allowlist, approval gate, dry run, kill switch, action log, verify + rollback.
5. **Eval, reports & docs** — runs all 10 practice incidents (live and offline), scoring script, incident reports, evaluation note, README, architecture page, team form; owns the demo script.

Shared conventions:
- Language: Python 3.11+ (unless the template dictates otherwise).
- Every tool is a function with a typed signature, a docstring the LLM sees, and a JSON-serialisable return value.
- Small PRs, commit often, each person with their own git identity.
- Log every LLM call and tool call to a run log — it doubles as our "timeline" for reports and our evidence for the judges.

---

## 11. Definition of done (what "good" looks like for judges)

- Agent investigates step by step, choosing tools based on findings.
- Diagnosis names component + cause + confidence + real, verifiable evidence.
- Proposes only allowlisted actions, with a reason.
- Waits for explicit human approval; dry run and kill switch work and are documented.
- Verifies recovery with metrics; rolls back and escalates if not recovered.
- Writes a schema-valid report every time.
- Says "I'm not sure, here's what I found" when evidence is weak.
- README and evaluation note honestly state what works and what doesn't.
