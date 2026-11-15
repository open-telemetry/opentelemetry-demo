# KalDB Dashboards Permissions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Demonstrate real index and field permissions enforced by KalDB's Java gateway, with denied requests proven not to reach KalDB.

**Architecture:** An isolated demo here runs OpenSearch Security, Dashboards, the patched Java gateway, and actual KalDB behind a recording upstream. Empty OpenSearch schema indexes provide native index authorization and FLS field visibility. The gateway inspects effective role definitions to reject unsupported DLS/masking policies and validates a bounded search grammar before forwarding.

**Tech Stack:** Java 21, Armeria 1.32.5, Jackson, JUnit 5, Python 3, Docker Compose, OpenSearch/Dashboards 2.11.1, Selenium.

**Spec:** `docs/superpowers/specs/2026-11-15-kaldb-dashboards-permissions-design.md`

**Execution revision:** Native 2.11.1 and latest 3.9.0 both failed the independent
multi-field exclusion probe. Use 3.9.0 for this new isolated demo and reject whole
indexes containing multi-fields or aliases before contacting KalDB. Keep a native
unsafe-schema reproduction, and qualify standalone/object/nested schemas before
Task 2. This supersedes pinned-2.11 and supported-multi-field assumptions below.
Evidence: `docs/superpowers/specs/2026-11-15-kaldb-permissions-native-feasibility.md`.

## Global Constraints

- Change the existing Java gateway in the KalDB repository; demo files belong here.
- Keep changes in isolated feature branches/worktrees; do not merge or push.
- Preserve the existing local demo. New secured mode is explicitly configured and fails closed.
- Real OpenSearch roles decide access; no hardcoded user permission map or local role-merging algorithm.
- Reject DLS/masking anywhere in every effective role, including unrelated indexes.
- Generate credentials in gitignored local files; never print plaintext credentials or put them in command-line arguments.
- Rejected requests cause zero KalDB upstream calls; all multi-search items pass before forwarding any.
- Implicit all-fields reads project visible fields; explicit forbidden-field references return 403.
- Unsupported policies/DSL fail closed. Native OpenSearch probe feasibility is a gate.
- No authorization cache. The next request reflects a completed role change.
- Use unique project/container names and ports. KalDB query and recorder control endpoints are private.

## Review Focus

1. Policy-source failure, incomplete roles, and unsupported masking/DLS must never become an allow decision (Tasks 1–2).
2. Alternate field paths, nested fields, wildcard selectors, and unfielded search must not expose or match hidden values (Task 3).
3. A denied later multi-search item must not execute an earlier allowed item (Tasks 3–4).
4. Client-supplied identity headers and direct query access must not bypass the gateway (Tasks 2, 4).
5. Role revocation, missing schema indexes, and concurrent metadata changes must fail closed without stale authorization (Tasks 1–2, 4).

## File Map

KalDB paths below are relative to its isolated worktree:

- Modify `contrib/dashboards-gateway/src/main/java/com/slack/astra/contrib/dashboardsgateway/GatewayConfig.java`: secured-mode configuration and secret-file locations.
- Modify `.../DashboardsGatewayService.java`: authenticate/authorize before data forwarding, protected header handling, metadata filtering.
- Modify `.../DashboardsGatewayRouting.java`: route real security/account requests in secured mode; do not synthesize admin there.
- Create `.../GatewayAuthorization.java`: native probes, complete role inspection, immutable per-request decisions.
- Create `.../AuthorizedSearch.java`: supported query/metadata grammar, field validation, safe projection, response filtering.
- Extend `contrib/dashboards-gateway/src/test/java/com/slack/astra/contrib/dashboardsgateway/DashboardsGatewayServiceTest.java` and routing tests: record actual requests and verify denial behavior.
- Add focused authorization/search tests in that same test package where the coverage warrants separate files.
- Modify `contrib/dashboards-gateway/pom.xml` only for directly used JSON dependencies, if needed.

OTel demo paths are relative to this repository's isolated worktree:

