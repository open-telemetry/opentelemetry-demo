---
name: open-pr
description: Rebase an Incident Zero branch on origin/main, push it (never main), and open a PR using the hackathon template. Drafts the PR text for the human to approve verbatim before anything is posted. Use when the user asks to open, create, or submit a PR.
---

# Open a PR

Run only after `verify-change` and `check-rules` have passed.

## 1. Rebase
```bash
git fetch origin
git rebase origin/main
```
- Resolve conflicts by keeping both sides' intent. If unsure whose change wins, ask the module owner.
- Re-run `pytest -q` and `ruff check .` after the rebase. Use the `verify-change` skill.

## 2. Push the branch
```bash
git push -u origin <branch>
```
- The branch must match `<type>/<issue#>-<slug>`. Never push to `main`. Never force-push.

## 3. Draft the PR text
- Fill in every section of `docs/hackathon/templates/pull_request_template.md`.
- Include `Closes #<n>`.
- Put real commands and trimmed real output in "How I tested it". Include "Not tested" and limitations.
- Fill in the "Safety and rules check" boxes from the `check-rules` result. Do not tick a box that did not pass.
- In "AI assistance", name the tool and model. The human author must be able to explain every line.
- Keep the PR under about 400 changed lines. If it is larger, split it.

## 4. Get human approval before posting
The repo's `AGENTS.md` says an AI agent may post only text that a human wrote or approved verbatim immediately before posting. This applies to PR descriptions, comments, and replies.
- Show the full PR title and body to the user.
- Ask: "Post this exact text? Reply yes, or give edits."
- If approval is ambiguous, do not post. Ask again for the exact text.
- If the user edits, show the new text and get approval again.

## 5. Open the PR
```bash
gh pr create --base main --head <branch> --title "<approved title>" --body-file <approved-body-file>
```
- Use the approved text exactly. Do not add footers, signatures, or generated-by lines unless the user approved them.
- Report the PR URL.

## 6. Never
- Approve or merge the PR. Only a human does that, after another teammate approves.
- Add a `Co-authored-by:` trailer. Use `Assisted-by:` on commits if the code was produced with AI assistance.
- Open a PR that fails `check-rules` without saying so in the PR body.
