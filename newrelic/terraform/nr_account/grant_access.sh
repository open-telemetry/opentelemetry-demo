#!/bin/bash
set -e

API_KEY="$1"
REGION="$2"
AUTH_DOMAIN_NAME="$3"
GROUP_NAME="$4"
ROLE_NAME="$5"
ACCOUNT_ID="$6"

API_ENDPOINT="https://api.${REGION}.com/graphql"

# Helper function to execute GraphQL queries
graphql_query() {
  curl -s -X POST "$API_ENDPOINT" \
    -H "Content-Type: application/json" \
    -H "API-Key: $API_KEY" \
    -d "$1"
}

# Get authentication domain ID
AUTH_DOMAIN_ID=$(graphql_query '{"query":"{ actor { organization { userManagement { authenticationDomains { authenticationDomains { id name } } } } } }"}' \
  | jq -r ".data.actor.organization.userManagement.authenticationDomains.authenticationDomains[] | select(.name == \"$AUTH_DOMAIN_NAME\") | .id")

[ -z "$AUTH_DOMAIN_ID" ] || [ "$AUTH_DOMAIN_ID" = "null" ] && echo "Error: Authentication domain '$AUTH_DOMAIN_NAME' not found" && exit 1
echo "Using Authentication Domain: $AUTH_DOMAIN_NAME (ID: $AUTH_DOMAIN_ID)"

# Get group ID
GROUP_ID=$(graphql_query "{\"query\": \"{ actor { organization { userManagement { authenticationDomains(id: \\\"$AUTH_DOMAIN_ID\\\") { authenticationDomains { groups { groups { id displayName } } } } } } } }\"}" \
  | jq -r ".data.actor.organization.userManagement.authenticationDomains.authenticationDomains[0].groups.groups[] | select(.displayName == \"$GROUP_NAME\") | .id")

[ -z "$GROUP_ID" ] || [ "$GROUP_ID" = "null" ] && echo "Error: Group '$GROUP_NAME' not found" && exit 1
echo "Found group: $GROUP_NAME (ID: $GROUP_ID)"

# Get role ID
ROLE_ID=$(graphql_query '{"query":"{ actor { organization { authorizationManagement { roles { roles { id name type } } } } } }"}' \
  | jq -r ".data.actor.organization.authorizationManagement.roles.roles[] | select(.name == \"$ROLE_NAME\") | .id")

[ -z "$ROLE_ID" ] || [ "$ROLE_ID" = "null" ] && echo "Error: Role '$ROLE_NAME' not found" && exit 1
echo "Using role: $ROLE_NAME (ID: $ROLE_ID)"

# Grant access
echo "Granting group access to sub-account..."
GRANT_RESPONSE=$(graphql_query "{\"query\": \"mutation { authorizationManagementGrantAccess(grantAccessOptions: {groupId: \\\"$GROUP_ID\\\", accountAccessGrants: [{accountId: $ACCOUNT_ID, roleId: \\\"$ROLE_ID\\\"}]}) { roles { accountId roleId } } }\"}")

# Check for errors
ERROR=$(echo "$GRANT_RESPONSE" | jq -r '.errors // empty')
[ -n "$ERROR" ] && echo "Error: Failed to create grant" && echo "$GRANT_RESPONSE" | jq -r '.errors' && exit 1

echo "Grant created. Waiting for permissions to propagate (up to 5 minutes)..."

# Poll until API key can access the account
for i in $(seq 1 60); do
  echo "Checking grant status (attempt $i/60)..."

  RESPONSE=$(graphql_query "{\"query\": \"{ actor { account(id: $ACCOUNT_ID) { id name } } }\"}")

  [ $i -eq 1 ] && echo "Poll response: $RESPONSE"

  ACCESSIBLE=$(echo "$RESPONSE" | jq -r '.data.actor.account.id // empty')

  if [ "$ACCESSIBLE" = "$ACCOUNT_ID" ]; then
    echo "Grant confirmed! API key can now access the account."
    exit 0
  fi

  [ $i -lt 60 ] && echo "Account not accessible yet, waiting 10 seconds..." && sleep 10
done

echo "Error: Grant not confirmed after 5 minutes."
echo "Please verify your API key user is a member of the '$GROUP_NAME' group."
exit 1
