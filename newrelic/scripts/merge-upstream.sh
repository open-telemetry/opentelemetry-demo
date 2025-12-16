#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# merge-upstream.sh
#
# Purpose:
#   Merges changes from the upstream repository into the origin repository and
#   creates a pull request if there are changes to merge.
#
# How to run:
#   ./merge-upstream.sh
#   (Run from the newrelic/scripts directory)
#
# Environment variables:
#   UPSTREAM_REPO_URL - Optional. URL of the upstream repository to sync from.
#                       Defaults to https://github.com/opentelemetry/opentelemetry-demo.git
#   UPSTREAM_REMOTE   - Optional. Name of the git remote for the upstream
#                       repository. Defaults to 'official'.
#   TARGET_REPO       - Optional. GitHub repository to create the pull request
#                       against in the format 'owner/repo'. Defaults to
#                       'newrelic/opentelemetry-demo'.
#   GH_TOKEN or GITHUB_TOKEN - Required. GitHub token with permissions to create
#                              pull requests. gh auth login can also be used to
#                              authenticate the GitHub CLI prior to running this
#                              script.
#
# Dependencies:
#   - git
#   - gh (GitHub CLI)
#   - Upstream remote must be configured in the local git repository
# -----------------------------------------------------------------------------
set -euo pipefail

source "$(dirname "$0")/common.sh"

check_tool_installed git
check_tool_installed gh

UPSTREAM_REPO_URL="${UPSTREAM_REPO_URL:-https://github.com/opentelemetry/opentelemetry-demo.git}"
UPSTREAM_REMOTE="${UPSTREAM_REMOTE:-official}"
TARGET_REPO="${TARGET_REPO:-newrelic/opentelemetry-demo}"

TS=$(date +"%Y%m%d_%H%M%S")
TS_FULL=$(date +"%Y-%m-%d %H:%M:%S")
ORIGIN_REPO_URL=$(git config --get remote.origin.url)
REGEX="^git@github.com:(.*)/(.*).git$"

if [[ $ORIGIN_REPO_URL =~ $REGEX ]]; then
  REPO_OWNER="${BASH_REMATCH[1]}"
  REPO_NAME="${BASH_REMATCH[2]}"
else
  echo "unable to parse repository owner/name from URL: $ORIGIN_REPO_URL"
  exit 1
fi

echo "starting merge from upstream repository: $UPSTREAM_REPO_URL"
git fetch $UPSTREAM_REMOTE
git checkout main

AHEAD=$(git rev-list $UPSTREAM_REMOTE/main..main --count)
BEHIND=$(git rev-list main..$UPSTREAM_REMOTE/main --count)

if [ $BEHIND -eq 0 ]; then
  echo "main already up-to-date with $UPSTREAM_REMOTE/main, no merge needed"
  exit 0
fi

echo "main is behind $UPSTREAM_REMOTE/main by $BEHIND commits and ahead by $AHEAD commits"
git checkout -b chore/sync-upstream_$TS

echo "merging changes from $UPSTREAM_REMOTE/main into local main branch"
git merge $UPSTREAM_REMOTE/main -m "chore: sync with $UPSTREAM_REMOTE main branch on $TS_FULL"
if [ $? -ne 0 ]; then
  echo "merge failed, possibly due to conflicts"
  exit 1
fi

echo "pushing merge branch to origin"
git push -u origin chore/sync-upstream_$TS

gh pr create --head $REPO_OWNER:chore/sync-upstream_$TS \
  --title "chore: sync with upstream main branch on $TS_FULL" \
  --body "Automated sync with upstream main branch on $TS_FULL" \
  --base main \
  --repo $TARGET_REPO

if [ $? -ne 0 ]; then
  echo "create pull request against $TARGET_REPO failed"
  exit 1
fi

echo "merge from upstream repository completed successfully"
