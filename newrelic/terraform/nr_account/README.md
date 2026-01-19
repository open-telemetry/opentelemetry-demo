# New Relic Account Management Module

This Terraform module creates a New Relic sub-account and generates a license key for the OpenTelemetry Demo.

## Purpose

Use this module to:
1. Create a dedicated New Relic sub-account for the OpenTelemetry Demo
2. Generate a license key for data ingestion
3. Get credentials ready for the `install-k8s.sh` script

## Prerequisites

- Terraform >= 1.4
- New Relic account with sub-account creation permissions
- New Relic User API Key
- `jq` command-line JSON processor (used by the access granting script)
- `curl` (usually pre-installed)

**Important**: The User API Key must belong to a user who is a member of the group specified in `admin_group_name`. The module grants permissions to the group, not directly to the user. If the API key user is not in the group, license key creation will fail with a permission error.

## Usage

Navigate to this directory and apply directly:

```bash
cd newrelic/terraform/account_management

# Set Terraform variables (all provider config via TF_VAR_*)
export TF_VAR_newrelic_api_key="your-user-api-key"
export TF_VAR_newrelic_parent_account_id="your-parent-account-id"
export TF_VAR_newrelic_region="US"  # or "EU" (optional, defaults to "US")
export TF_VAR_subaccount_name="OpenTelemetry Demo Environment"

# Initialize Terraform
terraform init

# Step 1: Create the sub-account first
terraform apply -target=newrelic_account_management.subaccount

# Step 2: Create the license key (after account is created)
terraform apply
```

**Note**: Due to a New Relic provider limitation, we need to apply in two steps. The provider validates the license key resource during planning, but the account ID isn't available until after the sub-account is created.

## Variables

| Name | Description | Type | Default               | Required |
|------|-------------|------|-----------------------|:--------:|
| newrelic_api_key | New Relic User API Key | `string` | n/a                   | yes |
| newrelic_parent_account_id | Parent account ID for creating sub-accounts | `string` | n/a                   | yes |
| newrelic_region | New Relic region (US or EU) | `string` | `"US"`                | no |
| subaccount_name | Name of the sub-account to create | `string` | n/a                   | yes |
| authentication_domain_name | Authentication domain name to use | `string` | `"Default"`           | no |
| admin_group_name | Name of an existing group to grant access | `string` | n/a                   | yes |
| admin_role_name | Role to grant for admin access | `string` | `"all_product_admin"` | no |

Set variables using environment variables (recommended):
- `TF_VAR_newrelic_api_key` - Your User API Key
- `TF_VAR_newrelic_parent_account_id` - Your parent account ID
- `TF_VAR_newrelic_region` - Region (US or EU, defaults to US)
- `TF_VAR_subaccount_name` - Name for the sub-account
- `TF_VAR_authentication_domain_name` - Auth domain (defaults to "Default")
- `TF_VAR_admin_group_name` - Existing group name (required)
- `TF_VAR_admin_role_name` - Role name (defaults to "all_product_admin")

Or use a `.tfvars` file:

```hcl
# terraform.tfvars
newrelic_api_key           = "your-api-key"
newrelic_parent_account_id = "1234567"
newrelic_region            = "US"
subaccount_name            = "OpenTelemetry Demo Environment"

# Authentication and access management
authentication_domain_name = "Default"                           # Your auth domain name
admin_group_name           = "Admins"                            # Existing group to grant access
admin_role_name            = "all_product_admin"                 # Role for managing the account
```

## Outputs

| Name | Description | Sensitive |
|------|-------------|:---------:|
| account_id | The ID of the created sub-account | no |
| license_key | The license key for data ingestion | yes |

## Complete Workflow

### Step 1: Set Environment Variables

```bash
cd newrelic/terraform/account_management

# Set all configuration via TF_VAR_* (consistent!)
export TF_VAR_newrelic_api_key="your-user-api-key"
export TF_VAR_newrelic_parent_account_id="your-parent-account-id"
export TF_VAR_newrelic_region="US"
export TF_VAR_subaccount_name="OpenTelemetry Demo"
```

### Step 2: Initialize Terraform

```bash
terraform init
```

### Step 3: Create Sub-Account

```bash
# Create the sub-account first
terraform apply -target=newrelic_account_management.subaccount
```

