# F02 implementation record

Implementation date: 2026-10-23. Baseline commit: e8980674dabe885820273b5deebfdecc92133a52.

**Implemented and fixture-tested; live acceptance pending.** All outputs in verification-01 and verification-02 are test and preservation results, not real incident telemetry. No Live Demo or practice incident was executed in this task.

## Completed

- Added an independent standard-library Python 3.11+ package under incident_tools/f02. Existing source, configuration, scripts, build files and dependency files are unchanged.
- Six read-only tool entry points: allowlisted Prometheus metrics, scoped OpenSearch logs, bounded Jaeger traces, current Docker health, bounded Docker lifecycle history and optional deployment audit history.
- Deterministic service/time validation, request/output limits, selected fields, exact numeric source values, source identifiers, UTC timestamps, evidence IDs and query provenance.
- Explicit ok/partial/no_data/unavailable/invalid_request/error results. Missing data is never replaced with healthy or zero values.
- Generated function schemas, Python API, single-call CLI and JSON stdin/stdout dispatcher. Future investigator integration is documented; the existing shopping assistant is unchanged.
- Operator-owned TOML template with endpoints, authentication through environment variables, service allowlist, Docker native/WSL selection and resource limits. No credentials are installed or included in generated artifacts.
- Common credential/PII redaction, omission of flag-resolution records and non-allowlisted span attributes, and explicit truncation metadata for long log excerpts.
- No shell execution, mutable application endpoints, Docker exec/restart/stop commands, feature-flag file reads, or faultctl calls through the tool dispatcher.
- Reproducible offline verification and an Ubuntu WSL live handoff in [the package documentation](../../incident_tools/f02/README.md).

## Verification actually executed

Commands ran from the repository root using Windows Python 3.11:

~~~text
python -B -m incident_tools.f02 --config incident_tools/f02/operator.example.toml schemas
python -B -m unittest discover -s incident_tools/f02/tests -v
python -B -m incident_tools.f02.verify --output-dir artifacts/f02/verification-01
python -B -m incident_tools.f02.verify --output-dir artifacts/f02/verification-02
git status --short
git diff --check
~~~

The initial test suite exposed structured log credential redaction that needed correction. Regression coverage was retained. Additional tests cover OpenSearch keyword query fields, omitted empty protobuf fields, valid agent-style dispatch, Jaeger streamed responses and late errors, and exclusive trace end times.

Final verification: **45 tests run, 0 failures, 0 errors, 0 skipped**. HTTP tests issue actual requests to an ephemeral loopback fixture server. Docker operations are mocked; deployment records are synthetic temporary files. Tests include parsers, request scope, attempted injection, malformed data, no-data behavior, non-finite values, source IDs, redaction, response limits, retry bounds, Docker timeout/failure handling, and exclusive evidence file creation.

Evidence:

- [Pre-implementation SHA-256 baseline](baseline.json): 677 existing tracked/nonignored files.
- [Final machine-readable verification](verification-02/verification.json).
- [Final full test output](verification-02/test_results.txt).
- verification-01 records the earlier passing 42-test suite, before stream coverage was added.

All **677** baseline files matched their hashes; no existing file was missing. git diff against HEAD was empty. The new work resides only under incident_tools/ and artifacts/f02/. The baseline covers existing tracked/nonignored files, not a forensic snapshot of all ignored build/cache files.

## Pending acceptance and limitations

- Real Prometheus, Jaeger and OpenSearch responses, emitted service names, source fields/labels, metric units and query results still need verification in the unchanged live demo.
- Actual native Docker/WSL execution and selected inspect template quoting require a live run; fixtures verify constructed argument arrays and result handling only.
- No deployment audit source was identified. deployment_history intentionally returns unavailable until an operator configures a genuine existing feed. Docker lifecycle events and Git history are not substituted as deployments.
- F03 integration with an actual diagnostic agent is pending. These are callable tools, not an implemented adaptive investigation agent. No LLM or model routing was tested or changed for this task.
- F01 alert detection/intake is outside this implementation. No threshold breach or incident success is claimed.
- No real log/trace correlation or practice incident report can be certified from synthetic fixtures. Checkpoint 1 and full F02 live acceptance remain incomplete.

No offline requirements failed in the final verification. The live requirements above are **not run**, rather than reported as passing or as backend failures.
