#!/bin/bash
# Populate Slack channels with realistic mix of alerts
# 
# This posts all 57 scenarios:
# - 7 intensive discussions (~10%)
# - 50 quick/noisy alerts (~90%)
#
# Usage:
#   ./scripts/populate-slack.sh                    # Use real channels
#   ./scripts/populate-slack.sh --test-channel     # Use #testing for all

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENARIOS_DIR="${SCRIPT_DIR}/../scenarios"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse arguments
TEST_CHANNEL=""
if [[ "${1:-}" == "--test-channel" ]]; then
    TEST_CHANNEL="--test-channel '#testing'"
    echo -e "${YELLOW}Using test channel override: #testing${NC}"
fi

echo -e "${BLUE}===========================================${NC}"
echo -e "${BLUE}  Populating Slack with Realistic Alerts${NC}"
echo -e "${BLUE}===========================================${NC}"
echo ""
echo "Total scenarios: 57"
echo "  - Intensive discussions: 7 (~10%)"
echo "  - Quick/noisy alerts: 50 (~90%)"
echo ""

# Intensive scenarios (post with slower realtime)
INTENSIVE=(
    "cache-failure-001.json"
    "payment-failure-001.json"
    "kafka-lag-001.json"
    "catalog-failure-001.json"
    "memory-leak-001.json"
    "latency-spike-001.json"
    "high-cpu-001.json"
)

# Post intensive scenarios
echo -e "${GREEN}Posting intensive discussion scenarios...${NC}"
for scenario in "${INTENSIVE[@]}"; do
    if [[ -f "${SCENARIOS_DIR}/${scenario}" ]]; then
        echo "  📊 ${scenario}"
        python3 "${SCRIPT_DIR}/post-to-slack.py" \
            "${SCENARIOS_DIR}/${scenario}" \
            --yes \
            --realtime \
            --speed 20 \
            ${TEST_CHANNEL}
        
        echo "  ⏸ Waiting 2 minutes before next incident..."
        sleep 120
    fi
done

echo ""
echo -e "${GREEN}Posting quick/noisy alerts...${NC}"

# Post quick alerts in random order
QUICK_SCENARIOS=($(ls -1 "${SCENARIOS_DIR}/generated"/*.json | shuf))

count=0
total=${#QUICK_SCENARIOS[@]}

for scenario in "${QUICK_SCENARIOS[@]}"; do
    count=$((count + 1))
    echo "  ⚡ [${count}/${total}] $(basename $scenario)"
    
    python3 "${SCRIPT_DIR}/post-to-slack.py" \
        "${scenario}" \
        --yes \
        --realtime \
        --speed 50 \
        ${TEST_CHANNEL}
    
    # Random delay between alerts (5-30 seconds)
    delay=$((5 + RANDOM % 25))
    echo "     ⏸ ${delay}s..."
    sleep ${delay}
done

echo ""
echo -e "${GREEN}===========================================${NC}"
echo -e "${GREEN}  ✓ All scenarios posted successfully!${NC}"
echo -e "${GREEN}===========================================${NC}"
echo ""
echo "Summary:"
echo "  - Intensive incidents: 7"
echo "  - Quick alerts: ${total}"
echo "  - Total: $((7 + total))"
echo ""
echo "Check your Slack channels to see the realistic alert environment!"