### Step 4: Create License Key

```bash
# Now create the license key
terraform apply
```

### Step 5: Export License Key

```bash
export NEW_RELIC_LICENSE_KEY=$(terraform output -raw license_key)
```

## Finding Your New Relic Configuration Values

### Authentication Domain Name
1. Log into [New Relic](https://one.newrelic.com)
2. Click the user menu (bottom left) → **Administration**
3. In the left sidebar, click **Access management** → **Authentication domains**
4. You'll see a list of authentication domains with their names
5. Copy the exact name (case-sensitive) - usually `"Default"` for most accounts
6. **Example names**: `Default`, `Custom Domain`, `SAML Domain`

### Admin Role Name
1. From the same **Administration** page
2. Click **Access management** → **Roles**
3. You'll see roles like:
   - `all_product_admin` ← **Recommended** (full access including API keys)
   - `standard_user` (limited access)
   - `read_only` (view-only access)
   - Custom roles (if your org has created any)
4. Use the exact role name as displayed - role names use `snake_case` format
5. **Default**: `"all_product_admin"` works for most use cases
6. **Note**: Role names in New Relic's API use snake_case (e.g., `all_product_admin`), not the display names shown in the UI (e.g., "All Product Admin")

### Admin Group Name
1. From the same **Administration** page
2. Click **Access management** → **Groups**
3. You'll see a list of groups in each authentication domain
4. Select your authentication domain from the dropdown
5. Find a group **that you are already a member of**
6. Copy the exact group name (case-sensitive)
7. **Common examples**: `Admins`, `Admin`, `Terraform Users`, `Developers`
8. **Important**:
   - This group must already exist in New Relic
   - You must be a member of this group
   - Terraform will grant this group access to the new sub-account

### Quick Verification Command
If you want to verify your values before running Terraform, you can query the NerdGraph API:

```bash
# Replace YOUR_API_KEY and AUTH_DOMAIN_ID with your values
# First, get your authentication domains
curl -X POST https://api.newrelic.com/graphql \
  -H "Content-Type: application/json" \
  -H "API-Key: YOUR_API_KEY" \
  -d '{"query":"{ actor { organization { userManagement { authenticationDomains { authenticationDomains { id name } } } authorizationManagement { roles { roles { id name type } } } } } }"}' \
  | jq '.data.actor.organization'

# Then, get groups for a specific authentication domain
curl -X POST https://api.newrelic.com/graphql \
  -H "Content-Type: application/json" \
  -H "API-Key: YOUR_API_KEY" \
  -d '{"query":"{ actor { organization { userManagement { authenticationDomains(id: \"YOUR_AUTH_DOMAIN_ID\") { authenticationDomains { groups { groups { id displayName } } } } } } } }"}' \
  | jq '.data.actor.organization.userManagement.authenticationDomains.authenticationDomains[0].groups.groups'
```

This will show you:
- All authentication domains (`.userManagement.authenticationDomains.authenticationDomains[]`)
- All available roles (`.authorizationManagement.roles.roles[]`)
- All groups in a specific authentication domain

## Troubleshooting

### Error: "You do not have permission to create this key"

This error occurs during license key creation if the User API Key doesn't belong to a user who is a member of the group specified in `admin_group_name`.

**Solution**: Ensure the user associated with your API key is a member of the group you're granting access to. The module grants permissions to the group, not directly to users, so your API key user must be in that group to inherit the permissions.

**Steps to verify**:
1. Check which groups your user belongs to in New Relic's User Management UI
2. Ensure you're using a group that your user is already a member of for the `admin_group_name` variable
3. If needed, add your user to the group before running Terraform

**Alternative**: Use an API key from a user who is already a member of the admin group, or create the license key manually in the New Relic UI after the sub-account is created.

## Notes

- The license key is created with `INGEST` type and `LICENSE` ingest type
- The sub-account is created in your specified region (US or EU)
- You need admin-level permissions in your parent account to create sub-accounts
- The license key output is marked as sensitive, retrieve it with: `terraform output -raw license_key`
- The specified group will be granted access to the sub-account with the admin role
- **Important**: You must already be a member of the specified group before running Terraform
- If authentication domain, group, or role lookup fails, the script will show available options
