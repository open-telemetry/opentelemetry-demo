# Observability Agent

## Prerequisites

- VAST Kafka Broker with three topics
  - otel-logs
  - otel-traces
  - otel-metrics
- VAST DB bucket/schema access credentials

## Instructions

- Deploy [otel demo](https://opentelemetry.io/ecosystem/demo/)
- Replace the otel demo src/otel-collector/otelcol-config.yml with [otelcol-config.yml](./otelcol-config.yml)
- Modify the kafka broker name in `otelcol-config.yml`
- Restart otel demo
- Run the script [otel_ingester.py](./otel_ingester.py) using nohup/screen/tmux

## Connect Trino to VAST DB

- Connect Trino to VAST DB

## Diagnostic Chat Tool

An interactive LLM-powered chat interface for support engineers to diagnose issues by querying observability data via Trino.

### Features

- Natural language queries like "ad service is slow" or "show me errors in checkout"
- Iterative diagnosis - the LLM runs multiple queries to find root causes
- Correlates logs, metrics, and traces automatically
- Full SQL support via Trino (JOINs, GROUP BY, aggregations, etc.)

### Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Set environment variables:

```bash
export ANTHROPIC_API_KEY=your_api_key
export TRINO_HOST=trino.example.com
export TRINO_PORT=443
export TRINO_USER=your_user
export TRINO_CATALOG=vast
export TRINO_SCHEMA=otel
```

### Usage

```bash
python diagnostic_chat.py
```

### Example Queries

| Query | What it does |
|-------|--------------|
| "ad service is slow" | Investigates latency in the ad service |
| "what errors occurred in the last hour?" | Finds recent errors across all services |
| "show me failed checkouts" | Finds checkout failures with traces |
| "trace request abc123" | Shows full trace for a specific request |
| "why is the frontend timing out?" | Diagnoses timeout issues |

### Commands (CLI)

- `/clear` - Clear conversation history
- `/help` - Show help message
- `/quit` - Exit the chat

### Web UI

A browser-based interface with real-time system status monitoring.

```bash
python web_ui.py
```

Then open http://localhost:5000 in your browser.

**Features:**
- Chat interface for diagnosing issues
- Real-time service health dashboard
- Database status monitoring
- Recent errors feed
- Query result visualization
- Predictive alerts panel (see below)

## Predictive Maintenance Alerts

An automated service that monitors telemetry data and generates predictive alerts for potential issues before they become critical failures.

### Features

- **Fully automated** - no user input required, runs continuously in the background
- **Self-learning baselines** - computes statistical baselines from historical data
- **Multiple detection methods**:
  - Z-score anomaly detection for error rates, latency, throughput
  - Service down detection (no telemetry for 1+ hour)
  - Configurable thresholds for warning/critical severity
- **Auto-resolution** - alerts automatically resolve when conditions normalize
- **Web UI integration** - alerts panel in sidebar, click to investigate

### Alert Types

| Alert Type | Description |
|------------|-------------|
| `error_spike` | Error rate exceeds baseline or threshold |
| `latency_degradation` | P95 latency significantly above baseline |
| `throughput_drop` | Request volume dropped significantly |
| `service_down` | No telemetry received for extended period |

### Setup

The service requires the same Trino connection as the diagnostic chat:

```bash
export TRINO_HOST=trino.example.com
export TRINO_PORT=443
export TRINO_USER=your_user
export TRINO_PASSWORD=your_password
export TRINO_CATALOG=vast
export TRINO_SCHEMA=otel
```

### Running the Service

```bash
python predictive_alerts.py
```

Run alongside `otel_ingester.py` using nohup, screen, or tmux for production use.

### Configuration

All settings are configurable via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DETECTION_INTERVAL` | 60 | Seconds between anomaly detection runs |
| `BASELINE_INTERVAL` | 3600 | Seconds between baseline recomputation |
| `BASELINE_WINDOW_HOURS` | 24 | Hours of historical data for baselines |
| `ANOMALY_THRESHOLD` | 3.0 | Z-score threshold for anomaly detection |
| `ERROR_RATE_WARNING` | 0.05 | Error rate (5%) that triggers warning |
| `ERROR_RATE_CRITICAL` | 0.20 | Error rate (20%) that triggers critical |
| `MIN_SAMPLES_FOR_BASELINE` | 10 | Minimum data points required for baseline |
| `ALERT_COOLDOWN_MINUTES` | 15 | Cooldown after resolution before re-alerting |

### Automated Root Cause Analysis

When alerts are created, the service can automatically investigate using an LLM to find the root cause. This requires an Anthropic API key.

**Additional environment variables for investigations:**

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | - | API key for LLM investigations (required) |
| `INVESTIGATION_MODEL` | claude-3-5-haiku-20241022 | Model to use (Haiku recommended for cost) |
| `INVESTIGATION_MAX_TOKENS` | 1000 | Max response tokens per investigation |
| `MAX_INVESTIGATIONS_PER_HOUR` | 5 | Rate limit for API cost control |
| `INVESTIGATION_SERVICE_COOLDOWN_MINUTES` | 30 | Cooldown per service between investigations |
| `INVESTIGATE_CRITICAL_ONLY` | false | Only investigate critical severity alerts |

**How it works:**
1. When a new alert is created, the investigator checks rate limits
2. If within limits, it queries recent traces/logs/errors for the service
3. The LLM analyzes the data and identifies the root cause
4. Results are stored in `alert_investigations` table
5. Web UI displays the root cause summary with the alert

### Database Tables

The service creates/uses four tables for storing state:

- `service_baselines` - Computed statistical baselines per service/metric
- `anomaly_scores` - Historical anomaly detection results
- `alerts` - Active and resolved alerts
- `alert_investigations` - LLM-generated root cause analysis

Create tables using the DDL in `ddl.sql`.

### Web UI Integration

When running, alerts appear in the sidebar:
- Badge shows count of active alerts (color indicates severity)
- Click any alert to automatically investigate via diagnostic chat
- Alerts auto-refresh with the rest of the dashboard

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/alerts` | GET | List alerts (filter by status, severity, service) |
| `/api/alerts/<id>/acknowledge` | POST | Acknowledge an alert |
| `/api/alerts/<id>/resolve` | POST | Manually resolve an alert |
| `/api/alerts/history` | GET | Historical alert trends |
| `/api/baselines` | GET | Current service baselines |
| `/api/anomalies` | GET | Recent anomaly scores |

## Testing with Simulated Failures

To test the diagnostic capabilities, you can simulate infrastructure failures in the OpenTelemetry demo using the provided script.

### Using the Simulation Script

```bash
# From the opentelemetry-demo directory:
cd /path/to/opentelemetry-demo

# Copy the script or run from the observability_agent directory
./scripts/simulate_failure.sh <action> <target>

# Actions: block, unblock, status
# Targets: postgres, redis, kafka, or any docker compose service name
```

### Examples

```bash
# Block PostgreSQL (gracefully blocks connections)
./scripts/simulate_failure.sh block postgres

# Check status
./scripts/simulate_failure.sh status postgres

# Restore PostgreSQL
./scripts/simulate_failure.sh unblock postgres

# Pause Redis (simulates timeout/hang)
./scripts/simulate_failure.sh block redis

# Stop any service completely
./scripts/simulate_failure.sh block checkoutservice
```

### Manual Testing

You can also manually simulate failures:

```bash
# PostgreSQL - block connections
docker compose exec postgresql psql -U root -d otel -c "REVOKE CONNECT ON DATABASE otel FROM PUBLIC;"

# PostgreSQL - restore
docker compose exec postgresql psql -U root -d otel -c "GRANT CONNECT ON DATABASE otel TO PUBLIC;"

# Any service - stop/start
docker compose stop <service>
docker compose start <service>

# Any service - pause/unpause (simulates hang)
docker compose pause <service>
docker compose unpause <service>
```

### What to Look For

After simulating a failure, wait 30-60 seconds for effects to propagate, then ask the diagnostic chat:
- "Show me errors in the last 5 minutes"
- "What's wrong with the system?"
- "Diagnose the frontend issues"

The AI should follow the SysAdmin diagnostic process:
1. Check infrastructure health first (databases, hosts, services)
2. Look for connection errors, timeouts, and missing telemetry
3. Trace errors through the dependency chain
4. Identify the root cause component
