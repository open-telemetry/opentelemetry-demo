#!/bin/bash
# Helper script to generate invite commands for all channels

echo "================================================"
echo "  Invite Bots to All Channels"
echo "================================================"
echo ""
echo "Copy and paste these commands into each Slack channel:"
echo ""

CHANNELS=(
  "recommendation-alert"
  "product-catalog-alert"
  "frontend-alert"
  "payment-alert"
  "checkout-alert"
  "accounting-alert"
  "cart-alert"
  "shipping-alert"
  "currency-alert"
  "ad-alert"
  "email-alert"
  "fraud-alert"
  "images-alert"
  "reviews-alert"
  "llm-alert"
  "kafka-alert"
  "load-gen-alert"
)

echo "Channels to invite bots (${#CHANNELS[@]} total):"
echo ""

for channel in "${CHANNELS[@]}"; do
  echo "#$channel:"
  echo "  /invite @your-main-bot @your-pagerduty-bot"
  echo ""
done

echo "================================================"
echo ""
echo "Or use Slack UI:"
echo "1. Go to each channel"
echo "2. Click channel name → Integrations"
echo "3. Add apps → Select both bots"
echo ""
echo "After inviting bots to all channels, run:"
echo "  ./scripts/populate-slack.sh"
