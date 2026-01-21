#!/bin/bash
set -e

API_KEY="$1"
REGION="$2"
AUTH_DOMAIN_ID="$3"
GROUP_ID="$4"
USER_ID="$5"

API_ENDPOINT="https://api.${REGION}.com/graphql"

# Helper function to execute GraphQL queries
graphql_query() {
  curl -s -X POST "$API_ENDPOINT" \
    -H "Content-Type: application/json" \
    -H "API-Key: $API_KEY" \
    -d "$1"
}

echo "Removing user from group..."
echo "Authentication Domain ID: $AUTH_DOMAIN_ID"
echo "Group ID: $GROUP_ID"
echo "User ID: $USER_ID"

# Remove user from group
REMOVE_RESPONSE=$(graphql_query "{\"query\": \"mutation { userManagementRemoveUsersFromGroups(removeUsersFromGroupsOptions: {groupIds: [\\\"$GROUP_ID\\\"], userIds: [\\\"$USER_ID\\\"]}) { groups { displayName } } }\"}")

# Check for errors
ERROR=$(echo "$REMOVE_RESPONSE" | jq -r '.errors // empty')
if [ -n "$ERROR" ]; then
  # Check if user is not a member (already removed)
  if echo "$ERROR" | grep -q "not a member\|not found"; then
    echo "User is not a member of the group or already removed, continuing..."
  else
    echo "Error: Failed to remove user from group"
    echo "$REMOVE_RESPONSE" | jq -r '.errors'
    exit 1
  fi
else
  echo "User removed from group successfully"
fi

echo ""
echo "============================================================================"
echo "User group membership removal completed"
echo "============================================================================"
echo "User ID: $USER_ID"
echo "Group ID: $GROUP_ID"
echo "============================================================================"
