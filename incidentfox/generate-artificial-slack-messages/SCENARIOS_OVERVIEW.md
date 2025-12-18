# Scenarios Overview

## Total: 57 Alert Scenarios

### Intensive Discussion Incidents (7 scenarios - ~12%)

These simulate complex incidents with detailed investigation, cross-team coordination, and resolution.

| Scenario | Services | Duration | Description |
|----------|----------|----------|-------------|
| `cache-failure-001` | 3 | 170s | Cache fails → product-catalog overload → frontend impact |
| `payment-failure-001` | 3 | 180s | Payment 50% failure → checkout broken → revenue loss |
| `kafka-lag-001` | 3 | 310s | Consumer lag → accounting delay → fraud blind spot |
| `catalog-failure-001` | 4 | 135s | DB config error → catalog down → multiple service failures |
| `memory-leak-001` | 2 | 115s | Email OOM → crash → missed confirmation emails |
| `latency-spike-001` | 2 | 95s | Image latency → page load degradation |
| `high-cpu-001` | 2 | 75s | Ad CPU saturation → frontend timeouts |

**Total events:** ~160 messages across these scenarios

**Characteristics:**
- Multiple people responding
- Back-and-forth investigation
- Cross-channel @mentions
- kubectl commands and actions
- Metrics shown throughout
- Proper resolutions with impact analysis

### Quick/Noisy Alerts (50 scenarios - ~88%)

These simulate everyday alerts that are quickly handled or turn out to be non-issues.

**Types:**
- **False positives** (~12 scenarios) - Threshold too sensitive, metrics actually fine
- **Auto-resolved** (~12 scenarios) - Issue resolves itself before action
- **Acknowledged** (~12 scenarios) - Known issues, tickets already exist
- **Maintenance** (~8 scenarios) - Expected during deployments/maintenance
- **Threshold tweaks** (~6 scenarios) - Alert needs tuning

**Services covered:** All 16 services get alerts
**Duration:** 10-90 seconds each
**Response pattern:** 1-3 quick messages

**Example quick alert:**
```
🟡 High CPU - Shipping Service
  **maria:** Looking at this
  **maria:** False alarm - threshold too sensitive
  **maria:** Snoozing
```

## Breakdown by Service

| Service | Intensive | Quick | Total |
|---------|-----------|-------|-------|
| recommendation | 1 | 3-4 | 4-5 |
| product-catalog | 2 | 3-4 | 5-6 |
| frontend | 3 | 2-3 | 5-6 |
| payment | 1 | 3-4 | 4-5 |
| checkout | 2 | 3-4 | 5-6 |
| accounting | 1 | 3-4 | 4-5 |
| email | 1 | 2-3 | 3-4 |
| ad | 1 | 3-4 | 4-5 |
| images | 1 | 2-3 | 3-4 |
| kafka | 1 | 3-4 | 4-5 |
| fraud-detection | 1 | 2-3 | 3-4 |
| cart | 0 | 3-4 | 3-4 |
| shipping | 0 | 3-4 | 3-4 |
| currency | 0 | 2-3 | 2-3 |
| reviews | 0 | 2-3 | 2-3 |
| llm | 0 | 2-3 | 2-3 |
| load-generator | 0 | 1-2 | 1-2 |

## Alert Patterns

### Pattern 1: Cascading Failure (cache-failure, catalog-failure)
```
Service A alert
  ↓ Engineers investigate
  ↓ Downstream service B alert fires
  ↓ Service B engineer @mentions Service A
  ↓ Coordination and discovery
  ↓ Service A fixed
  ↓ Service B recovers
```

### Pattern 2: Single Service Recovery (high-cpu, latency-spike)
```
Alert fires
  ↓ Engineer investigates
  ↓ Finds root cause quickly
  ↓ Applies fix
  ↓ Monitors recovery
  ↓ Resolved
```

### Pattern 3: Async Processing Delays (kafka-lag)
```
Infrastructure alert (kafka)
  ↓ Multiple dependent services alert
  ↓ Multiple teams coordinate
  ↓ Fix applied
  ↓ Gradual recovery over 10+ minutes
  ↓ All teams confirm resolution
```

