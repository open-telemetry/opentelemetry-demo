## What & why
<!-- One paragraph. -->

Closes #

## Changes
<!-- Bullet list of files and what changed. -->
-

## Interface changes
<!-- "None", or the exact signature/JSON change + who approved it (interface-change issue #). -->
None

## How I tested it
<!-- Paste REAL commands and trimmed REAL output. No "should work". -->
- [ ] Unit tests added/updated: `pytest -q tests/...`
- [ ] Full suite passes after rebasing on latest main: `pytest -q`
- [ ] Lint passes: `ruff check .`
- [ ] Real run against: <!-- live demo / offline bundle <name> -->

```text
<command + output>
```

## Not tested / known limitations
<!-- Be honest. Stating a limitation costs nothing. -->

## Safety & rules check
- [ ] No reads of feature flags / flagd / flag config for diagnosis
- [ ] No system changes except via the Action API behind the approval gate
- [ ] No invented evidence — every evidence item comes from a real tool output
- [ ] No secrets, `.env`, or large data files committed
- [ ] Changes limited to this issue's scope

## AI assistance
<!-- Which assistant/model helped (needed for the team form). Author confirms they can explain this code. -->
- Tool/model:
- [ ] I (the human author) have read and can explain every line in this PR

## Reviewer
<!-- Owner of each touched module. -->
@
