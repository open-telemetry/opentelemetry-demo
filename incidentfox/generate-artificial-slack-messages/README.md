# Artificial Slack Incident Generator

Generate realistic Slack incident conversations that simulate on-call engineers responding to cascading failures in a microservices environment.

## Overview

This tool generates realistic incident scenarios based on the [Cascade Impact Analysis](../docs/cascade-impact-analysis.md) documentation. It creates:

- **Service-specific on-call channels** (e.g., `#cache-oncall`, `#checkout-oncall`)
- **Realistic alert messages** with proper formatting and severity
- **Human conversations** with back-and-forth discussions, theories, and debugging
- **Cross-team coordination** with @mentions when dependencies are discovered
- **Proper timelines** following the actual cascade of failures

## Directory Structure

```
generate-artificial-slack-messages/
├── README.md                      # This file
├── schema/
│   └── incident-schema.json       # JSON schema for incident definitions
├── templates/
│   └── message-templates.json     # Reusable message templates
├── scenarios/
│   ├── cache-failure.json         # Pre-defined incident scenarios
│   ├── payment-failure.json
│   └── ...                        # One for each failure mode
├── scripts/
│   ├── post-to-slack.py          # Posts messages to Slack
│   └── generate-scenario.py      # Generates new scenarios
└── lib/
    ├── scenario-generator.py      # Core generator logic
    └── slack-client.py            # Slack API wrapper
```

## Quick Start

### 1. Install Dependencies

```bash
cd incidentfox/generate-artificial-slack-messages
pip install slack-sdk python-dotenv
```

### 2. Configure Slack

Create a `.env` file:

```bash
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_WORKSPACE_ID=your-workspace-id
```

**Required Slack Bot Scopes:**
- `chat:write` - Post messages
- `chat:write.public` - Post to public channels
- `usergroups:read` - Read user groups (@mentions)

### 3. Run a Scenario

```bash
# Post a pre-defined cache failure scenario
python scripts/post-to-slack.py scenarios/cache-failure.json

# Generate and post a random incident
python scripts/generate-scenario.py --scenario cache-failure --post

# Dry run (preview messages without posting)
python scripts/post-to-slack.py scenarios/cache-failure.json --dry-run
```

## Scenario JSON Format

Each scenario is defined in JSON with the following structure:

```json
{
  "scenario_id": "cache-failure-001",
  "scenario_type": "cache-failure",
  "title": "Recommendation Cache Failure",
  "start_time": "2024-12-11T14:30:00Z",
  "services": {
    "recommendation": {
      "channel": "#recommendation-oncall",
      "oncall_group": "@recommendation-oncall",
      "role": "primary"
    },
    "product-catalog": {
      "channel": "#product-catalog-oncall",
      "oncall_group": "@product-catalog-oncall",
      "role": "affected"
    }
  },
  "timeline": [
    {
      "offset_seconds": 0,
      "type": "alert",
      "channel": "#recommendation-oncall",
      "severity": "warning",
      "title": "High Latency Detected",
      "details": "P95 latency increased from 50ms to 500ms",
      "metrics": {
        "p95_latency": "500ms",
        "p99_latency": "800ms",
        "error_rate": "0%"
      },
      "runbook": "https://wiki.company.com/runbooks/recommendation-latency"
    },
    {
      "offset_seconds": 10,
      "type": "message",
      "channel": "#recommendation-oncall",
      "user": "alice",
      "content": "Looking into this, checking the graphs",
      "thread_parent": 0
    }
  ]
}
```

## Message Types

### 1. Alert
Automated alert from monitoring system:
```json
{
  "type": "alert",
  "severity": "critical|warning|info",
  "title": "High CPU Usage",
  "details": "CPU usage exceeded threshold",
  "metrics": { "cpu": "95%" },
  "runbook": "url"
}
```

