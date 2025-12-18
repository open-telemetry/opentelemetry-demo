# Your Setup Checklist ✅

## What You Have

✅ Slack workspace with channels
✅ Channels created (e.g., `#recommendation-oncall`)  
✅ User groups created (e.g., `@recommendation-oncall`)
✅ PagerDuty bot created
❌ No real users (Alice, Bob, etc.) - **This is fine!**

## What's Been Implemented For You

### ✅ No Real Users Problem - SOLVED

Messages are formatted to show personas:

```
**alice:** Looking into this 👀
**bob:** I see it too. Checking the dashboard now
**charlie:** @recommendation-oncall Hey, are you seeing issues?
```

Even though it's posted by your bot, it's **crystal clear** who's speaking.

### ✅ .env Configuration - READY

Complete `.env` template in `env.example` with:
- Main bot token
- PagerDuty bot configuration
- Channel ID mapping
- User group ID mapping
- Testing options

### ✅ Channel IDs - AUTO-DISCOVERY

Script to automatically discover and configure:

```bash
python scripts/setup-slack.py --generate-env
```

### ✅ User Group IDs - AUTO-DISCOVERY

Same script discovers user groups and maps them:

```bash
python scripts/setup-slack.py --list-groups
```

### ✅ PagerDuty Bot for Alerts - SUPPORTED

Configuration in `.env`:

```bash
USE_ALERT_BOT=true
ALERT_BOT_TOKEN=xoxb-your-pagerduty-bot-token
ALERT_BOT_NAME=PagerDuty Bot
```

Now alerts come from PagerDuty bot, engineer messages from main bot!

### ✅ Proper @mentions - IMPLEMENTED

Automatically converts `@recommendation-oncall` to proper Slack user group mentions using your group IDs.

## What You Need To Do (5 minutes)

### 1. Get Your Tokens

```bash
cd incidentfox/generate-artificial-slack-messages

# Add your main bot token
echo "SLACK_BOT_TOKEN=xoxb-your-main-bot-token" > .env

# Add your PagerDuty bot token
echo "USE_ALERT_BOT=true" >> .env
echo "ALERT_BOT_TOKEN=xoxb-your-pagerduty-bot-token" >> .env
echo "ALERT_BOT_NAME=PagerDuty Bot" >> .env
```

### 2. Auto-Configure Everything

```bash
# This discovers all your channels and groups
python scripts/setup-slack.py --generate-env
```

This creates a complete `.env` with:
- ✅ All channel IDs mapped
- ✅ All user group IDs mapped
- ✅ Ready to use immediately

### 3. Test It

```bash
# Preview (no posting)
python scripts/post-to-slack.py scenarios/cache-failure-001.json --preview-only

# Dry run (simulate posting)
python scripts/post-to-slack.py scenarios/cache-failure-001.json --dry-run

# Test in single channel (10x speed)
python scripts/post-to-slack.py scenarios/cache-failure-001.json \
  --test-channel #incident-testing \
  --realtime --speed 10
```

### 4. Go Live!

```bash
# Post to real channels with realistic timing
python scripts/post-to-slack.py scenarios/cache-failure-001.json --realtime
```

## What It Will Look Like

### In #recommendation-oncall:

```
[PagerDuty Bot - 2:30 PM]
🟡 High Latency Detected - Recommendation Service
P95 latency increased from 50ms to 520ms (10.4x increase)

Current Metrics:
• p50_latency: 480ms
• p95_latency: 520ms
• p99_latency: 890ms

[📖 Runbook] [📊 Dashboard]

    [Your Bot - 2:30 PM]
    **alice:** Looking into this 👀
    
    [Your Bot - 2:30 PM]
    **bob:** I see it too. Checking the dashboard now
    
    [Your Bot - 2:31 PM]
    **alice:** Wait... cache hit rate just dropped to 0% 😱
```

### In #product-catalog-oncall (1 minute later):

```
[PagerDuty Bot - 2:31 PM]
🟡 High CPU Usage - Product Catalog Service
CPU usage increased from 15% to 68%

    [Your Bot - 2:31 PM]
    **charlie:** Whoa what's going on? We just got slammed with 10x traffic
    
    [Your Bot - 2:31 PM]
    **charlie:** All from recommendation service
    
    [Your Bot - 2:32 PM]
    **charlie:** @recommendation-oncall Hey folks, are you having issues?
```

## Files You Need

### Required

- ✅ `.env` - Your configuration (auto-generated)

### Already Created

- ✅ `scenarios/cache-failure-001.json` - Complete scenario
- ✅ `scenarios/payment-failure-001.json` - Another complete scenario
- ✅ `scripts/post-to-slack.py` - Posting script
- ✅ `scripts/setup-slack.py` - Auto-configuration script
- ✅ `lib/slack_client.py` - Slack integration (supports your setup!)

## Everything Works With Your Setup!

### ✅ No users needed
Messages show persona names: `**alice:** message`

### ✅ Channels auto-discovered
Script finds all your channels

### ✅ Groups auto-discovered
Script finds all your user groups

### ✅ PagerDuty bot supported
Alerts come from your PagerDuty bot

### ✅ @mentions work
Properly formatted for Slack

### ✅ Threading works
Conversations stay organized

### ✅ Realistic conversations
27 personas with distinct styles

### ✅ Proper timelines
Events follow cascade analysis

## Your Complete Setup Command

```bash
# One-time setup (5 minutes)
cd incidentfox/generate-artificial-slack-messages
pip install -r requirements.txt

# Configure
echo "SLACK_BOT_TOKEN=xoxb-your-token" > .env
echo "USE_ALERT_BOT=true" >> .env
echo "ALERT_BOT_TOKEN=xoxb-pagerduty-token" >> .env
python scripts/setup-slack.py --generate-env

# Test
python scripts/post-to-slack.py scenarios/cache-failure-001.json \
  --test-channel #testing --realtime --speed 10

# Go live
python scripts/post-to-slack.py scenarios/cache-failure-001.json --realtime
```

## What You DON'T Need

❌ Create fake user accounts
❌ Configure individual personas
❌ Manually map channels
❌ Manually map user groups
❌ Write any code
❌ Modify scenarios

Everything is **ready to use** with your exact setup! 🎉

## Questions?

See:
- **SETUP.md** - Detailed setup guide
- **CONFIG.md** - Configuration options
- **README.md** - Complete documentation
- **QUICKSTART.md** - 5-minute guide

## Summary

You have:
- ✅ Slack channels and groups (perfect!)
- ✅ PagerDuty bot (will be used for alerts!)
- ❌ No real users (not a problem!)

System provides:
- ✅ Formatted messages showing who's speaking
- ✅ Auto-discovery of channels and groups
- ✅ PagerDuty bot integration
- ✅ Proper @mentions
- ✅ Realistic conversations
- ✅ Ready-to-use scenarios

**You're ready to go!** Just add your tokens and run the setup script. 🚀
