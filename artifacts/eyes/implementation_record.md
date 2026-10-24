# F01 / F03 / Eyes implementation record

Implemented externally under incident_tools/eyes. This record describes offline verification, not completed live Checkpoint 1 acceptance.

Delivered: durable symptom-based alert intake, true source timestamp checks in addition to F02 evaluation times, bounded consecutive-breach rules, coverage/warmup checks, deduplication, joined service symptoms, cooldown, durable sequential investigation queue, one adaptive model/tool loop, local/cloud provider selection and fallback, selected provider/model audit, evidence-linked symptom report, safe model configuration report, execution JSON/Markdown and one-page SVG export. Existing source and configuration files were not changed. Runtime dependencies are the existing F02 package, Python 3.11+ standard library, existing telemetry backends and an operator-configured existing compatible inference runtime.

Static/offline validation command, executed once:

~~~text
python -B -m incident_tools.eyes.static_check --output-dir artifacts/eyes/check-01
~~~

Result: 59 tests (45 existing F02 and 14 new Eyes), zero failures/errors. Python AST and SVG XML checks passed. All 692 pre-existing tracked files matched the pre-implementation SHA-256 baseline. The synthetic pipeline generated a durable incident and selected search_traces followed by search_logs based on preceding timeout evidence; its stop reason was model_finished. The complete fixture outputs are explicitly labelled SYNTHETIC-fixture-report and origin=fixture. No real incident, Docker change, faultctl call, cloud/local inference request or completed live demonstration is claimed.

Artifacts:

- baseline.json: pre-existing file preservation hashes.
- check-01/verification.json: machine-readable verification and limitations.
- check-01/test_results.txt: complete offline test output.
- check-01/SYNTHETIC-fixture-report/: reviewable synthetic report, execution log, model configuration audit and SVG.
- check-01/synthetic-state/: temporary-test-derived durable state/evidence retained as synthetic examples.

Pending live acceptance: configure the existing F02 endpoints and model provider, calibrate freshness/threshold/coverage settings against actual publication, select a compliant known-reset practice incident, demonstrate one sustained breach causing one automatically investigated incident, inspect at least two evidence-dependent tool choices, review cited facts/interpretations, and retain actual report/architecture artifacts. The earlier faultctl safety/reset findings remain relevant when selecting a practice incident. No organiser report schema is claimed. Citation existence is validated; semantic correctness still requires evidence review. No remediation, approval or recovery execution is implemented here.

See incident_tools/eyes/README.md for the operator configuration, commands, explicit freshness/resource/model limitations, interrupted-job handling and acceptance procedure. These changes are not committed or pushed as part of this task.
