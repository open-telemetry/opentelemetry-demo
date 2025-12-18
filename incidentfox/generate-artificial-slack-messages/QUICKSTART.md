# Quick Start Guide
## Artificial Slack Incident Generator

Get up and running in 5 minutes!

## 1. Install Dependencies

```bash
cd incidentfox/generate-artificial-slack-messages
pip install -r requirements.txt
```

## 2. Set Up Slack (Optional for Testing)

For testing without Slack, skip to step 3 and use `--dry-run`.

To actually post to Slack:

### Create a Slack App

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name it "Incident Generator" and select your workspace
4. Go to "OAuth & Permissions"
5. Add these **Bot Token Scopes**:
   - `chat:write`
   - `chat:write.public`
   - `reactions:write`
6. Click "Install to Workspace"
7. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### Configure Environment

```bash
cp env.example .env
# Edit .env and add your token:
SLACK_BOT_TOKEN=xoxb-your-token-here
```

### Create Channels (Optional)

For realistic testing, create these channels in Slack:
- `#recommendation-oncall`
- `#product-catalog-oncall`
- `#frontend-oncall`
- `#payment-oncall`
- `#checkout-oncall`

Or use `--test-channel` to post everything to one channel!

## 3. Preview a Scenario

```bash
python scripts/post-to-slack.py scenarios/cache-failure-001.json --preview-only
```

This shows you what will be posted without actually posting.

## 4. Test with Dry Run

```bash
python scripts/post-to-slack.py scenarios/cache-failure-001.json --dry-run
```

This simulates posting and shows what would happen.

## 5. Post to Slack (for real!)

### Option A: Post to a Test Channel

```bash
python scripts/post-to-slack.py scenarios/cache-failure-001.json --test-channel #incident-testing
```

All messages go to one channel for easy testing.

### Option B: Post to Real Channels

```bash
python scripts/post-to-slack.py scenarios/cache-failure-001.json
```

Posts to the actual service channels defined in the scenario.

### Option C: Post with Realistic Timing

```bash
# Post with real delays (2.5 min total for cache-failure)
python scripts/post-to-slack.py scenarios/cache-failure-001.json --realtime

# Post 10x faster (15 seconds instead of 2.5 min)
python scripts/post-to-slack.py scenarios/cache-failure-001.json --realtime --speed 10
```

## 6. Try Different Scenarios

```bash
# Payment service failure
python scripts/post-to-slack.py scenarios/payment-failure-001.json --dry-run

# List all available scenarios
ls scenarios/*.json
```

## Available Scenarios

- ✅ `cache-failure-001.json` - Cache fails → downstream overload
- ✅ `payment-failure-001.json` - Payment 50% failure → checkout impact

More scenarios coming soon!

## Creating Your Own Scenario

1. Copy an existing scenario:
```bash
cp scenarios/cache-failure-001.json scenarios/my-scenario.json
```

2. Edit the JSON file (see [schema/incident-schema.json](schema/incident-schema.json) for reference)

3. Validate it:
```bash
python scripts/validate-scenario.py scenarios/my-scenario.json
```

4. Post it:
```bash
python scripts/post-to-slack.py scenarios/my-scenario.json --dry-run
```

## Tips for Realistic Incidents

### 1. Vary Response Times

Not everyone responds immediately:

```json
{
  "offset_seconds": 0,    // Alert fires
},
{
  "offset_seconds": 8,    // Alice responds fast
  "user": "alice"
},
{
  "offset_seconds": 15,   // Bob responds slower
  "user": "bob"
}
```

### 2. Include False Starts

Engineers investigate wrong paths:

```json
{
  "offset_seconds": 30,
  "user": "alice",
  "content": "Could this be a network issue?"
},
{
  "offset_seconds": 40,
  "user": "bob",
  "content": "I don't think so, network looks fine"
},
{
  "offset_seconds": 50,
  "user": "alice",
  "content": "You're right. Let me check the cache..."
}
```

### 3. Show the Debugging Process

Include commands, logs, dashboards:

```json
{
  "offset_seconds": 55,
  "user": "alice",
  "content": "Checking logs... seeing `CacheConnectionException: Connection refused to redis:6379`"
},
{
  "offset_seconds": 60,
  "type": "action",
  "user": "bob",
  "action_type": "restart",
  "content": "```\n$ kubectl rollout restart deployment/redis\n```"
}
```

### 4. Cross-Team Coordination

Show @mentions when discovering dependencies:

```json
{
  "offset_seconds": 85,
  "user": "charlie",
  "content": "@recommendation-oncall Hey folks, seeing huge spike in traffic from your service",
  "mentions": ["@recommendation-oncall"]
}
```

### 5. Add Reactions

Show team engagement:

```json
{
  "offset_seconds": 130,
  "user": "alice",
  "content": "Cache hit rate recovering!",
  "reactions": [
    {
      "emoji": "rocket",
      "users": ["bob", "charlie"]
    }
  ]
}
```

## Common Issues

### "SLACK_BOT_TOKEN not set"

Make sure you have a `.env` file with your token, or use `--dry-run` for testing.

### "Channel not found"

Either:
- Create the channels in Slack, or
- Use `--test-channel #your-channel` to post to one channel

### "Invalid JSON"

Validate your scenario:
```bash
python scripts/validate-scenario.py scenarios/your-scenario.json
```

### Messages not threading correctly

Make sure `thread_parent` indices are correct:
- Use `null` or omit for top-level messages
- Use `0` to reply to the first message (alert)
- Indices are 0-based and must be less than current message index

## Next Steps

- **Read the full [README.md](README.md)** for detailed documentation
- **Study existing scenarios** in `scenarios/` folder
- **Review the [Cascade Impact Analysis](../docs/cascade-impact-analysis.md)** for realistic failure patterns
- **Create custom scenarios** based on your own incident experiences
- **Share your scenarios** with the team!

## Examples

### Test Everything in One Command

```bash
# Validate → Preview → Dry Run → Test Channel
python scripts/validate-scenario.py scenarios/cache-failure-001.json && \
python scripts/post-to-slack.py scenarios/cache-failure-001.json --preview-only && \
python scripts/post-to-slack.py scenarios/cache-failure-001.json --dry-run && \
python scripts/post-to-slack.py scenarios/cache-failure-001.json --test-channel #testing --realtime --speed 10
```

### Morning Incident Simulation

```bash
# Post a realistic incident every hour
for scenario in scenarios/*.json; do
  echo "Posting $scenario at $(date)"
  python scripts/post-to-slack.py "$scenario" --realtime --speed 20
  echo "Waiting 1 hour..."
  sleep 3600
done
```

## Need Help?

- Check [README.md](README.md) for full documentation
- Review example scenarios in `scenarios/`
- Read the JSON schema in `schema/incident-schema.json`
- Look at cascade analysis in `../docs/cascade-impact-analysis.md`

Happy incident generating! 🚨
