---
name: incident-report
description: Produce an Incident Zero incident report that matches the organisers' JSON schema exactly, with a readable markdown form, where every evidence item traces to a real tool output. Use when the user asks for an incident report, a run summary, or to check a report against the schema.
---

# Incident report

The report is scored. It must match the organisers' JSON schema every time, and every piece of evidence must be real.

## 1. Find the schema
- The schema comes from the organisers' template. Its path is still TBD in `docs/hackathon/interfaces.md`.
- Ask the user for the path if you cannot find it. Do not write a schema from memory.
- Never edit the schema.

## 2. Gather inputs
- The run log: every tool call, its arguments, and its raw result.
- The diagnosis: component, cause, confidence, and evidence references.
- The action log: proposals, approvals, executions, and verification results. If nothing was executed, say so.

## 3. Build the JSON
- Fill every required field. Use `null` only where the schema allows it.
- Every evidence item must match an entry in the run log: same trace ID, same log line and timestamp, same metric query and value. Check this in code before writing the file.
- Confidence is a number the schema accepts. Do not round it up to look better.

## 4. Validate
```bash
python -m jsonschema -i <report.json> <schema.json>
```
- Check that the validator is installed first. If not, ask before installing a package, and pin its version.
- A failing report is not written as a valid report. Fix it or report the errors.

## 5. Write the readable form
Markdown with: timeline, root cause, evidence (each item with its source reference), action taken, verification result, and what would prevent a repeat. State the limitations and what was not verified.

## Never
- Invent evidence, timestamps, metric values, or trace IDs.
- Report recovery that the verification step did not confirm.
- Hide a failed or escalated run. Escalations are valid outcomes.
