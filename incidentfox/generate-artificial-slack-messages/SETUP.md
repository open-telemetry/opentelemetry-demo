# Setup Guide for Your Slack

## Your Situation

✅ Slack channels created (e.g., `#recommendation-oncall`)
✅ Slack user groups created (e.g., `@recommendation-oncall`)
❌ No real users named Alice, Bob, etc.
✅ Have a PagerDuty bot

**This is perfect!** The system will work great with what you have.

## Quick Setup (5 minutes)

### Step 1: Get Your Bot Token

```bash
cd incidentfox/generate-artificial-slack-messages

# Add your bot token to .env
echo "SLACK_BOT_TOKEN=xoxb-your-token-here" > .env
```

### Step 2: Auto-Generate Configuration

```bash
# This will discover all your channels and groups
python scripts/setup-slack.py --generate-env
```

This creates a `.env` file with:
- All your channel IDs mapped
- All your user group IDs mapped
- Ready to use!

### Step 3: Configure Your PagerDuty Bot (Optional)

If you want alerts to come from your PagerDuty bot:

```bash
# Add to .env
echo "USE_ALERT_BOT=true" >> .env
echo "ALERT_BOT_TOKEN=xoxb-your-pagerduty-bot-token" >> .env
echo "ALERT_BOT_NAME=PagerDuty Bot" >> .env
```

### Step 4: Test It!

```bash
# Test in a single channel
python scripts/post-to-slack.py scenarios/cache-failure-001.json \
  --test-channel #incident-testing \
  --dry-run

# If it looks good, remove --dry-run to post for real
python scripts/post-to-slack.py scenarios/cache-failure-001.json \
  --test-channel #incident-testing
```

## What You'll See in Slack

Since you don't have real users, messages will look like this:

```
[In #recommendation-oncall]

🟡 High Latency Detected - Recommendation Service
P95 latency increased from 50ms to 520ms...

**alice:** Looking into this 👀

**bob:** I see it too. Checking the dashboard now

**alice:** Wait... cache hit rate just dropped to 0% 😱

...

[In #product-catalog-oncall - 60 seconds later]

🟡 High CPU Usage - Product Catalog Service  
CPU usage increased from 15% to 68%...

**charlie:** Whoa what's going on? We just got slammed with 10x traffic

**charlie:** @recommendation-oncall Hey folks, are you having issues?

[Back in #recommendation-oncall]

**alice:** Yes @charlie! Our cache is down so we're bypassing it
```

## The Format

Messages are posted by your bot but **formatted to show who's speaking**:

- **`**alice:** Looking into this`** - Makes it clear Alice is speaking
- **`@recommendation-oncall`** - Properly formatted Slack mentions
- **Threading** - Conversations stay organized in threads

This actually works **better** than having fake user accounts because:
- ✅ No need to create 27 fake users
- ✅ Clear who's speaking
- ✅ Real Slack threading and @mentions work
- ✅ Your PagerDuty bot can post alerts (looks official!)

## Manual Configuration (if auto-generation fails)

### Get Channel IDs

**Method 1: Slack UI**
```
Right-click channel → View channel details → Copy Channel ID
```

**Method 2: Use helper script**
```bash
python scripts/setup-slack.py --list-channels
```

**Method 3: API call**
```bash
curl -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  "https://slack.com/api/conversations.list" | jq '.channels[] | {name, id}'
```

### Get User Group IDs

```bash
python scripts/setup-slack.py --list-groups
```

### Add to .env

```bash
# Your channels
CHANNEL_recommendation_oncall=C01ABC123
CHANNEL_product_catalog_oncall=C02DEF456
CHANNEL_frontend_oncall=C03GHI789

# Your user groups
USERGROUP_recommendation_oncall=S01ABC123
USERGROUP_product_catalog_oncall=S02DEF456
USERGROUP_frontend_oncall=S03GHI789

# Your PagerDuty bot
USE_ALERT_BOT=true
ALERT_BOT_TOKEN=xoxb-pagerduty-token
ALERT_BOT_NAME=PagerDuty Bot
```

## Testing Workflow

### 1. Test with Dry Run

```bash
python scripts/post-to-slack.py scenarios/cache-failure-001.json --dry-run
```

Shows what would be posted without actually posting.

### 2. Test in Single Channel

