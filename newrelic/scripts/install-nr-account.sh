#!/bin/bash
set -euo pipefail

# Source common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/common.sh"

# Check prerequisites
check_prerequisites() {
    echo "Checking Prerequisites"
    check_tool_installed terraform
    check_tool_installed jq
    check_tool_installed curl
    echo "All prerequisites are installed"
}

# Gather Terraform configuration
gather_config() {
    prompt_for_env_var "TF_VAR_newrelic_api_key" "Please enter your New Relic API Key" true
    prompt_for_env_var "TF_VAR_newrelic_parent_account_id" "Please enter your New Relic Parent Account ID" true
    prompt_for_env_var "TF_VAR_newrelic_region" "Please enter your New Relic Region (US/EU, default: US)" false
    prompt_for_env_var "TF_VAR_subaccount_name" "Please enter a name for the sub-account" true
    prompt_for_env_var "TF_VAR_authentication_domain_name" "Please enter the authentication domain name (default: Default)" false
    prompt_for_env_var "TF_VAR_admin_group_name" "Please enter the admin group name (must exist in New Relic)" true
    prompt_for_env_var "TF_VAR_admin_role_name" "Please enter the admin role name (default: all_product_admin)" false
}

# Create New Relic sub-account and license key
create_account() {
    local terraform_dir="$SCRIPT_DIR/../terraform/nr_account"
    local auto_approve_flag=""

    if [ "${TF_AUTO_APPROVE:-}" = "true" ]; then
        auto_approve_flag="-auto-approve"
    fi

    echo "Creating New Relic Sub-Account"
    echo "Initializing Terraform..."
    terraform -chdir="$terraform_dir" init -input=false

    echo "Creating sub-account..."
    terraform -chdir="$terraform_dir" apply -target=newrelic_account_management.subaccount $auto_approve_flag
    echo "Sub-account created with ID: $(terraform -chdir="$terraform_dir" output -raw account_id)"

    echo "Granting access and creating license key..."
    terraform -chdir="$terraform_dir" apply $auto_approve_flag
}

# Main
check_prerequisites
gather_config
create_account
echo "Account created successfully and access granted!"