### 2. Message
Human engineer message:
```json
{
  "type": "message",
  "user": "alice",
  "content": "Checking the dashboards...",
  "thread_parent": 0  // Index of parent message for threading
}
```

### 3. Mention
Cross-team coordination:
```json
{
  "type": "mention",
  "user": "bob",
  "content": "Hey @cache-oncall, seeing issues downstream",
  "mentions": ["@cache-oncall"],
  "thread_parent": 0
}
```

### 4. Resolution
Incident resolution:
```json
{
  "type": "resolution",
  "user": "alice",
  "content": "Issue resolved. Cache is healthy now.",
  "metrics_after": { "p95_latency": "50ms" }
}
```

## Realistic Conversation Patterns

The generator uses these patterns to create realistic discussions:

### Pattern 1: Initial Investigation
```
[Alert] → 
[Engineer] "Looking into this" → 
[Engineer] "Checking metrics..." → 
[Engineer] "Seeing X in the dashboard"
```

### Pattern 2: Hypothesis Formation
```
[Engineer A] "Could this be Y?" →
[Engineer B] "I don't think so, because Z" →
[Engineer A] "Good point. What about W?" →
[Engineer B] "Let me check..."
```

### Pattern 3: Cross-Team Discovery
```
[Engineer A] "Seeing errors calling service X" →
[Engineer A] "@service-x-oncall Hey, seeing issues on your end?" →
[Service X Engineer] "Yes! We have an active incident" →
[Engineer A] "Ah, that explains it"
```

### Pattern 4: Mitigation
```
[Engineer] "I'm going to try fix X" →
[Engineer] "Applied the fix" →
[Wait 30 seconds] →
[Engineer] "Seeing improvement in metrics" →
[Engineer] "✓ Resolved"
```

## Available Scenarios

Based on [Cascade Impact Analysis](../docs/cascade-impact-analysis.md):

1. ✅ `cache-failure` - Recommendation cache fails → product-catalog overload
2. ✅ `payment-failure` - Payment errors → checkout failures → kafka backlog
3. ✅ `high-cpu` - Ad service CPU spike → frontend timeouts
4. ✅ `memory-leak` - Email service OOM → checkout email failures
5. ✅ `latency-spike` - Image provider slow → frontend page load degradation
6. ✅ `kafka-lag` - Message queue lag → accounting/fraud-detection delays
7. ✅ `catalog-failure` - Product catalog errors → multiple service failures
8. ✅ `service-unreachable` - Payment service down → complete checkout failure
9. ✅ `traffic-spike` - Load spike → system-wide degradation
10. ✅ `llm-rate-limit` - LLM rate limits → product-reviews fallback

## Configuration

### Service Mapping

Edit `lib/services.json` to customize service channels and teams:

```json
{
  "recommendation": {
    "channel": "#recommendation-oncall",
    "oncall_group": "@recommendation-oncall",
    "engineers": ["alice", "bob", "charlie"],
    "timezone": "America/Los_Angeles"
  }
}
```

### Personas

Edit `lib/personas.json` to define engineer personalities:

```json
{
  "alice": {
    "name": "Alice Chen",
    "style": "analytical",
    "response_time": "fast",
    "characteristics": ["checks metrics first", "asks clarifying questions"]
  },
  "bob": {
    "name": "Bob Smith",
    "style": "pragmatic",
    "response_time": "medium",
    "characteristics": ["suggests quick fixes", "references past incidents"]
  }
}
```

## Advanced Usage

### Generate Custom Scenario

```python
from lib.scenario_generator import ScenarioGenerator

generator = ScenarioGenerator()
scenario = generator.generate(
    scenario_type="cache-failure",
    start_time="2024-12-11T15:00:00Z",
    engineers={
        "recommendation": ["alice", "bob"],
        "product-catalog": ["charlie"]
    }
)

# Save to file
with open("scenarios/custom-cache-failure.json", "w") as f:
    json.dump(scenario, f, indent=2)
```

### Post with Delays

