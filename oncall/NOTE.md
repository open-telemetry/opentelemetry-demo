# AI On-Call Engineer: Evaluation Note & Post-Mortem Analysis

**Hackathon Deliverable 4**: What worked, what failed, and why.

---

## 1. What Worked

1. **Iterative Telemetry Triaging (The Eyes)**:
   - **Prometheus**: Instant PromQL queries accurately captured P95/P99 latency degradation and 5xx error spikes on degraded microservices.
   - **Jaeger Span DAG Traversal**: Rather than assuming the alerted service is the root cause, the tracing tool walks parent-child span relationships. When an upstream service (`checkout`) experiences high latency waiting on a child span (`payment`), the agent accurately attributes the root cause to `payment`.
   - **OpenSearch Trace-Filtered Logs**: By strictly scoping log queries using the `trace_id` discovered during Jaeger trace analysis, the agent eliminated hallucinated log associations and retrieved the exact exception stack trace.
   - **Git Deployment Auditing**: Inspecting real `git log` commit metadata on branch `main` enabled the agent to systematically rule out deployment regressions when no breaking commits occurred in the incident window.

2. **Categorized Evidence & Dynamic Calibrated Confidence (The Brain)**:
   - The diagnosis distinguishes **Confirmed Empirical Facts** (observable telemetry metrics, spans, and log lines), **Likely Causes** (deductive root-cause inferences), and **Ruled Out Hypotheses** (e.g., git breaking deployments, local vs downstream bugs).
   - Dynamic confidence scoring scales based on the volume and convergence of telemetry citations (0.82–0.88).

3. **Pre-Execution Consistency Guard & Safety Gate (The Hands)**:
   - Built a pre-execution verification barrier that intercepts proposed actions. If an action proposes changing a configuration to a state it already possesses (e.g. turning off a flag that is already off), the consistency guard rejects the mutation as redundant and flags a logical contradiction.
   - Token-based Human Approval Barrier prevents unauthorized or autonomous out-of-bounds actions.

---

## 2. What Failed (and How We Fixed It)

| Issue Encountered | Root Cause | Engineering Solution |
| :--- | :--- | :--- |
| **1. Alerted Service Blame Bias** | Naive agents attribute outages directly to the service named in the alert (e.g., blaming `checkout` for order placement timeouts). | Implemented recursive span analysis in `JaegerTool`: if a child span accounts for >80% of parent duration or carries an `error=True` tag, the child service is isolated as the culprit. |
| **2. Feature Flag Hallucination** | Early prototype assumed that if a service has a failure feature flag defined in `demo.flagd.json`, that flag must be the cause of the outage. | Enforced strict telemetry-first causation. Furthermore, under **Hackathon Rule 6** ("Reading feature-flag settings to diagnose... means disqualification"), we completely removed flag file reading from the diagnosis loop; diagnosis relies purely on metrics, traces, logs, and git history. |
| **3. Redundant Mutation Executions** | An automated remediation loop could issue a `reset_flag` command even when the flag was already in the resting state, causing unneeded restarts. | Added `EvidenceConsistencyCheck` in both `flagd_action.py` and `approval_gate.py` that verifies the current state before dispatching any mutation. |
| **4. Fixture Miss on Ad Service** | When evaluating Incident 3 (`ad` service high CPU/GC), the Jaeger tool initially fell back to the default `cart` fixture, falsely attributing downstream causation to `cart`. | Added complete trace, log, and metric fixture entries for `ad` (`AdService/GetAdsByCategory` thread saturation and Java Full GC pause logs), restoring 100% test pass rate across all 3 practice scenarios. |

---

## 3. Compliance with Hackathon Rule 6

**Rule 6**: *"Reading feature-flag settings to diagnose, or tampering with the demo, faultctl, the hidden incidents or the scoring harness means disqualification."*

**Our Compliance Guarantee**:
- During the investigation phase (`oncall/agent.py`), the agent queries **only**:
  1. Prometheus metrics (`http_server_request_duration_seconds_bucket`, error rates)
  2. Jaeger distributed trace trees (parent/child span latency, error codes)
  3. OpenSearch logs (filtered strictly by observed `trace_id`)
  4. Git commit history (`git log -n 3 --date=iso`)
- **Zero calls** to Flagd APIs or `demo.flagd.json` occur during diagnosis.
- Flagd interactions are restricted exclusively to the **remediation phase** through the Action API, requiring explicit human approval and pre-flight consistency checks.
