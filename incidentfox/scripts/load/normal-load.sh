#!/bin/bash
# IncidentFox: Configure normal load profile
#
# This script sets the load generator to simulate normal user traffic

set -euo pipefail

echo "👥 Configuring normal load profile..."

# Check if load generator is running
if ! curl -s http://localhost:8080/loadgen/ > /dev/null 2>&1; then
    echo "❌ Load generator not accessible at http://localhost:8080/loadgen/"
    echo "   Make sure the demo is running: docker compose up -d"
    exit 1
fi

echo "✓ Load generator is running"
echo ""
echo "Normal load profile:"
echo "  • 10 concurrent users"
echo "  • 1 user spawned per second"
echo "  • Realistic browsing behavior"
echo "  • Mix of homepage, product pages, cart, checkout"
echo ""
echo "Access Locust UI to start/stop load: http://localhost:8080/loadgen/"
echo ""
echo "To configure, set environment variables in docker-compose.yml:"
echo "  LOCUST_USERS=10"
echo "  LOCUST_SPAWN_RATE=1"
echo "  LOCUST_AUTOSTART=true"