```bash
# Post messages with realistic delays
python scripts/post-to-slack.py scenarios/cache-failure.json --realtime

# Speed up (10x faster)
python scripts/post-to-slack.py scenarios/cache-failure.json --realtime --speed 10
```

### Batch Mode

```bash
# Post multiple scenarios throughout the day
python scripts/post-to-slack.py \
  --batch scenarios/cache-failure.json,scenarios/payment-failure.json \
  --interval 3600  # 1 hour between incidents
```

## Validation

Validate scenario JSON:

```bash
python scripts/validate-scenario.py scenarios/cache-failure.json
```

Checks:
- ✅ Timeline is chronologically ordered
- ✅ Thread references are valid
- ✅ Services match dependency graph
- ✅ @mentions reference valid oncall groups
- ✅ Metrics are realistic

## Examples

### Example 1: Cache Failure with Discovery

```
T+0s   [#recommendation-oncall] 🚨 Alert: High Latency
T+10s  [alice] Looking into this...
T+30s  [alice] P95 went from 50ms to 500ms. Cache hit rate is 0%!
T+45s  [bob] Cache failures in the logs. Restarting cache pods.
T+60s  [#product-catalog-oncall] 🚨 Alert: High CPU Usage  
T+70s  [charlie] What's going on? Seeing 10x traffic suddenly
T+80s  [charlie] Oh wait, all from recommendation service
T+90s  [charlie] @recommendation-oncall Hey are you having issues?
T+100s [alice] Yes! Cache is down, we're bypassing it
T+110s [charlie] That makes sense. We're handling it fine, just heads up
T+120s [bob] Cache is back up
T+130s [alice] ✓ Confirmed. Latency back to normal.
T+140s [charlie] ✓ Traffic returned to normal on our end too
```

### Example 2: Payment Service Unreachable

```
T+0s   [#checkout-oncall] 🔴 CRITICAL: Payment Service Unreachable
T+5s   [dave] On it. Health check failing.
T+10s  [dave] Service is returning no response. Timeout after 30s.
T+15s  [dave] @payment-oncall Payment service down?
T+20s  [emma] Not seeing any issues on our end. Let me check...
T+30s  [emma] Oh crap, feature flag enabled by mistake
T+35s  [emma] Disabling now
T+40s  [dave] Still timing out
T+45s  [emma] Try now, just disabled
T+50s  [dave] ✓ Health check passing. Monitoring...
T+60s  [dave] ✓ Checkout success rate back to 100%
```

## Tips for Realistic Scenarios

1. **Vary response times** - Not everyone responds immediately
2. **Include false starts** - Engineers may investigate wrong paths
3. **Add uncertainty** - "Maybe...", "Not sure but...", "Let me check..."
4. **Show debugging process** - Checking dashboards, reading logs, running queries
5. **Include metrics** - Reference actual numbers
6. **Cross-reference past incidents** - "Similar to last week's issue"
7. **Add human touches** - Typos, abbreviations, emojis
8. **Realistic timelines** - Investigation takes time, don't resolve instantly

## Contributing

To add a new scenario:

1. Create JSON in `scenarios/your-scenario.json`
2. Follow the schema in `schema/incident-schema.json`
3. Validate with `scripts/validate-scenario.py`
4. Test with `--dry-run` before posting to Slack
5. Update this README with the new scenario

## Troubleshooting

**Messages not posting:**
- Check Slack token scopes
- Verify channels exist
- Ensure bot is invited to channels

**@mentions not working:**
- Verify user groups exist in Slack
- Check group names match exactly (case-sensitive)

**Timeline seems off:**
- Check `offset_seconds` values
- Ensure chronological order
- Use `--dry-run` to preview

## Resources

- [Slack API Documentation](https://api.slack.com/)
- [Cascade Impact Analysis](../docs/cascade-impact-analysis.md)
- [Incident Scenarios](../docs/incident-scenarios.md)
