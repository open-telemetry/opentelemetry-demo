#!/bin/bash
# IncidentFox: Trigger a traffic spike
#
# This script uses the load generator feature flag to create a traffic spike

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENARIO_SCRIPT="${SCRIPT_DIR}/../scenarios/traffic-spike.sh"

echo "🌊 Triggering traffic spike via feature flag..."
echo ""
echo "This will use the 'loadGeneratorFloodHomepage' feature flag"
echo "to flood the homepage with requests."
echo ""

# Call the traffic-spike scenario
if [ -x "$SCENARIO_SCRIPT" ]; then
    "$SCENARIO_SCRIPT"
else
    echo "❌ Traffic spike scenario not found or not executable"
    echo "   Expected: $SCENARIO_SCRIPT"
    exit 1
fi

echo ""
echo "Alternative: Manual spike via Locust UI"
echo "  1. Go to http://localhost:8080/loadgen/"
echo "  2. Set users to 100+"
echo "  3. Set spawn rate to 10+"
echo "  4. Click 'Start swarming'"

