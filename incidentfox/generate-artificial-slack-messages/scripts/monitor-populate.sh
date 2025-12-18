#!/bin/bash
# Monitor the populate-slack.sh progress

TERMINAL_FILE="/Users/apple/.cursor/projects/Users-apple-Desktop-aws-playground/terminals/880258.txt"

echo "================================================"
echo "  Monitoring Slack Population Progress"
echo "================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

while true; do
    clear
    echo "================================================"
    echo "  Slack Population Progress"
    echo "================================================"
    echo ""
    
    # Check if process is still running
    if ! ps aux | grep -q "[p]opulate-slack.sh"; then
        echo -e "${GREEN}✓ Process completed!${NC}"
        echo ""
        
        # Show final summary
        if [[ -f "$TERMINAL_FILE" ]]; then
            echo "Final status:"
            tail -20 "$TERMINAL_FILE" | grep -E "(✓|✅|posted|complete)" | tail -5
        fi
        break
    fi
    
    if [[ -f "$TERMINAL_FILE" ]]; then
        # Count completed scenarios
        intensive_done=$(grep -c "Scenario posted successfully" "$TERMINAL_FILE" 2>/dev/null || echo "0")
        quick_done=$(grep -c "⚡" "$TERMINAL_FILE" 2>/dev/null || echo "0")
        
        echo -e "${BLUE}Intensive scenarios:${NC} ${intensive_done}/7 completed"
        echo -e "${BLUE}Quick alerts:${NC} ${quick_done}/50 completed"
        echo ""
        
        # Show current activity
        echo -e "${YELLOW}Current activity:${NC}"
        tail -15 "$TERMINAL_FILE" | grep -E "(📊|⚡|Posting|Posted|Waiting)" | tail -5
        echo ""
        
        # Estimate time remaining
        if [[ $intensive_done -gt 0 ]]; then
            remaining_intensive=$((7 - intensive_done))
            remaining_quick=$((50 - quick_done))
            estimated_min=$(( (remaining_intensive * 2) + (remaining_quick / 3) ))
            echo -e "${BLUE}Estimated time remaining:${NC} ~${estimated_min} minutes"
        fi
    else
        echo "Waiting for process to start..."
    fi
    
    echo ""
    echo "Press Ctrl+C to stop monitoring (process will continue)"
    sleep 5
done

echo ""
echo "================================================"
echo -e "${GREEN}  All scenarios posted successfully!${NC}"
echo "================================================"
echo ""
echo "Check your Slack channels:"
echo "  • #recommendation-alert"
echo "  • #product-catalog-alert"
echo "  • #payment-alert"
echo "  • #checkout-alert"
echo "  • And 13 more service channels!"