- Create `local/kaldb/permissions/compose.yaml`: isolated native-policy and complete demo services/networks; no fixed global container names.
- Create `local/kaldb/permissions/demo.py`: generated credentials/security files, setup, build/start/stop/status commands, fixture bootstrap.
- Create `local/kaldb/permissions/verify.py`: native feasibility, real API security matrix, UI verification, sanitized results.
- Create `local/kaldb/permissions/recorder.py`: forwarding observer and private request-count control API; no authorization logic.
- Create `local/kaldb/permissions/README.md` and requirements file if required: exact reproducible commands and supported/unsupported behavior.
- Modify `Makefile`, `.gitignore`, and `local/kaldb/README.md`: additive entrypoints and generated-file exclusions.

## Task 1: Prove Native Policy Probes on OpenSearch 2.11

**Interfaces:** `demo.py native-start|native-stop`; `verify.py native`. Generated state directory is `local/kaldb/permissions/.state/` (ignored). Default isolated project is `kaldb-permissions`; public ports are gateway 29201 and Dashboards 25601. Native test access is a private Compose harness, not a published OpenSearch admin port.

- [ ] Create isolated worktrees based on `kaldb_support` and the current KalDB gateway commit; copy the approved spec/plan into the OTel worktree and record their paths.
- [ ] Add native feasibility cases: full/restricted/no-access users, empty indexes with complete mappings, mixed effective roles, parent/nested/multifield FLS, index denial, missing indexes, and field-capability output.
- [ ] Bootstrap real Security configuration with generated passwords, a private CA/TLS, role mappings, and a policy-reader account restricted to role GET operations. Test forbidden role writes and unrelated admin APIs.
- [ ] Run `python local/kaldb/permissions/demo.py native-start` followed by `python local/kaldb/permissions/verify.py native`. Assert zero documents in the OpenSearch schema indexes and that the restricted user's hidden fields are absent from native field capabilities.
- [ ] If an oracle assumption fails, stop and revise the design; do not replace it with a local permission map. Otherwise record sanitized evidence and commit the native harness.

## Task 2: Authenticate and Authorize Indexes in the Java Gateway

**Interfaces:** Extend `GatewayConfig` with optional secured-mode configuration. `GatewayAuthorization.authorize(AggregatedHttpRequest request, String path)` returns `CompletableFuture<Decision>`. `Decision` records authenticated principal, concrete datasets and visible fields per dataset; denied/error decisions include their HTTP status and a sanitized message. No user-supplied identity is accepted as authoritative.

- [ ] Extend the existing gateway harness to count all KalDB requests and configure independent fake OpenSearch responses. Write failures for no credentials (401), bad credentials (401), unauthorized index (403), policy outage (503), missing/incomplete roles (503), and DLS/masking (403); all assert zero KalDB calls.
- [ ] Run `mvn -f contrib/dashboards-gateway/pom.xml test` and confirm the new behavior fails against the old forwarding implementation.
- [ ] Implement native user authentication, read-only role inspection, empty-index search probes, and field-capability probes. Require all probe responses to be complete, successful, and tied to the same authenticated principal.
- [ ] Handle real account/security passthrough in secured mode. Strip spoofable identity and internal security headers; user credentials are sent only to the native authorizer, not to KalDB. Never log credentials or secret values.
- [ ] Add cases for revoked roles on the next request, no matching schema index, malformed probe responses, partial field capabilities, and forged user/role headers. Preserve the existing unsecured local-mode tests.
- [ ] Run the complete gateway module suite, verify allowed requests reach the recording upstream, and commit.

## Task 3: Enforce Field Visibility and Atomic Multi-search Authorization

**Interfaces:** `AuthorizedSearch.prepare(AggregatedHttpRequest request, Decision decision)` returns a validated/re-written request or a structured denial. `AuthorizedSearch.filterResponse(AggregatedHttpResponse response, Decision decision)` returns a filtered response or fails closed. Keep supported constructs explicit; do not parse arbitrary Lucene syntax with a permissive regex.

