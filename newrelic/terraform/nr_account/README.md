# New Relic Account Management Module

This Terraform module creates a New Relic sub-account and generates a license key for the OpenTelemetry Demo.

## Purpose

Use this module to:
1. Create a dedicated New Relic sub-account for the OpenTelemetry Demo
2. Grant admin group access to the sub-account
3. Create a read-only user with limited access to the sub-account
4. Generate a license key for data ingestion

## Prerequisites

- Terraform >= 1.4
- New Relic account with sub-account creation permissions
- New Relic User API Key
- `jq` command-line JSON processor (used by the access granting script)
- `curl` (usually pre-installed)

**Important**:
- The `newrelic_api_key` must belong to a user with "Organization Manager" permissions
- The `admin_group_name` must already exist in New Relic
- The API key user should be a member of the group specified in `admin_group_name`
- The `readonly_authentication_domain_name` must use basic authentication (SAML/OIDC not yet supported here)
- A readonly group will be created automatically with the name `"{subaccount_name} - ReadOnly"`
- A user will be added to this group, and an invitation sent to `readonly_user_email`

## Usage

Navigate to this directory and apply directly:

```bash
cd newrelic/terraform/account_management

# Set variables (see below)
# Initialize Terraform
terraform init

# Step 1: Create the sub-account first
terraform apply -target=newrelic_account_management.subaccount

# Step 2: Create the license key (after account is created)
terraform apply
```

**Note**: Due to a New Relic provider limitation, we need to apply in two steps. The provider validates the license key resource during planning, but the account ID isn't available until after the sub-account is created.

## Variables

| Name | Description                                                                                           | Type | Default               | Required |
|------|-------------------------------------------------------------------------------------------------------|------|-----------------------|:--------:|
| newrelic_api_key | New Relic User API Key with Organization Manager permissions, and which is part of `admin_group_name` | `string` | n/a                   | yes |
| newrelic_parent_account_id | Parent account ID for creating sub-accounts                                                           | `string` | n/a                   | yes |
| newrelic_region | New Relic region (US or EU)                                                                           | `string` | `"US"`                | no |
| subaccount_name | Name of the sub-account to create                                                                     | `string` | n/a                   | yes |
| admin_authentication_domain_name | Authentication domain containing `admin_group_name` group                                             | `string` | `"Default"`           | no |
| admin_group_name | Name of an existing group to grant `admin_role_name` in the new account                               | `string` | n/a                   | yes |
| admin_role_name | Role to grant `admin_group_name`; must have permissions to create license keys                        | `string` | `"all_product_admin"` | no |
| readonly_authentication_domain_name | Authentication domain for creating the read-only user (only basic auth supported)                     | `string` | `"Default"`           | no |
| readonly_role_name | Role to grant the `readonly_group_name` in the new account                                             | `string` | `"read_only"`         | no |
| readonly_user_email | Email address of the read-only user to create                                                         | `string` | n/a                   | yes |
| readonly_user_name | Display name of the read-only user                                                                    | `string` | n/a                   | yes |

Set variables using environment variables (recommended):
- `TF_VAR_newrelic_api_key` - Your User API Key
- `TF_VAR_newrelic_parent_account_id` - Your parent account ID
- `TF_VAR_newrelic_region` - Region (US or EU, defaults to US)
- `TF_VAR_subaccount_name` - Name for the sub-account
- `TF_VAR_admin_authentication_domain_name` - Auth domain for admin (defaults to "Default")
- `TF_VAR_admin_group_name` - Existing admin group name (required)
- `TF_VAR_admin_role_name` - Admin role name (defaults to "all_product_admin")
- `TF_VAR_readonly_authentication_domain_name` - Auth domain for readonly user (defaults to "Default")
- `TF_VAR_readonly_role_name` - Readonly role name (defaults to "read_only")
- `TF_VAR_readonly_user_email` - Email address for readonly user (required)
- `TF_VAR_readonly_user_name` - Display name for readonly user (required)

Or use a `.tfvars` file:

