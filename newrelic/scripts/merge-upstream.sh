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
#   UPSTREAM_REMOTE   - Optional. Name of the git remote for the upstream
#                       repository. Defaults to 'official'.
#   TARGET_REPO       - Optional. GitHub repository to create the pull request
#                       against in the format 'owner/repo'. Defaults to
#                       'newrelic/opentelemetry-demo'.
#   GH_TOKEN or GITHUB_TOKEN - Required. GitHub token with permissions to create
#                              issues and pull requests. gh auth login can also
#                              be used to authenticate the GitHub CLI prior to
#                              running this script. When used in GitHub Actions,
#                              the token should also have permissions to modify
#                              repository contents.
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

UPSTREAM_REMOTE="${UPSTREAM_REMOTE:-official}"
TARGET_REPO="${TARGET_REPO:-newrelic/opentelemetry-demo}"

TS=$(date +"%Y%m%d_%H%M%S")
TS_FULL=$(date +"%Y-%m-%d %H:%M:%S")
ORIGIN_REPO_URL=$(git config --get remote.origin.url)
SSH_REGEX='^git@github.com:([^/]+)/([^.]+)(\.git)?$'
HTTPS_REGEX='^https://github.com/([^/]+)/([^.]+)(\.git)?$'

if [[ $ORIGIN_REPO_URL =~ $SSH_REGEX ]]; then
  REPO_OWNER="${BASH_REMATCH[1]}"
  REPO_NAME="${BASH_REMATCH[2]}"
elif [[ $ORIGIN_REPO_URL =~ $HTTPS_REGEX ]]; then
  REPO_OWNER="${BASH_REMATCH[1]}"
  REPO_NAME="${BASH_REMATCH[2]}"
else
  echo "unable to parse repository owner/name from URL: $ORIGIN_REPO_URL"
  exit 1
fi

echo "starting merge from $UPSTREAM_REMOTE/main"
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
git merge $UPSTREAM_REMOTE/main -m "chore: sync with upstream main branch on $TS_FULL"
if [ $? -ne 0 ]; then
  echo "merge failed, possibly due to conflicts"
  exit 1
fi

echo "pushing merge branch to origin"
git push -u origin chore/sync-upstream_$TS

gh pr create --head $REPO_OWNER:chore/sync-upstream_$TS \
  --title "chore: sync with upstream main branch on $TS_FULL" \
  --body "This PR was generated on $TS_FULL by merge-upstream.sh to sync $TARGET_REPO/main with the upstream main branch" \
  --base main \
  --repo $TARGET_REPO

if [ $? -ne 0 ]; then
  echo "create pull request against $TARGET_REPO failed"
  exit 1
else
  echo "pull request for merged changes created successfully against $TARGET_REPO"
fi

echo "merge from upstream repository completed successfully"