```bash
# Override all channels to post to #testing
python scripts/post-to-slack.py scenarios/cache-failure-001.json \
  --test-channel #incident-testing
```

### 3. Test with Speed

```bash
# Post 10x faster (17 seconds instead of 2.5 minutes)
python scripts/post-to-slack.py scenarios/cache-failure-001.json \
  --test-channel #incident-testing \
  --realtime --speed 10
```

### 4. Post to Real Channels

```bash
# Remove --test-channel to use actual channels
python scripts/post-to-slack.py scenarios/cache-failure-001.json --realtime
```

## Complete Example .env

```bash
# ============================================
# Main Bot
# ============================================
SLACK_BOT_TOKEN=xoxb-1234567890-1234567890123-abcdefghijklmnopqrstuvwx

# ============================================
# PagerDuty Bot (for alerts)
# ============================================
USE_ALERT_BOT=true
ALERT_BOT_TOKEN=xoxb-9876543210-9876543210987-zyxwvutsrqponmlkjihgfedc
ALERT_BOT_NAME=PagerDuty Bot

# ============================================
# Channels (auto-discovered)
# ============================================
CHANNEL_recommendation_oncall=C01RECOMMEND
CHANNEL_product_catalog_oncall=C02CATALOG
CHANNEL_frontend_oncall=C03FRONTEND
CHANNEL_payment_oncall=C04PAYMENT
CHANNEL_checkout_oncall=C05CHECKOUT

# ============================================
# User Groups (auto-discovered)
# ============================================
USERGROUP_recommendation_oncall=S01RECOMMEND
USERGROUP_product_catalog_oncall=S02CATALOG
USERGROUP_frontend_oncall=S03FRONTEND
USERGROUP_payment_oncall=S04PAYMENT
USERGROUP_checkout_oncall=S05CHECKOUT

# ============================================
# Testing
# ============================================
# TEST_CHANNEL_OVERRIDE=#incident-testing
DRY_RUN=false
SPEED_MULTIPLIER=1.0
LOG_LEVEL=INFO
```

## What Each Bot Does

### Main Bot
- Posts all engineer messages (**alice:**, **bob:**, etc.)
- Posts actions (kubectl commands, etc.)
- Posts resolutions

### PagerDuty Bot (Optional)
- Posts monitoring alerts only
- Makes alerts look official
- Clearly separates alerts from human discussion

## Troubleshooting

### "channel_not_found"

**Fix:** Invite both bots to all channels

```
In Slack:
/invite @your-bot to #recommendation-oncall
/invite @pagerduty-bot to #recommendation-oncall
```

### "@mentions not working"

**Fix:** Make sure user groups exist and IDs are correct

```bash
# Check your groups
python scripts/setup-slack.py --list-groups

# Update .env with correct IDs
USERGROUP_recommendation_oncall=S01ABC123
```

### "Messages don't look right"

The format is:
```
**alice:** Looking into this
```

Slack renders `**text**` as bold, so you'll see:
**alice:** Looking into this

This is correct! It's clear who's speaking.

### "Want to use single channel for testing"

```bash
# Add to .env
TEST_CHANNEL_OVERRIDE=#incident-testing

# Or use flag
python scripts/post-to-slack.py scenarios/... --test-channel #testing
```

## Next Steps

1. ✅ Run setup script to discover channels/groups
2. ✅ Test with `--dry-run` first
3. ✅ Test in single channel
4. ✅ Try with realtime mode
5. ✅ Post to real channels!

## Example Session

```bash
# Step 1: Setup
cd incidentfox/generate-artificial-slack-messages
cp env.example .env
# Edit .env and add SLACK_BOT_TOKEN

# Step 2: Auto-configure
python scripts/setup-slack.py --generate-env

# Step 3: Preview
python scripts/post-to-slack.py scenarios/cache-failure-001.json --preview-only

# Step 4: Dry run
python scripts/post-to-slack.py scenarios/cache-failure-001.json --dry-run

# Step 5: Test in single channel (10x speed)
python scripts/post-to-slack.py scenarios/cache-failure-001.json \
  --test-channel #testing \
  --realtime --speed 10

# Step 6: Post to real channels!
python scripts/post-to-slack.py scenarios/cache-failure-001.json --realtime
```

You're all set! 🚀
