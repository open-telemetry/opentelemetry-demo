# oncall

The AI on-call agent for Incident Zero. Specs and rules live in `docs/hackathon/`.

## Demo UI

A single Streamlit page that shows the agent at work. Run it from the repo root:

```bash
pip install -r oncall/requirements.txt
streamlit run oncall/ui/app.py
```

It reads the same settings as the CLI (`oncall/.env`, see `.env.example`). With
`TELEMETRY_BACKEND=offline` it replays the `OFFLINE_SCENARIO` fixtures.

- **Header**: whether Prometheus, Jaeger and OpenSearch are reachable.
- **System health**: press Refresh to run `container_health` and
  `get_metrics(error_rate)`. Unhealthy rows are red; load-generator is a client
  and is always gray. Error rates only show for the services `get_metrics` ranks.
- **Alert**: describe the problem, optionally pick a service, press Investigate.
  The agent runs in the background and each tool call appears as it is logged.
- **Result**: the symptom summary, the Diagnosis and every cited evidence item,
  read verbatim from the run log.
- **Action**: Approve and Reject are disabled. The approval gate and Action API
  land with F19/F22; the UI never executes anything.
- **Sidebar**: every run in `RUNS_DIR`, newest first. Click one to replay it, which
  is also the fallback if a live run fails during the demo.
