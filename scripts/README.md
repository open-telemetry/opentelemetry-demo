# Scripts

Helper scripts for the Incident Zero hackathon agent.

## faultctl.py — Inject and reset faults

```bash
# List all available flags and their current state
python scripts/faultctl.py list

# Show only currently active faults
python scripts/faultctl.py status

# Inject a fault
python scripts/faultctl.py inject paymentFailure --variant "100%"
python scripts/faultctl.py inject cartFailure --variant "50%"
python scripts/faultctl.py inject adHighCpu
python scripts/faultctl.py inject emailMemoryLeak --variant "1000x"
python scripts/faultctl.py inject kafkaQueueProblems --variant "3sec"

# Reset ALL faults back to off
python scripts/faultctl.py reset
```

## capture_bundle.py — Snapshot telemetry into a bundle

Run this WHILE a fault is active (after injecting and waiting 2-3 minutes).

```bash
# Capture a bundle (requires Docker stack running)
python scripts/capture_bundle.py --name incident_01_payment_failure

# Skip specific sources if they are unavailable
python scripts/capture_bundle.py --name my_bundle --skip-logs
```

### Prerequisites for capture_bundle.py
- Docker stack must be running
- Prometheus at localhost:9090
- Jaeger at localhost:16686
- OpenSearch at localhost:9200 (optional)

Override endpoints with env vars:
```bash
PROMETHEUS_URL=http://localhost:9090 python scripts/capture_bundle.py --name test
```

## Typical workflow to build all 10 bundles

```bash
# 1. Start the demo
docker compose -f compose.yaml -f compose.full.yaml -f compose.observability.yaml up --no-build -d

# 2. For each fault:
python scripts/faultctl.py inject paymentFailure --variant "100%"
# wait 3 minutes...
python scripts/capture_bundle.py --name incident_01_payment_failure
python scripts/faultctl.py reset
# wait 1 minute for recovery...

# 3. Repeat for each fault in bundles/README.md
```