- [ ] Add failing tests for forbidden fields in queries, filters, sort, aggregations, source/fields/docvalue selections, nested paths and wildcard selections. Test bare text matching only a private sentinel, and hidden names in mappings/field capabilities.
- [ ] Add a mixed `_msearch` with an allowed first item and denied later item, asserting a whole-request 403 and zero KalDB calls. Test an index in body metadata differing from the URL, absent index metadata, oversized/malformed NDJSON, encoded resource names, and unauthorized response indexes.
- [ ] Implement the bounded grammar: match-all; simple fielded queries; term/terms, range, exists and bool; visible-field sorting/projection; count/date histogram needed by Discover. Reject scripts, templates, runtime fields, SQL/PPL, scroll/PIT and unsupported clauses before forwarding.
- [ ] Rewrite unfielded/all-fields queries to the native visible-field set, validate every explicit reference, and filter metadata/documents defensively. Unknown fields default to denied; schema changes become readable only after the native schema index is updated.
- [ ] Exercise the prepared requests against actual KalDB in Task 4 so response filtering and source projection are not verified only by mocks.
- [ ] Run the entire gateway module suite and commit.

## Task 4: Add Actual KalDB, Recording Evidence, and Real Security Verification

**Interfaces:** `demo.py start|stop|status`; `verify.py api`; recorder private `GET /__test__/calls` returns counts and sanitized request IDs, with forwarding available only on the backend network. Add Make targets `start-kaldb-permissions`, `verify-kaldb-permissions`, `stop-kaldb-permissions`.

- [ ] Extend Compose with the built gateway and actual KalDB plus required Kafka/ZooKeeper/S3 dependencies. Prefer a single local multi-role KalDB process where supported to reduce memory. Build from the chosen KalDB worktree, not the earlier temporary OTLP image; this demo uses bulk-ingested fixtures and does not require PR 55.
- [ ] Isolate internal policy-reader credentials, admin setup and recorder control access. Publish only the secured gateway and Dashboards on loopback; demonstrate that a user-facing container cannot reach the private KalDB query/recorder-control services.
- [ ] Create two synthetic KalDB datasets and identically named empty OpenSearch schema indexes. Bootstrap full reader, FLS reader and no-access reader with appropriate Dashboards tenant rights. Ingest recognizable public/private/nested fixture values into KalDB only.
- [ ] Run real allowed/denied API cases from the spec. For each denied request, capture recorder count before/after and assert delta zero. Positive controls must return the actual KalDB sentinel and increase the count. Verify matching behavior for unfielded hidden-value searches and metadata responses.
- [ ] Change a role through OpenSearch Security, repeat the previously allowed request, assert denial, then restore the demo-owned role. Test authorizer outage and unsupported policy changes with a reliable cleanup path.
- [ ] Add commands and generated-state ignores; run Compose validation, existing KalDB startup regression, Java module tests and `verify.py api`. Commit only after inspecting the results.

## Task 5: Verify the Dashboards User Experience and Document the Demo

**Interfaces:** `verify.py ui|all` uses the generated credential file without printing it. Reports contain test names, statuses, sentinel visibility and recorder deltas; failure screenshots contain only synthetic data. `make verify-kaldb-permissions` invokes `all`.

- [ ] Add real login/Discover verification for full and restricted readers: authorized dataset visible, denied dataset undiscoverable, private fields absent, actual public fixture visible. Use the pinned Dashboards version's actual request shapes to check the supported grammar.
- [ ] Verify an explicit forbidden-field request through Dashboards Dev Tools/API returns 403 and leaves the recorder unchanged. Verify a full reader sees the private sentinel so an empty/misconfigured dataset cannot make the test pass.
- [ ] Run `python local/kaldb/permissions/verify.py all`; inspect screenshots/results. If legitimate Discover requests fall outside the grammar, implement them safely with regression coverage or document a design revision rather than bypassing enforcement.
- [ ] Document startup, login credential-file location, role scenarios, exact commands, field behavior, supported scope, private-network boundary, expected evidence and resource requirements. Explain that this is a bounded demo, not all OpenSearch security features.
- [ ] Run final module tests/configuration checks/security matrix once, self-review against both repositories' AGENTS.md rules, and obtain a whole-change review. Fix findings and rerun only affected checks plus any required final gate.
- [ ] Leave branches unmerged/unpushed and report exact worktree/branch paths, changes, evidence, and any unresolved failures.

## Self-review

The tasks cover the spec's native-probe feasibility gate, real authentication,
index and FLS decisions, unsupported-policy rejection, no-cache revocation,
multi-search atomicity, response/metadata filtering, private query boundary,
recording proof, browser workflow and separate repository deliverables. All five
review-focus risks have explicit owning tests. Branch names, helper split and
exact fixture values remain builder choices as the spec permits.
