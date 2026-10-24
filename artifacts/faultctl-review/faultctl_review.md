# faultctl verification review

**Date:** 23 October 2026. **Scope:** Current repository implementation, isolated file fixtures, and a disposable HTTP API stub.  
**Verdict:** Basic flag switching and the preset catalog work, but the tool is not yet reliable for unattended timed drills or concurrent operators. Several hardening contracts fail. This is a review, not a source-code fix or a successful live practice run.

## Verification results

- **24 contract tests: 16 passed, 8 failed, 0 errors.** The failures represent six themes below; negative duration is tested through three command paths.
- All **20 current flags / 59 flag-and-variant combinations** passed in-memory set/clear checks.
- All **18 current scenarios** applied their declared values through the actual CLI against temporary configuration files.
- Targeted `productCatalogFailure` handling preserved its predicate, default variant, and nonmatching fallback.
- Ordinary set/clear/reset, default variant selection, filtered JSON listing, invalid names/variants, dry-run, and successful one-second timed operations passed.
- HTTP routes and `{"data": ...}` payload matched the inspected UI API contract under a local disposable server.
- **705 pre-existing files were hashed and compared; none changed or disappeared.** No live demo configuration was written. All test mutations were confined to disposable fixtures or an in-memory HTTP stub.

Evidence: [results.json](./results.json), [test_output.txt](./test_output.txt), [commands.json](./commands.json), and [baseline.json](./baseline.json). The external harness is [verify_faultctl.py](./verify_faultctl.py).

## Findings, ordered by operational impact

### 1. High: failed timed reset still returns a successful exit code

**Source:** `src/faultctl/cli.py:198–212`, especially the reset worker at lines 200–207 and thread join at 210–212.

`set --duration` performs the initial write, then runs the eventual reset in a thread. An exception in that worker does not propagate to the main CLI process. The caller can therefore receive exit code zero even when the fault remains active.

**Reproduction:** A disposable API accepted `paymentFailure=100%`, then returned HTTP 500 on the scheduled reset write. The CLI emitted the worker traceback, exited **0**, and the test API still held **100%**.

**Impact:** A test harness or operator checking the command's exit code can incorrectly conclude a timed drill finished successfully. Recovery/reset has not occurred.

**Recommended change, not applied:** Propagate reset failures to the command result; exit nonzero when reset cannot be confirmed; retain an explicit unresolved/reset-needed record. For interrupted processes, a durable reset mechanism or backend-supported expiry would be needed rather than relying only on a client thread.

### 2. Medium: negative durations mutate flags before failing

**Source:** `src/faultctl/cli.py:188–210`, `246–261`, `302–318`, and integer-only argument declarations at `375`, `388`, `407`.

Duration accepts any integer. Mutation happens before `time.sleep(duration)` validates that the interval is nonnegative.

**Observed on temporary files:**

| Command path with duration -1 | Exit code | Result left behind |
| --- | --- | --- |
| `set paymentFailure 100%` | 0 | Payment fault remains 100%; reset thread raises `ValueError`. |
| `scenario apply payment-fail` | 1 | Payment fault remains 100%; command fails after applying it. |
| `trigger-all` | 1 | All 20 flags remain active; command fails after bulk mutation. |

These descriptions omit transport arguments for readability. They were executed only with `--local --file <temporary fixture>`; do not reproduce them against the default live file.

**Recommended change, not applied:** Validate a positive duration before any write. Define zero-duration semantics explicitly rather than silently treating zero as no expiry.

### 3. Medium: bulk incident injection also enables an explicit non-failure PII flag

**Source:** `src/faultctl/flags.py:137–144`; flag definition `src/flagd/demo.flagd.json:86–96`.

`trigger_all` activates every flag with a non-off variant. That includes `emitRawPii`, whose definition explicitly says **“Not a failure scenario”** and marks `metadata.schedulable=false`.

**Reproduction:** Running `trigger_all` on an isolated copy changed `emitRawPii` from `off` to `on`.

**Impact:** Requesting all incident faults also changes a separate data-emission behaviour. The existing Collector's redaction remains separate; this test does **not** establish that sensitive data escaped redaction.

**Recommended change, not applied:** Define an explicit bulk-injection eligibility policy. Exclude the known non-failure PII flag by default and require an explicit opt-in for that demonstration. If scheduler metadata is reused for this purpose, document that policy rather than assuming every future `schedulable=false` flag has identical semantics.

### 4. Medium: whole-configuration writes lose concurrent updates

**Source:** read/modify/write in `src/faultctl/cli.py:165–188`; transports in `src/faultctl/client.py:23–38,57–61`; file replacement in `src/faultctl/flags.py:43–48`.

The atomic rename protects a single write from producing a partly written JSON file. It does not make a read/modify/write transaction atomic across clients.

**Reproduction:** Two local clients read the same off-state fixture. Client A enabled payment failure and saved. Client B enabled ad CPU using its earlier snapshot and saved. The resulting file had ad CPU **on**, but payment failure was silently back **off**.

**Impact:** Overlapping operators, timers, or schedulers can remove one another's changes. API mode uses full replacement too; the shared design has the same stale-snapshot risk, although the concurrency reproduction here used local clients, not a live Elixir server.

**Recommended change, not applied:** Use a single authoritative mutation interface with per-flag operations or version-checked updates. Local mode needs locking around the entire transaction, not just atomic file replacement. Until then, use one writer and avoid concurrent scheduling.