```hcl
# terraform.tfvars
newrelic_api_key           = "your-api-key"
newrelic_parent_account_id = "1234567"
newrelic_region            = "US"
subaccount_name            = "OpenTelemetry Demo Environment"

# Admin authentication and access management
admin_authentication_domain_name = "Default"                           # Your auth domain name
admin_group_name                 = "Admins"                            # Existing group to grant access
admin_role_name                  = "all_product_admin"                 # Role for managing the account

# Read-only user setup
readonly_authentication_domain_name = "Default"                        # Auth domain for readonly user
readonly_role_name                  = "read_only"                      # Role for readonly user
readonly_user_email                 = "readonly@example.com"           # Email for readonly user
readonly_user_name                  = "ReadOnly User"                  # Display name for readonly user
```

## Outputs

| Name | Description | Sensitive |
|------|-------------|:---------:|
| account_id | The ID of the created sub-account | no |
| license_key | The license key for data ingestion | yes |
| readonly_user_email | Email address of the created read-only user | no |

## Read-Only User Setup

This module automatically creates a read-only user with full Terraform management:

**Important Notes:**
- A new group is created for each sub-account automatically
- All resources (user, group, membership) are managed by Terraform
- The user **must** check their email and follow the link to set their password
- Password setup is required before the user can log in

## Complete Workflow

### Step 1: Set Environment Variables

```bash
cd newrelic/terraform/account_management

# Set all configuration via TF_VAR_*
export TF_VAR_newrelic_api_key="your-user-api-key"
export TF_VAR_newrelic_parent_account_id="your-parent-account-id"
export TF_VAR_newrelic_region="US"
export TF_VAR_subaccount_name="OpenTelemetry Demo"

# Admin group access
export TF_VAR_admin_authentication_domain_name="Default"
export TF_VAR_admin_group_name="Admins"
export TF_VAR_admin_role_name="all_product_admin"

# Read-only user (group will be created automatically)
export TF_VAR_readonly_authentication_domain_name="Default"
export TF_VAR_readonly_role_name="read_only"
export TF_VAR_readonly_user_email="readonly@example.com"
export TF_VAR_readonly_user_name="ReadOnly User"
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

### Step 4: Create Other Resources

```bash
# Now create the license key
terraform apply
```

### Step 5: View Outputs

```bash
# Export the license key
export NEW_RELIC_LICENSE_KEY=$(terraform output -raw license_key)

# View the account ID
terraform output account_id

# View readonly user email
terraform output readonly_user_email
```

**Note**: The read-only user will receive an email with instructions to set their password. They must complete this step before they can log in.

## How It Works

This module uses a hybrid approach:

1. **Terraform Resources** manage the lifecycle of:
   - Sub-account creation (`newrelic_account_management`)
   - User creation (`newrelic_user`)
   - Group creation (`newrelic_group`)
   - Group membership (`newrelic_group_management`)
   - License key creation (`newrelic_api_access_key`)
   - Data lookups (authentication domains, groups)

2. **Shell Scripts** handle operations not available in the Terraform provider:
   - `grant_access.sh`: Grants group access to the sub-account (called on apply)
   - `revoke_access.sh`: Revokes group access from the sub-account (called on destroy)

This separation ensures proper resource management while handling provider limitations. Access grants are automatically cleaned up when running `terraform destroy`.

## Finding Your New Relic Configuration Values

### Authentication Domain Name
1. Log into [New Relic](https://one.newrelic.com)
2. Click the user menu (bottom left) → **Administration**
3. In the left sidebar, click **Access management** → **Authentication domains**
4. You'll see a list of authentication domains with their names
5. Copy the exact name (case-sensitive) - usually `"Default"` for most accounts
6. **Example names**: `Default`, `Custom Domain`, `SAML Domain`

### Role Names
1. From the same **Administration** page
2. Click **Access management** → **Roles**
3. You'll see roles like:
   - `all_product_admin` ← (full access including API keys)
   - `standard_user` (limited access)
   - `read_only` (view-only access)
   - Custom roles (if your org has created any)

**Note**: Role names in New Relic's API use snake_case (e.g., `all_product_admin`), not the display names shown in the UI (e.g., "All Product Admin")

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

