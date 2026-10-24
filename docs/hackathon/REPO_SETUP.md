# Repo setup (5 minutes, do it once)

## Repo owner (one person)
1. Copy these files into the root of our forked template repo (keep the folder structure), commit on a branch, PR, merge.
2. GitHub → **Settings → Branches → Add branch protection rule** for `main`:
   - ✅ Require a pull request before merging → Require **1 approval**
   - ✅ Require conversation resolution before merging
   - ✅ Require branches to be up to date before merging
   - ✅ Do not allow bypassing the above settings
   - ❌ Allow force pushes / ❌ Allow deletions
3. Settings → General → Pull Requests: allow **Squash merging** only; enable **Automatically delete head branches**.
4. Create labels: `P0`, `P1`, `P2`, `platform`, `tools`, `agent`, `safety`, `eval-docs`, `interface-change`, `bug`.
5. Fill in owner names in `AGENTS.md` §6.

## Every teammate
```bash
git clone <repo> && cd <repo>
git config user.name "Your Name"; git config user.email "you@example.com"   # your OWN identity
bash scripts/setup-hooks.sh
```
Then open your coding agent in the repo and tell it: *"Read AGENTS.md and docs/TEAM_CONTEXT.md, then work on issue #N."*

## Daily loop
```
pick issue → git pull --rebase origin main → git checkout -b feat/N-slug
→ plan → code → test (unit + full suite + real run) → commit → rebase → push → PR
→ teammate reviews → squash merge → everyone pulls
```
