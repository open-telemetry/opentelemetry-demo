#!/bin/bash
set -euo pipefail

# Source common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/common.sh"

# Destroy New Relic resources
destroy_resources() {
    local terraform_dir="$SCRIPT_DIR/../terraform/nr_resources"
    local auto_approve_flag=""

    if [ "${TF_AUTO_APPROVE:-}" = "true" ]; then
        auto_approve_flag="-auto-approve"
    fi

    echo "Destroying New Relic Resources"

    if [ -f "$terraform_dir/terraform.tfstate" ]; then
        echo "Destroying New Relic resources..."
        terraform -chdir="$terraform_dir" destroy $auto_approve_flag
        echo "New Relic resources destroyed"
    else
        echo "No Terraform state found, skipping"
    fi
}

# Main execution
echo "New Relic Resources Cleanup"
check_tool_installed terraform
destroy_resources
echo "Cleanup complete!"
