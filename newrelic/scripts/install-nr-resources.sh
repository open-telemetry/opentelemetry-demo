#!/bin/bash
set -euo pipefail

# Source common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/common.sh"

# Check prerequisites
check_prerequisites() {
    echo "Checking Prerequisites"
    check_tool_installed terraform
    echo "All prerequisites are installed"
}

# Create New Relic resources
create_resources() {
    local terraform_dir="$SCRIPT_DIR/../terraform/nr_resources"
    local auto_approve_flag=""

    if [ "${TF_AUTO_APPROVE:-}" = "true" ]; then
        auto_approve_flag="-auto-approve"
    fi

    echo "Creating New Relic Resources"
    echo "Initializing Terraform..."
    terraform -chdir="$terraform_dir" init

    echo "Creating New Relic resources..."
    terraform -chdir="$terraform_dir" apply $auto_approve_flag
}

# Main
check_prerequisites
create_resources
echo "Resources created successfully!"
