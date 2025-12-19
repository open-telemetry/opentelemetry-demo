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
MERGE_BASE="${MERGE_BASE:-}"

TS=$(date +"%Y%m%d_%H%M%S")
TS_FULL=$(date +"%Y-%m-%d %H:%M:%S")
ORIGIN_REPO_URL=$(git config --get remote.origin.url)
SSH_REGEX='^git@github.com:([^/]+)/([^.]+)(\.git)?$'
HTTPS_REGEX='^https://github.com/([^/]+)/([^.]+)(\.git)?$'
TAG_REGEX='^([0-9a-fA-F]+),refs/tags/([0-9]+\.[0-9]+\.[0-9]+)$'

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

DISPLAY_MERGE_BASE=""

if [ "$MERGE_BASE" == "" ]; then
  echo "MERGE_BASE is not set, using latest tag"
  TAGS=$(git ls-remote --tags --sort='-creatordate' $UPSTREAM_REMOTE | awk '{ print $1 "," $2 }')
  read -ra ATAGS <<< $TAGS
  for TAG in "${ATAGS[@]}"; do
    if [[ $TAG =~ $TAG_REGEX ]]; then
      MERGE_BASE=${BASH_REMATCH[1]}
      DISPLAY_MERGE_BASE="$UPSTREAM_REMOTE/${BASH_REMATCH[2]}"
      echo "using latest tag $DISPLAY_MERGE_BASE as MERGE_BASE"
      break
    fi
  done
else
  MERGE_BASE="$UPSTREAM_REMOTE/$MERGE_BASE"
  DISPLAY_MERGE_BASE="$MERGE_BASE"
  echo "using provided MERGE_BASE on $UPSTREAM_REMOTE: $DISPLAY_MERGE_BASE"
fi

echo "starting merge from $DISPLAY_MERGE_BASE"
git fetch $UPSTREAM_REMOTE
git checkout main

AHEAD=$(git rev-list $MERGE_BASE..main --count)
BEHIND=$(git rev-list main..$MERGE_BASE --count)

if [ $BEHIND -eq 0 ]; then
  echo "main already up-to-date with merge base, no merge needed"
  exit 0
fi

echo "main is behind merge base by $BEHIND commits and ahead by $AHEAD commits"
git checkout -b chore/sync-upstream_$TS

echo "merging changes from $DISPLAY_MERGE_BASE into local main branch"
git merge $MERGE_BASE -m "chore: sync with $DISPLAY_MERGE_BASE on $TS_FULL"
if [ $? -ne 0 ]; then
  echo "merge failed, possibly due to conflicts"
  exit 1
fi

echo "pushing merge branch to origin"
git push -u origin chore/sync-upstream_$TS

gh pr create --head $REPO_OWNER:chore/sync-upstream_$TS \
  --title "chore: sync with $DISPLAY_MERGE_BASE on $TS_FULL" \
  --body "This PR was generated on $TS_FULL by merge-upstream.sh to sync the $TARGET_REPO main branch with $DISPLAY_MERGE_BASE." \
  --base main \
  --repo $TARGET_REPO

if [ $? -ne 0 ]; then
  echo "create pull request against $TARGET_REPO failed"
  exit 1
else
  echo "pull request for merged changes created successfully against $TARGET_REPO"
fi

echo "merge completed successfully"
