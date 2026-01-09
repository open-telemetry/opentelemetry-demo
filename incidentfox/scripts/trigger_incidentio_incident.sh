#!/bin/bash
#
# trigger_incidentio_incident.sh
# Creates an incident in incident.io via the API
#
# Usage:
#   ./trigger_incidentio_incident.sh                    # Uses defaults
#   ./trigger_incidentio_incident.sh "Incident Name"   # Custom name
#   ./trigger_incidentio_incident.sh "Name" "Summary" "critical|major|minor"
#
# Environment Variables:
#   INCIDENTIO_API_KEY - Required, or set below
#

set -eo pipefail

# ============================================================================
# Configuration
# ============================================================================

API_KEY="${INCIDENTIO_API_KEY:-}"  # Set via env var: export INCIDENTIO_API_KEY=inc_xxx
API_BASE="https://api.incident.io"

if [[ -z "$API_KEY" ]]; then
    echo "ERROR: INCIDENTIO_API_KEY environment variable is not set." >&2
    echo "Set it with: export INCIDENTIO_API_KEY=inc_your_key_here" >&2
    exit 1
fi

# Severity IDs (from your incident.io organization)
SEVERITY_ID_MINOR="01KCSZ7E54DSD4TTVPXFEEQ2PV"
SEVERITY_ID_MAJOR="01KCSZ7E54R7NQE5570YHFA3C8"
SEVERITY_ID_CRITICAL="01KCSZ7E54WJQBBZ0HBYQ152FW"

# ============================================================================
# Parse Arguments
# ============================================================================

INCIDENT_NAME="${1:-Payment Service - High Error Rate}"
SUMMARY="${2:-Coralogix detected anomalous behavior in the payment service. Error rate exceeded threshold.}"
SEVERITY="${3:-critical}"

# Validate severity and get ID
SEVERITY_LOWER=$(echo "$SEVERITY" | tr '[:upper:]' '[:lower:]')
case "$SEVERITY_LOWER" in
    minor)
        SEVERITY_ID="$SEVERITY_ID_MINOR"
        ;;
    major)
        SEVERITY_ID="$SEVERITY_ID_MAJOR"
        ;;
    critical)
        SEVERITY_ID="$SEVERITY_ID_CRITICAL"
        ;;
    *)
        echo "Error: Invalid severity '$SEVERITY'. Must be one of: minor, major, critical"
        exit 1
        ;;
esac

# Generate unique idempotency key
IDEMPOTENCY_KEY="coralogix-$(date +%s)-$(openssl rand -hex 4)"

# ============================================================================
# Create Incident
# ============================================================================

echo "Creating incident in incident.io..."
echo "  Name: $INCIDENT_NAME"
echo "  Severity: $SEVERITY_LOWER"
echo "  Summary: $SUMMARY"
echo ""

RESPONSE=$(curl -s -X POST "${API_BASE}/v2/incidents" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"${INCIDENT_NAME}\",
    \"idempotency_key\": \"${IDEMPOTENCY_KEY}\",
    \"severity_id\": \"${SEVERITY_ID}\",
    \"visibility\": \"public\",
    \"summary\": \"${SUMMARY}\"
  }")

# Check for errors
if echo "$RESPONSE" | grep -q '"error"'; then
    echo "❌ Failed to create incident:"
    echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
    exit 1
fi

# Extract incident details
INCIDENT_ID=$(echo "$RESPONSE" | jq -r '.incident.id')
INCIDENT_REF=$(echo "$RESPONSE" | jq -r '.incident.reference')
INCIDENT_URL=$(echo "$RESPONSE" | jq -r '.incident.permalink')
SLACK_CHANNEL=$(echo "$RESPONSE" | jq -r '.incident.slack_channel_name')

echo "✅ Incident created successfully!"
echo ""
echo "  ID: $INCIDENT_ID"
echo "  Reference: $INCIDENT_REF"
echo "  URL: $INCIDENT_URL"
echo "  Slack Channel: #$SLACK_CHANNEL"

