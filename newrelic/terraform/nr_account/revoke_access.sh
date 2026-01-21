#!/bin/bash
set -e

API_KEY="$1"
REGION="$2"
GROUP_ID="$3"
ROLE_NAME="$4"
ACCOUNT_ID="$5"

API_ENDPOINT="https://api.${REGION}.com/graphql"

# Helper function to execute GraphQL queries
graphql_query() {
  curl -s -X POST "$API_ENDPOINT" \
    -H "Content-Type: application/json" \
    -H "API-Key: $API_KEY" \
    -d "$1"
}

echo "Revoking group access from sub-account..."
echo "Group ID: $GROUP_ID"
echo "Role ID: $ROLE_ID"
echo "Account ID: $ACCOUNT_ID"

# Get role ID
echo "Looking up role: $ROLE_NAME"
ROLE_ID=$(graphql_query '{"query":"{ actor { organization { authorizationManagement { roles { roles { id name type } } } } } }"}' \
  | jq -r ".data.actor.organization.authorizationManagement.roles.roles[] | select(.name == \"$ROLE_NAME\") | .id")

[ -z "$ROLE_ID" ] || [ "$ROLE_ID" = "null" ] && echo "Error: Role '$ROLE_NAME' not found" && exit 1
echo "Found role: $ROLE_NAME (ID: $ROLE_ID)"

# Revoke access
echo "Revoking access..."
REVOKE_RESPONSE=$(graphql_query "{\"query\": \"mutation { authorizationManagementRevokeAccess(revokeAccessOptions: {groupId: \\\"$GROUP_ID\\\", accountAccessGrants: [{accountId: $ACCOUNT_ID, roleId: \\\"$ROLE_ID\\\"}]}) { roles { accountId roleId } } }\"}")

# Check for errors
ERROR=$(echo "$REVOKE_RESPONSE" | jq -r '.errors // empty')
if [ -n "$ERROR" ]; then
  # Check if access grant doesn't exist (already revoked)
  if echo "$ERROR" | grep -q "not found\|does not exist"; then
    echo "Access grant already revoked or does not exist, continuing..."
  else
    echo "Error: Failed to revoke access"
    echo "$REVOKE_RESPONSE" | jq -r '.errors'
    exit 1
  fi
else
  echo "Access revoked successfully"
fi