### Pattern 4: Quick Noise (most quick alerts)
```
Alert fires
  ↓ Engineer checks (1 message)
  ↓ False alarm / auto-resolved / known issue
  ↓ Acknowledged or snoozed
```

## Posting All Scenarios

### Option 1: Automated Batch (Realistic Timing)

```bash
# Posts all 57 scenarios with realistic delays
./scripts/populate-slack.sh

# Or to test channel:
./scripts/populate-slack.sh --test-channel
```

**Timeline:**
- Intensive scenarios: ~2 min between each (7 scenarios = 14 min)
- Quick alerts: 5-30 sec between each (50 alerts = 10-15 min)
- **Total runtime: ~25-30 minutes**

This creates a realistic "busy day" environment!

### Option 2: Manual Selection

```bash
# Post one intensive scenario
python3 scripts/post-to-slack.py scenarios/cache-failure-001.json \
  --yes --realtime --speed 10

# Post a few quick alerts
for scenario in scenarios/generated/*.json | head -10; do
  python3 scripts/post-to-slack.py "$scenario" --yes --realtime --speed 50
  sleep 10
done
```

### Option 3: Test All in One Channel

```bash
# Post everything to #testing
./scripts/populate-slack.sh --test-channel

# Faster for testing (30x speed = ~1 minute total)
# Edit script and change --speed 20 to --speed 30
```

## What You'll Get

After running, your Slack will have:

### High-Activity Channels
- `#product-catalog-alert` - 2 intensive + ~4 quick = busy!
- `#frontend-alert` - 3 intensive + ~3 quick = busy!
- `#checkout-alert` - 2 intensive + ~4 quick
- `#recommendation-alert` - 1 intensive + ~4 quick

### Medium-Activity Channels
- `#payment-alert` - 1 intensive + ~3 quick
- `#accounting-alert` - 1 intensive + ~3 quick
- `#kafka-alert` - 1 intensive + ~3 quick
- `#ad-alert` - 1 intensive + ~3 quick

### Low-Activity Channels  
- `#email-alert` - 1 intensive + ~2 quick
- `#images-alert` - 1 intensive + ~2 quick
- Other services - 2-3 quick alerts each

## Realistic Elements

✅ **Volume realistic** - 57 alerts in a day is normal for busy systems
✅ **Ratio realistic** - 90% noise, 10% real incidents
✅ **Mix realistic** - False positives, auto-resolves, real issues
✅ **Dependencies accurate** - Based on cascade analysis
✅ **Timing realistic** - Spread throughout the day
✅ **Conversations realistic** - 27 personas with distinct styles

## Testing the Full Set

### Quick Test (30 seconds):
```bash
# Just the intensive scenarios to #testing (fast)
for s in scenarios/*.json; do
  [[ "$s" != *"generated"* ]] && \
  python3 scripts/post-to-slack.py "$s" --test-channel '#testing' --yes --speed 50
done
```

### Full Test (2-3 minutes):
```bash
# All scenarios to #testing (fast)
./scripts/populate-slack.sh --test-channel
# Edit script first: change --speed 20 to --speed 50
```

### Production Run (25-30 minutes):
```bash
# Post to real channels with realistic timing
./scripts/populate-slack.sh
```

This will populate your channels gradually over 25-30 minutes, creating a realistic "busy ops day" environment!

## Expected Results

After completion, you'll have:
- ✅ Realistic alert volume across all service channels
- ✅ Mix of trivial and serious incidents
- ✅ Cross-channel cascading failures
- ✅ Proper @mentions and coordination
- ✅ Complete conversation threads
- ✅ Professional on-call engineer responses
- ✅ Perfect training data for AI agents!

## Next Steps

1. **Create channels** (see CHANNEL_LIST.md)
2. **Invite bots** to all channels
3. **Test with #testing**: `./scripts/populate-slack.sh --test-channel`
4. **Run for real**: `./scripts/populate-slack.sh`
5. **Watch the magic** happen! 🎭
