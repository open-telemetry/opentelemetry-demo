# Slack Channels to Create

## All Channels (17 services + 1 test)

### Copy-paste these channel names into Slack:

```
recommendation-alert
product-catalog-alert
frontend-alert
payment-alert
checkout-alert
accounting-alert
cart-alert
shipping-alert
currency-alert
ad-alert
email-alert
fraud-alert
images-alert
reviews-alert
llm-alert
kafka-alert
load-gen-alert
testing
```

## Core Channels (for current 2 scenarios)

**Minimum needed to run cache-failure and payment-failure:**

```
testing
recommendation-alert
product-catalog-alert
frontend-alert
payment-alert
checkout-alert
accounting-alert
```

## Full List with Descriptions

| Channel | Service | Used In Scenario |
|---------|---------|------------------|
| `#recommendation-alert` | Recommendation Service | ✅ cache-failure |
| `#product-catalog-alert` | Product Catalog | ✅ cache-failure |
| `#frontend-alert` | Frontend | ✅ cache-failure |
| `#payment-alert` | Payment | ✅ payment-failure |
| `#checkout-alert` | Checkout | ✅ payment-failure |
| `#accounting-alert` | Accounting | ✅ payment-failure |
| `#cart-alert` | Cart | (future) |
| `#shipping-alert` | Shipping | (future) |
| `#currency-alert` | Currency | (future) |
| `#ad-alert` | Advertisement | (future) |
| `#email-alert` | Email | (future) |
| `#fraud-alert` | Fraud Detection | (future) |
| `#images-alert` | Image Provider | (future) |
| `#reviews-alert` | Product Reviews | (future) |
| `#llm-alert` | LLM Service | (future) |
| `#kafka-alert` | Kafka/Messaging | (future) |
| `#load-gen-alert` | Load Generator | (future) |
| `#testing` | Test channel | ✅ Testing |

## Quick Setup Steps

### 1. Create Channels

In Slack:
1. Click `+` next to "Channels"
2. Select "Create a channel"
3. Paste channel name (without `#`)
4. Make it **public**
5. Click "Create"
6. Repeat for all channels

### 2. Invite Bots to ALL Channels

In **EACH** channel, run:
```
/invite @your-main-bot @your-pagerduty-bot
```

**Or invite manually:**
- Click channel name → Integrations → Add apps → Select your bots

### 3. Create User Groups (Optional but recommended)

In Slack:
- Settings & administration → Manage members → User groups
- Create these groups:
  - `@recommendation-oncall`
  - `@product-catalog-oncall`
  - `@frontend-oncall`
  - `@payment-oncall`
  - `@checkout-oncall`
  - `@accounting-oncall`

You can add yourself to all groups for testing.

## Test After Setup

```bash
cd incidentfox/generate-artificial-slack-messages

# Test in #testing channel first
python3 scripts/post-to-slack.py scenarios/cache-failure-001.json \
  --test-channel '#testing' --yes

# If it works, try with real channels
python3 scripts/post-to-slack.py scenarios/cache-failure-001.json --yes
```

## Naming Convention

- **Channels**: `#service-alert` (for alert discussions)
- **User Groups**: `@service-oncall` (for @mentions to on-call team)

This separation makes it clear:
- Channels are where alerts and discussions happen
- User groups are teams that get @mentioned

## After Creating Channels

Update your `.env` if needed (auto-discovery should work):

```bash
python3 scripts/setup-slack.py --generate-env
```

This will discover all your new channels and update the configuration automatically!
