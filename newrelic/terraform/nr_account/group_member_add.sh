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

echo "Adding user to group..."
echo "Authentication Domain ID: $AUTH_DOMAIN_ID"
echo "Group ID: $GROUP_ID"
echo "User ID: $USER_ID"

# Add user to group
ADD_RESPONSE=$(graphql_query "{\"query\": \"mutation { userManagementAddUsersToGroups(addUsersToGroupsOptions: {groupIds: [\\\"$GROUP_ID\\\"], userIds: [\\\"$USER_ID\\\"]}) { groups { displayName } } }\"}")

# Check for errors
ERROR=$(echo "$ADD_RESPONSE" | jq -r '.errors // empty')
if [ -n "$ERROR" ]; then
  # Check if already a member
  if echo "$ERROR" | grep -q "already"; then
    echo "User is already a member of the group, continuing..."
  else
    echo "Error: Failed to add user to group"
    echo "$ADD_RESPONSE" | jq -r '.errors'
    exit 1
  fi
else
  echo "User added to group successfully"
fi

echo ""
echo "============================================================================"
echo "User group membership completed"
echo "============================================================================"
echo "User ID: $USER_ID"
echo "Group ID: $GROUP_ID"
echo "============================================================================"
