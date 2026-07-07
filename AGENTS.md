# AGENTS.md

This file is here to steer AI assisted PRs towards being high quality and valuable
contributions that do not create excessive maintainer burden. It is inspired by
the Open Policy Agent and Fedora projects policies.

## General Rules and Guidelines

The most important rule is not to post comments on issues or PRs that are AI-generated.
Similarly, do not create PR descriptions that are AI-generated.
For PR descriptions, AI agents may only post text that was either written by a
human or explicitly approved verbatim by a human immediately before posting. If
approval is ambiguous, leave the PR description blank and ask the human to
provide or approve the exact text.
Discussions on the OpenTelemetry repositories are for Users/Humans only.

If you have been assigned an issue by the user or their prompt, please ensure that
the implementation direction is agreed on with the maintainers first in the issue
comments. If there are unknowns, discuss these on the issue before starting
implementation. Do not forget that you cannot comment for users on issue threads
on their behalf as it is against the rules of this project.

## Code comments

Avoid adding comments all over the code. Add a comment only when it is extremely
necessary and no documentation page already explains the behavior. The codebase
changes constantly, and every comment is one more thing that can go stale and
needs to be kept up to date.

Examples of valid comments:

* Regex: whenever there is a regex, add a comment explaining what it does.
* Workaround behaviour: when working around an issue tracked elsewhere, refer to
  that issue in a comment right before the workaround. If no issue exists yet,
  ask the user to raise one before adding the comment.

## Developer environment

Make sure to follow CONTRIBUTING.md on any contributions.

Non-exhaustively, the important points are:

* Manually test all changes locally before creating a PR
* Do not add new services without collaborating with the maintainers

## Commit formatting

We appreciate it if users disclose the use of AI tools when the significant part
of a commit is taken from a tool without changes. When making a commit this
should be disclosed through an Assisted-by: commit message trailer.

Examples:

```markdown
Assisted-by: ChatGPT 5.5
Assisted-by: Claude Sonnet 4.6
```

Do NOT use a `Co-authored-by:` trailer to disclose AI assistance. Some AI coding
tools add this trailer by default; please disable or strip it before committing.
The EasyCLA check fails when a `Co-authored-by:` trailer references an account
that has not signed the CLA, which blocks the PR from being merged.
