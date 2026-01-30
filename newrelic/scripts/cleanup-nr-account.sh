#!/bin/bash
set -euo pipefail

# Source common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/common.sh"

# Destroy New Relic sub-account
destroy_account() {
    local terraform_dir="$SCRIPT_DIR/../terraform/nr_account"
    local auto_approve_flag=""

    if [ "${TF_AUTO_APPROVE:-}" = "true" ]; then
        auto_approve_flag="-auto-approve"
    fi

    echo "Destroying New Relic Sub-Account"

    if [ -f "$terraform_dir/terraform.tfstate" ]; then
        terraform -chdir="$terraform_dir" destroy $auto_approve_flag
    else
        echo "No Terraform state found, skipping"
    fi
}

# Main
echo "New Relic Account Cleanup"
check_tool_installed terraform
destroy_account
echo "Cleanup complete!"
