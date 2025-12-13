#!/bin/bash
# Create a new feature branch from updated main

set -e

# Check if feature name was provided
if [ -z "$1" ]; then
    echo "Usage: ./new-feature.sh <feature-name>"
    echo "Example: ./new-feature.sh add-dark-mode"
    exit 1
fi

FEATURE_NAME="$1"
BRANCH_NAME="feature/${FEATURE_NAME}"

echo "Creating feature branch: $BRANCH_NAME"

# Switch to main and update
git checkout main
git pull origin main

# Create and switch to feature branch
git checkout -b "$BRANCH_NAME"

echo ""
echo "✓ Feature branch '$BRANCH_NAME' created and ready!"
echo ""
echo "Next steps:"
echo "  1. Make your changes"
echo "  2. git add <files> && git commit -m 'feat: description'"
echo "  3. git push -u origin $BRANCH_NAME"
echo "  4. gh pr create --base main"
