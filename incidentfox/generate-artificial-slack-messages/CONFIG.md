# Configuration Guide

## Setting Up Your .env File

### 1. Copy the template

```bash
cp env.example .env
```

### 2. Get Your Slack Bot Token

1. Go to https://api.slack.com/apps
2. Select your app (or create one)
3. Go to "OAuth & Permissions"
4. Copy the "Bot User OAuth Token" (starts with `xoxb-`)
5. Add to `.env`:

```
SLACK_BOT_TOKEN=xoxb-your-token-here
```

### 3. Get Channel IDs (Optional)

The script can use channel names like `#recommendation-oncall`, but if you want to map them to specific IDs:

**Option A: Use Slack UI**
1. Right-click a channel → View channel details
2. Scroll down to see Channel ID
3. Copy the ID (e.g., `C01234567`)

**Option B: Use Slack API**
```bash
# List all channels
curl -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  https://slack.com/api/conversations.list
```

### 4. Get User Group IDs (for @mentions)

**Option A: Use Slack API**
```bash
curl -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  https://slack.com/api/usergroups.list
```

**Option B: Mention in Slack and check**
1. Type @yourgroup in Slack
2. Right-click the mention → Copy link
3. Extract the ID from the URL

### 5. Configure Your PagerDuty Bot for Alerts

If you want alerts to come from a different bot (like your PagerDuty bot):

```
# Main bot token (for engineer messages)
SLACK_BOT_TOKEN=xoxb-main-bot-token

# Alert bot token (for alerts)
ALERT_BOT_TOKEN=xoxb-pagerduty-bot-token
ALERT_BOT_NAME=PagerDuty Bot
```

## Configuration Options

### Basic Configuration

```bash
# Required: Your Slack bot token
SLACK_BOT_TOKEN=xoxb-1234567890-1234567890123-abcdefghijklmnopqrstuvwx

# Optional: Slack workspace ID (for reference)
SLACK_WORKSPACE_ID=T01234567
```

### Channel Mapping

Map scenario channels to your actual Slack channels:

```bash
# Map #recommendation-oncall to your channel ID
CHANNEL_recommendation_oncall=C01ABC123

# Or map to channel name
CHANNEL_recommendation_oncall=#team-recommendations

# If not specified, uses the channel name from scenario
```

### User Group Mapping

Map @mentions to your actual Slack user groups:

```bash
# Map @recommendation-oncall to actual group ID
USERGROUP_recommendation_oncall=S01ABC123

# Or use the handle
USERGROUP_recommendation_oncall=@team-rec
```

### Testing Options

```bash
# Override all channels to post to a test channel
TEST_CHANNEL_OVERRIDE=#incident-testing

# Dry run mode (don't actually post)
DRY_RUN=false

# Speed multiplier for realtime mode
SPEED_MULTIPLIER=1.0
```

### Alert Bot Configuration

```bash
# Use different bot for alerts
USE_ALERT_BOT=true
ALERT_BOT_TOKEN=xoxb-alert-bot-token
ALERT_BOT_NAME=Monitoring Alert
ALERT_BOT_ICON=:rotating_light:
```

### Logging

```bash
# Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# Log file (optional)
LOG_FILE=incidents.log
```

## Complete Example .env

