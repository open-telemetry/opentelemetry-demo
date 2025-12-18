#!/bin/bash
# Post all quick alerts with progress tracking

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENARIOS_DIR="${SCRIPT_DIR}/../scenarios/generated"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "================================================"
echo "  Posting 50 Quick Alerts"
echo "================================================"
echo ""

count=0
total=$(ls -1 "$SCENARIOS_DIR"/*.json | wc -l | tr -d ' ')

for scenario in "$SCENARIOS_DIR"/*.json; do
    count=$((count + 1))
    basename=$(basename "$scenario")
    
    echo -e "${BLUE}[$count/$total]${NC} $basename"
    
    python3 "${SCRIPT_DIR}/post-to-slack.py" "$scenario" --yes --realtime --speed 100 2>&1 | grep -E "(✓|ERROR)" || true
    
    # Random delay 5-15 seconds
    delay=$((5 + RANDOM % 10))
    sleep $delay
done

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  ✓ All $total quick alerts posted!${NC}"
echo -e "${GREEN}================================================${NC}"
