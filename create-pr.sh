#!/bin/bash
# Push current branch and create a PR to main

set -e

# Get current branch name
BRANCH=$(git branch --show-current)

# Check we're not on main
if [ "$BRANCH" = "main" ]; then
    echo "Error: You're on main branch. Switch to a feature branch first."
    exit 1
fi

# Check if title was provided
if [ -z "$1" ]; then
    echo "Usage: ./create-pr.sh \"<PR title>\" [\"<summary>\"]"
    echo "Example: ./create-pr.sh \"Add user authentication\" \"Implements OAuth2 login flow\""
    exit 1
fi

TITLE="$1"
SUMMARY="${2:-Describe what this PR does}"

echo "Pushing branch: $BRANCH"
git push -u origin "$BRANCH"

echo ""
echo "Creating PR..."

gh pr create --base main --title "$TITLE" --body "## Summary
- $SUMMARY

## Test plan
- [ ] Tested locally
- [ ] Verified no TEST manifests included
"

echo ""
echo "✓ PR created successfully!"
