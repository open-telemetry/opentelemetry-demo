# AGENTS.md

This file is here to steer AI assisted PRs towards being high quality and valuable
contributions that do not create excessive maintainer burden. It is inspired by
the Open Policy Agent and Fedora projects policies.

## General Rules and Guidelines

The most important rule is never to post AI-generated content on issues or PRs.
AI agents may only post text (PR descriptions, and comments or replies on issues
and PRs) that was written by a human or explicitly approved verbatim by a human
immediately before posting. If approval is ambiguous, leave it blank and ask the
human to provide or approve the exact text. Discussions on the OpenTelemetry
repositories are for Users/Humans only: an agent may act as a conduit for a
human's own words, but must never author its own.

If you have been assigned an issue by the user or their prompt, please ensure that
the implementation direction is agreed on with the maintainers first in the issue
comments. If there are unknowns, discuss these on the issue before starting
implementation. Do not forget that any comment you post must carry the human's
own verbatim words, never text you generated yourself.

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

## Telemetry conventions

The demo's custom attributes and metrics are defined in `telemetry-schema/`,
which is an OpenTelemetry Weaver registry. Attributes are grouped by business
domain under `attributes/`, metrics by service under `metrics/`, and each
service declares the telemetry it emits under `services/`.

When adding or changing instrumentation:

* Reuse an existing attribute from `telemetry-schema/attributes/` whenever one
  already describes what you are recording.
* Prefer an upstream semantic convention attribute over a demo specific one
  when semconv already defines it. For example, use `user.id` rather than
  defining a demo attribute for the same value.
* Define any genuinely new attribute or metric in the registry before using it
  in code, so that the schema stays the single source of truth.
* Use the `demo.` prefix for demo specific attributes. Do not use `app.`, it is
  reserved for client side instrumentations.

The `Weaver check` CI job runs `weaver registry check` against the registry, so
a definition that is invalid or missing from the schema fails the build. The
generated documentation is served by the `telemetry-docs` service, see
`src/telemetry-docs/README.md`.

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
