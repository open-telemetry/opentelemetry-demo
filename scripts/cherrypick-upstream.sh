#!/usr/bin/env bash
set -euo pipefail

# ---- config via env ----
: "${UPSTREAM_REPO:=open-telemetry/opentelemetry-demo}"
: "${UPSTREAM_BRANCH:=main}"
: "${FORK_BRANCH:=main}"                  # base branch in your fork (PR base)
# Prefix only; the working branch is ${SYNC_BRANCH}-YYYY-MM-DD (local date).
: "${SYNC_BRANCH:=sync/upstream}"

today="$(date +%Y-%m-%d)"
HEAD_BRANCH="${SYNC_BRANCH}-${today}"

# Open a draft PR before merging (local + CI). Set CHERRYPICK_EARLY_DRAFT_PR=0 to skip (legacy push-then-merge only).
EARLY_DRAFT=false
if [ "${CHERRYPICK_EARLY_DRAFT_PR:-1}" != "0" ]; then
  EARLY_DRAFT=true
fi

count_unpushed() {
  if git show-ref --verify --quiet "refs/remotes/origin/${HEAD_BRANCH}"; then
    git rev-list --count "origin/${HEAD_BRANCH}..HEAD"
  else
    git rev-list --count "origin/${FORK_BRANCH}..HEAD"
  fi
}

push_and_update_pr() {
  echo "Pushing '${HEAD_BRANCH}' to origin..."
  git push -u origin "${HEAD_BRANCH}"

  total_applied="$(git rev-list --count "origin/${FORK_BRANCH}..HEAD")"
  pr_title="chore: sync upstream ${today}"
  pr_body="Automated merge of ${total_applied} commit(s) from \`${UPSTREAM_REPO}@${UPSTREAM_BRANCH}\` as of ${today}."

  existing_pr="$(gh pr list --head "${HEAD_BRANCH}" --base "${FORK_BRANCH}" --json number --jq '.[0].number' 2>/dev/null || true)"

  if [ -n "${existing_pr}" ]; then
    echo "Updating existing PR #${existing_pr}..."
    gh pr edit "${existing_pr}" --title "${pr_title}" --body "${pr_body}"
    gh pr view "${existing_pr}" --json url --jq '"PR: " + .url'
  else
    echo "Opening new PR..."
    gh pr create \
      --head "${HEAD_BRANCH}" \
      --base "${FORK_BRANCH}" \
      --title "${pr_title}" \
      --body "${pr_body}"
    existing_pr="$(gh pr list --head "${HEAD_BRANCH}" --base "${FORK_BRANCH}" --json number --jq '.[0].number' 2>/dev/null || true)"
  fi

  if [ "${CHERRYPICK_LEAVE_DRAFT_ON_SUCCESS:-0}" != "1" ] && [ -n "${existing_pr}" ]; then
    is_draft="$(gh pr view "${existing_pr}" --json isDraft --jq '.isDraft' 2>/dev/null || echo false)"
    if [ "${is_draft}" = "true" ]; then
      gh pr ready "${existing_pr}"
    fi
  fi
}

# ---- safety: don't run if a merge is already in progress ----
GIT_DIR="$(git rev-parse --git-dir)"
if [ -f "${GIT_DIR}/MERGE_HEAD" ]; then
  echo "A merge is already in progress on this repo checkout."
  echo "Resolve it first, then run:"
  echo "  git status"
  echo "  git add <files>"
  echo "  git merge --continue   # or --abort"
  echo "Then re-run this script to push and open the PR."
  exit 2
fi

# Ensure remotes exist
if ! git remote get-url upstream >/dev/null 2>&1; then
  git remote add upstream "https://github.com/${UPSTREAM_REPO}.git"
fi

# Fetch latest state from both remotes
git fetch --prune origin
git fetch --prune upstream "${UPSTREAM_BRANCH}"

# ---- checkout dated sync branch ----
# If we're already on the branch (resuming after a conflict resolution),
# do NOT reset it — that would discard the resolved commits.
current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "${current_branch}" = "${HEAD_BRANCH}" ]; then
  echo "Already on '${HEAD_BRANCH}', resuming..."
elif git show-ref --verify --quiet "refs/remotes/origin/${HEAD_BRANCH}"; then
  git checkout -B "${HEAD_BRANCH}" "origin/${HEAD_BRANCH}"