```bash
# ============================================
# Slack Configuration
# ============================================

# Main bot token (required)
SLACK_BOT_TOKEN=xoxb-1234567890-1234567890123-abcdefghijklmnopqrstuvwx

# Workspace info (optional)
SLACK_WORKSPACE_ID=T01234567

# ============================================
# Alert Bot (optional - use different bot for alerts)
# ============================================

USE_ALERT_BOT=true
ALERT_BOT_TOKEN=xoxb-9876543210-9876543210987-zyxwvutsrqponmlkjihgfedc
ALERT_BOT_NAME=PagerDuty Bot
ALERT_BOT_ICON=:rotating_light:

# ============================================
# Channel Mapping (optional - only if different from scenario)
# ============================================

# If your channels have different names, map them here
CHANNEL_recommendation_oncall=C01RECOMMEND
CHANNEL_product_catalog_oncall=C02CATALOG
CHANNEL_frontend_oncall=C03FRONTEND
CHANNEL_payment_oncall=C04PAYMENT
CHANNEL_checkout_oncall=C05CHECKOUT

# ============================================
# User Group Mapping (optional)
# ============================================

# Map @mentions to actual group IDs
USERGROUP_recommendation_oncall=S01RECOMMEND
USERGROUP_product_catalog_oncall=S02CATALOG
USERGROUP_frontend_oncall=S03FRONTEND
USERGROUP_payment_oncall=S04PAYMENT
USERGROUP_checkout_oncall=S05CHECKOUT

# ============================================
# Testing Options
# ============================================

# Override all channels (useful for testing)
# TEST_CHANNEL_OVERRIDE=#incident-testing

# Preview without posting
DRY_RUN=false

# Speed multiplier for realtime mode (1.0 = realtime, 10.0 = 10x faster)
SPEED_MULTIPLIER=1.0

# ============================================
# Logging
# ============================================

LOG_LEVEL=INFO
# LOG_FILE=incidents.log
```

## Quick Setup (Minimal)

For quick testing, you only need:

```bash
SLACK_BOT_TOKEN=xoxb-your-token-here
TEST_CHANNEL_OVERRIDE=#incident-testing
```

This will:
- Post all messages using your bot
- Override all channels to post to `#incident-testing`
- Use default names for everything else

## Finding Your IDs

### Channel IDs

**Method 1: Slack UI**
```
Right-click channel → View channel details → Channel ID
```

**Method 2: API call**
```bash
curl -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  "https://slack.com/api/conversations.list?types=public_channel,private_channel" \
  | jq '.channels[] | {name, id}'
```

### User Group IDs

**Method 1: API call**
```bash
curl -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  "https://slack.com/api/usergroups.list" \
  | jq '.usergroups[] | {handle, id}'
```

**Method 2: Slack UI**
```
Settings → People → User groups → Click group → Group ID in URL
```

## Troubleshooting

### "channel_not_found"
- Make sure bot is invited to channel
- Use `TEST_CHANNEL_OVERRIDE` to test in a single channel first

### "@mentions not working"
- User groups must exist in Slack
- Bot needs `usergroups:read` scope
- Use actual group IDs in USERGROUP_ mappings

### "No real users"
- That's fine! Messages will show as "**alice:** message here"
- Bot posts all messages but formats them to show who's speaking
- Looks realistic in practice

### Multiple bots not working
- Make sure ALERT_BOT_TOKEN is valid
- Check bot has same permissions as main bot
- Both bots must be invited to channels

## Best Practices

1. **Testing Setup**
   - Start with `DRY_RUN=true`
   - Use `TEST_CHANNEL_OVERRIDE` for initial tests
   - Verify formatting before posting to real channels

2. **Channel Organization**
   - Create all channels before running
   - Invite both bots to all channels
   - Use consistent naming (`#service-oncall`)

3. **User Groups**
   - Create user groups matching scenario names
   - Add yourself to groups for testing @mentions
   - Groups can be empty (just need to exist)

4. **Multiple Bots**
   - Use PagerDuty bot for alerts (looks official)
   - Use main bot for engineer messages
   - Gives better visual separation

## Example Workflow

```bash
# 1. Set up minimal config
cat > .env << EOF
SLACK_BOT_TOKEN=xoxb-your-token
TEST_CHANNEL_OVERRIDE=#testing
EOF

# 2. Test with dry run
python scripts/post-to-slack.py scenarios/cache-failure-001.json --dry-run

# 3. Test in single channel
python scripts/post-to-slack.py scenarios/cache-failure-001.json

# 4. Review in Slack, then configure real channels
# 5. Remove TEST_CHANNEL_OVERRIDE
# 6. Post for real!
```
