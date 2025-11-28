#!/bin/bash
# IncidentFox: Export secrets to 1Password-compatible format
#
# This script exports all secrets from AWS Secrets Manager to a format
# that can be imported into 1Password or stored securely offline.
#
# Usage:
#   ./export-secrets-to-1password.sh
#   ./export-secrets-to-1password.sh --output /path/to/backup.json

set -euo pipefail

# Configuration
CLUSTER_NAME="${CLUSTER_NAME:-incidentfox-demo}"
OUTPUT_FILE="${1:---output}"
OUTPUT_FILE="${OUTPUT_FILE#--output=}"
OUTPUT_FILE="${OUTPUT_FILE#--output }"

if [ "$OUTPUT_FILE" = "--output" ] || [ -z "$OUTPUT_FILE" ]; then
    OUTPUT_FILE="incidentfox-secrets-$(date +%Y%m%d-%H%M%S).json"
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check prerequisites
if ! command -v aws &> /dev/null; then
    log_error "AWS CLI not found. Please install it first."
    exit 1
fi

if ! command -v jq &> /dev/null; then
    log_error "jq not found. Please install it first."
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    log_error "AWS credentials not configured or invalid"
    exit 1
fi

log_info "Exporting secrets from AWS Secrets Manager..."
log_info "Cluster: $CLUSTER_NAME"
echo ""

# Get region from AWS config
REGION=$(aws configure get region || echo "us-west-2")

# List of secrets to export
SECRETS=(
    "${CLUSTER_NAME}/postgres"
    "${CLUSTER_NAME}/grafana"
)

# Create output JSON structure
cat > "$OUTPUT_FILE" << EOF
{
  "export_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "cluster_name": "$CLUSTER_NAME",
  "region": "$REGION",
  "secrets": {}
}
EOF

# Export each secret
for secret_id in "${SECRETS[@]}"; do
    log_info "Fetching: $secret_id"
    
    if secret_value=$(aws secretsmanager get-secret-value \
        --secret-id "$secret_id" \
        --query SecretString \
        --output text 2>/dev/null); then
        
        # Add to output JSON
        secret_name=$(basename "$secret_id")
        tmp=$(mktemp)
        jq ".secrets.\"$secret_name\" = ($secret_value)" "$OUTPUT_FILE" > "$tmp"
        mv "$tmp" "$OUTPUT_FILE"
        
        log_success "✓ Exported: $secret_id"
    else
        log_warning "✗ Failed to fetch: $secret_id (may not exist yet)"
    fi
done

echo ""
log_success "Secrets exported to: $OUTPUT_FILE"
echo ""

# Display summary
log_info "Secrets Summary:"
echo ""
jq -r '.secrets | to_entries[] | "  • \(.key): \(.value | keys | join(", "))"' "$OUTPUT_FILE"
echo ""

# Generate 1Password import format
ONEPASSWORD_FILE="${OUTPUT_FILE%.json}-1password.csv"
log_info "Generating 1Password CSV format..."

cat > "$ONEPASSWORD_FILE" << 'EOF'
Title,Username,Password,URL,Notes,Type
EOF

# PostgreSQL entry
if postgres=$(jq -r '.secrets.postgres // empty' "$OUTPUT_FILE" 2>/dev/null); then
    username=$(echo "$postgres" | jq -r '.username // "otelu"')
    password=$(echo "$postgres" | jq -r '.password // ""')
    echo "IncidentFox - PostgreSQL,$username,$password,https://console.aws.amazon.com/secretsmanager/,Cluster: $CLUSTER_NAME,login" >> "$ONEPASSWORD_FILE"
    log_success "✓ Added PostgreSQL to 1Password CSV"
fi

# Grafana entry
if grafana=$(jq -r '.secrets.grafana // empty' "$OUTPUT_FILE" 2>/dev/null); then
    username=$(echo "$grafana" | jq -r '.["admin-user"] // "admin"')
    password=$(echo "$grafana" | jq -r '.["admin-password"] // ""')
    echo "IncidentFox - Grafana,$username,$password,http://grafana/,Cluster: $CLUSTER_NAME,login" >> "$ONEPASSWORD_FILE"
    log_success "✓ Added Grafana to 1Password CSV"
fi

log_success "1Password CSV exported to: $ONEPASSWORD_FILE"
echo ""

# Instructions
log_info "Next Steps:"
echo ""
echo "1. JSON Format (recommended for backup):"
echo "   • File: $OUTPUT_FILE"
echo "   • Contains full secret structure"
echo "   • Store in secure location (encrypted drive, 1Password document)"
echo ""
echo "2. 1Password Import:"
echo "   • File: $ONEPASSWORD_FILE"
echo "   • Open 1Password → File → Import → CSV"
echo "   • Select: $ONEPASSWORD_FILE"
echo "   • Choose vault: 'IncidentFox' or create new"
echo ""
echo "3. Secure the Files:"
echo "   • Move to encrypted location"
echo "   • Delete after importing to 1Password"
echo "   • Never commit to Git"
echo ""

log_warning "⚠️  IMPORTANT: These files contain sensitive passwords!"
log_warning "   Delete them after backing up to 1Password:"
echo ""
echo "   rm $OUTPUT_FILE $ONEPASSWORD_FILE"
echo ""

# Optionally display passwords (with confirmation)
read -p "Display passwords in terminal? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    log_info "Secrets (SENSITIVE - Clear terminal after viewing):"
    echo ""
    jq -C . "$OUTPUT_FILE"
    echo ""
    log_warning "Clear your terminal history after viewing!"
fi

log_success "Export complete!"