else
  git checkout -B "${HEAD_BRANCH}" "origin/${FORK_BRANCH}"
fi

new_commits="$(git rev-list --count "HEAD..upstream/${UPSTREAM_BRANCH}")"
unpushed="$(count_unpushed)"
merge_succeeded=false

if [ "${new_commits}" -eq 0 ] && [ "${unpushed}" -eq 0 ]; then
  echo "No new upstream commits to merge."
  echo "Commits to be merged: 0"
  exit 0
fi

pr_num=""

if [ "${new_commits}" -gt 0 ]; then
  echo "Merging ${new_commits} new upstream commit(s) into '${HEAD_BRANCH}'..."

  if [ "${EARLY_DRAFT}" = "true" ]; then
    if [ "$(git rev-parse HEAD)" = "$(git rev-parse "origin/${FORK_BRANCH}")" ]; then
      git commit --allow-empty -m "chore: start upstream sync (${UPSTREAM_REPO}@${UPSTREAM_BRANCH})"
    fi
    git push -u origin "${HEAD_BRANCH}"

    pr_num="$(gh pr list --head "${HEAD_BRANCH}" --base "${FORK_BRANCH}" --json number --jq '.[0].number' 2>/dev/null || true)"
    if [ -z "${pr_num}" ]; then
      gh pr create --draft \
        --head "${HEAD_BRANCH}" \
        --base "${FORK_BRANCH}" \
        --title "chore: sync upstream ${today} (in progress)" \
        --body "Upstream sync in progress — automation will update this PR."
      pr_num="$(gh pr list --head "${HEAD_BRANCH}" --base "${FORK_BRANCH}" --json number --jq '.[0].number' 2>/dev/null || true)"
    fi
  else
    if ! git show-ref --verify --quiet "refs/remotes/origin/${HEAD_BRANCH}"; then
      git push -u origin "${HEAD_BRANCH}"
    fi
  fi

  # Merge upstream — preserves upstream commit SHAs so GitHub correctly tracks
  # the fork's divergence. This is why cherry-pick caused "N commits behind":
  # cherry-pick creates new SHAs and GitHub counts them as unrelated commits.
  if ! git merge "upstream/${UPSTREAM_BRANCH}" --no-edit -m "chore: merge upstream ${UPSTREAM_REPO}@${UPSTREAM_BRANCH}"; then
    if [ "${EARLY_DRAFT}" = "true" ]; then
      if [ "${GITHUB_ACTIONS:-false}" = "true" ]; then
        git merge --abort
      fi
      if [ -n "${pr_num}" ]; then
        run_link=""
        if [ -n "${GITHUB_SERVER_URL:-}" ] && [ -n "${GITHUB_REPOSITORY:-}" ] && [ -n "${GITHUB_RUN_ID:-}" ]; then
          run_link="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"
        fi
        if [ "${GITHUB_ACTIONS:-false}" = "true" ]; then
          where="in CI"
        else
          where="while running the sync script locally"
        fi
        comment="Merge from \`${UPSTREAM_REPO}@${UPSTREAM_BRANCH}\` hit conflicts ${where}.

**To continue:**
1. \`git fetch origin upstream\`
2. \`git checkout ${HEAD_BRANCH}\`
3. If you are not mid-merge: \`git merge upstream/${UPSTREAM_BRANCH}\`
4. Resolve conflicts, \`git add\` the files, then \`git merge --continue\`
5. \`git push origin ${HEAD_BRANCH}\`

Re-run \`scripts/cherrypick-upstream.sh\` to refresh the PR title and body."
        if [ -n "${run_link}" ]; then
          comment="${comment}

**Workflow run:** ${run_link}"
        fi
        gh pr comment "${pr_num}" --body "${comment}"
      fi
    else
      echo ""
      echo "Merge conflict detected."
      echo "Resolve the conflicts, then run:"
      echo "  git add <files>"
      echo "  git merge --continue"
      echo "Then re-run this script to push and open the PR."
    fi
    exit 1
  fi
  merge_succeeded=true
  echo "Done. '${HEAD_BRANCH}' updated with ${new_commits} new commit(s)."
fi

unpushed="$(count_unpushed)"
if [ "${unpushed}" -gt 0 ] || [ "${merge_succeeded}" = true ]; then
  push_and_update_pr
fi