### 5. Medium: HTTP success is treated as confirmation that the flag changed

**Source:** `src/faultctl/client.py:30–38`; `src/faultctl/cli.py:188–190`; asynchronous server handler `src/flagd-ui/lib/flagd_ui_web/controllers/feature_controller.ex:13–17`.

The HTTP transport consumes the response but does not read back or otherwise confirm the requested variant. The inspected server sends a `GenServer.cast` and returns HTTP 200 rather than synchronously returning the storage write result.

**Controlled fault-injection test:** A stub returned HTTP 200 without applying the requested replacement. The CLI printed `paymentFailure -> 100%` and exited **0**, while the API state remained **off**.

**Scope:** This proves the client's missing completion check, not that the actual UI always fails to save. No live backend failure was observed in this review. Successful flag readback also would not prove that every application has consumed the new flag or that the expected incident symptoms appeared.

**Recommended change, not applied:** Distinguish request acceptance, persisted flag state, and observed application effect. Use bounded readback or a backend completion result; report timeout/unconfirmed state instead of unconditional success. Confirm incident telemetry independently.

### 6. Low: API read/replace roundtrip discards top-level configuration metadata

**Source:** `src/faultctl/client.py:23–28`; `src/flagd-ui/lib/flagd_ui_web/controllers/feature_controller.ex:7–17`; replacement storage in `src/flagd-ui/lib/flagd_ui/storage.ex:49–54`.

The actual file contains `$schema` and `flags`. The API exposes only `flags`; the client constructs a flags-only document, then submits that document for complete replacement.

**Reproduction:** A stub matching the inspected read/write API started with both top-level keys. After one CLI API write, only `flags` remained. Local mode preserved `$schema`.

**Impact:** Existing root metadata is lost. `$schema` is a schema-reference field, and this review does not claim losing it alone stops flagd; nevertheless the API operation does not preserve the original document.

**Recommended change, not applied:** Preserve the complete document or use a flag-scoped mutation API. The present read endpoint cannot supply root metadata it deliberately omits, so this is a shared API-contract issue rather than solely a CLI problem.

## Additional source-review observations

- `traffic-flood` describes **100 concurrent users** (`src/faultctl/scenarios.py:59–61`), but its flag drives a loop of **100 sequential homepage requests per executing Locust user** (`src/load-generator/locustfile.py:230–236`). Existing Locust users can overlap, but the scenario does not create 100 additional concurrent users. The description should match that behaviour.
- The existing `paymentFailure` variant named `90%` maps to **0.95** in `src/flagd/demo.flagd.json:166`. The payment implementation compares a random sample directly with that value. This is an existing configuration-label inconsistency, not a faultctl mutation bug.
- All current flags have an `off` variant, so the constant resting-state assumption matches this checkout. It is not a general-purpose implementation for arbitrary flagd registries with other resting values.
- Timed reversion intentionally sets affected flags to `off`; it does not restore an arbitrary previous snapshot. A global reset intentionally turns all flags off. Do not treat either operation as byte-for-byte or previous-state restoration.
- Automatic transport selection falls back to local file writes when its API availability check fails. That matches the implemented auto-detection design, but it is unsuitable when the operator intends API-only behaviour. Use explicit transport selection; specifying a custom API URL alone does not force API mode.
- `--duration` needs the CLI to remain alive. Process termination or interruption can leave faults active. No durable expiry/recovery mechanism was found.
- The utility implements flag-based faults. It does not implement infrastructure drills such as stopped containers, packet loss, or CPU/memory resource limits, and it does not verify that the associated services are deployed or that symptoms appeared.
- No existing faultctl tests or CI wiring were found in the inspected `test/`, workflows, or Makefile. This review's harness is external and does not alter those files.

## File-preservation boundary

Writing flag configuration is expected functionality for this injector. That behaviour is separate from the defects above.

However, both existing transports ultimately change `src/flagd/demo.flagd.json` in the current deployment: local mode writes it directly; API mode writes `/app/data/demo.flagd.json`, which Compose bind-mounts from `src/flagd`. API mode is therefore not a workaround for the project's current requirement to preserve existing configuration files.

During this review, the flag schema was read solely to verify the injector implementation. No configuration state or scenario answers were supplied to the incident-analysis model, and no diagnostic incident was run.

## Reproduce the isolated verification

From Windows PowerShell in the repository root:

```powershell
python -B artifacts/faultctl-review/verify_faultctl.py
```

The harness imports the existing tool unchanged, uses temporary copies of its current flag schema, and starts a loopback-only disposable HTTP server for contract/error-path tests. Each temporary directory is verified to lie under this review directory before automatic cleanup. Python bytecode writes are disabled.

**Exit code 1 is currently expected:** the harness asserts the safer contracts and reports the real failures. It is not a claim that every tested function is broken. Results are overwritten only inside this new review directory; the initial preservation baseline is not overwritten.

## What remains unverified

No live flagd/UI container, SDK flag propagation, real service failure, actual telemetry change, infrastructure drill, or recovery was exercised. The HTTP stub verifies the inspected payload contract and reproducible failure handling; it does not replace an integration test against the actual backend.

After the defects and configuration-preservation boundary are resolved, the remaining acceptance test is a real inject → observe symptoms → reset → observe recovery run against the authorised environment. No source files were edited to perform this review.
