# KalDB Dashboards permissions demo

## Intent and selected approach

Implementation revision after native feasibility testing: the isolated demo now
targets OpenSearch/Dashboards 3.9.0. Secured mode rejects entire indexes containing
multi-field mappings or field aliases. Supported demo schemas use standalone
fields and object/nested leaves. See the
[native evidence and bounded revision](2026-11-15-kaldb-permissions-native-feasibility.md).
This revision supersedes the original 2.11 and multi-field assumptions below;
the original text remains as the record of the approved approach and its gate.

Add a repeatable demo in this repository that uses real OpenSearch Dashboards
users and OpenSearch Security roles. Enforce index access and field restrictions
in KalDB's existing Java Dashboards gateway, before forwarding requests to KalDB.
The user selected this approach over a separate demo-only authorization proxy.

The demo must prove both successful reads and that rejected requests cause zero
requests to the KalDB upstream. Hiding UI controls is not sufficient.

## Current state

- OTel demo changes live on `kaldb_support` in this repository.
- The KalDB checkout is `/Users/suman/code/kaldb-kaldb`; gateway code is under
  `contrib/dashboards-gateway` on `opendashboards_otel_demo`.
- Current Compose disables OpenSearch Security and Dashboards security. The
  gateway fabricates an admin account response and otherwise routes requests.
- Existing tests check routing and dataset isolation, not per-user authorization.
- Previous full-stack runs had intermittent request timeouts. The permissions
  demo should use its own Compose project, ports, fixtures, and verification
  commands rather than relying on the health of that existing stack.

## Approaches

1. **Selected: extend the existing Java gateway, demo here.** One authorization
   implementation is exercised by gateway tests and the browser/API demo.
2. **Not selected: demo-only authorization proxy.** Faster to prototype, but
   would leave the production gateway without the behavior being demonstrated.

For the policy integration, the proposed implementation uses native OpenSearch
search authorization and field capabilities over empty schema indexes. It does
not implement OpenSearch's role-merging and field-inclusion rules itself.
An OpenSearch plugin exposing native authorization decisions remains a fallback
if these APIs cannot supply the required guarantees; adopting that fallback
requires revisiting this design, rather than silently substituting a new policy
engine.

## Policy integration

Create empty OpenSearch indexes with exactly the names and schemas of the demo
KalDB datasets. They contain no telemetry documents. OpenSearch remains the
identity/role authority and stores Dashboards saved objects.

For each request, in the user's authenticated context:

1. Authenticate through OpenSearch Security; forward actual account/security
   requests instead of synthesizing the admin response.
2. Resolve concrete, registered dataset names. Authorize search using a native
   search on the corresponding empty index, with `match_none` and size zero.
   This executes no KalDB query and reads no telemetry from OpenSearch.
3. Obtain the user's visible field names using native `_field_caps`. OpenSearch
   2.11's Security tests explicitly cover FLS filtering of field capabilities.
4. Validate the complete incoming search against those fields and operations.
   Apply a concrete allowed-field projection before forwarding; filter returned
   metadata and documents as an additional check.

The current documentation's `perform_permission_check` option is not assumed to
exist in pinned OpenSearch 2.11. Its SecurityFilter source does not contain that
mechanism. A standalone allow/deny response would not establish field visibility
in any case.

Native field capabilities do not express document-level security or field
masking. A dedicated internal policy reader must inspect every effective role
and conservatively reject requests if DLS or masking appears anywhere in those
roles, including on unrelated indexes. This intentional over-denial avoids
reimplementing OpenSearch's role applicability rules. Missing role definitions
or incomplete policy responses are also failures. Give the policy reader only
the required Security REST read access; never use its identity for user
authorization probes or data requests. Test that it cannot write roles or access
unrelated administrative APIs. Do not infer permission from an index merely
appearing in a saved data view.

No authorization cache in the first demo. Authenticate and evaluate policy on
every request. Role changes must affect the next request after they are applied.
Missing schema indexes, unavailable policy services, malformed policy responses,
or unsupported policies must fail closed before contacting KalDB.

## Deliberately bounded behavior

This is an index-access and FLS demo, not support for every OpenSearch security
feature or every query API. DLS, masking, scripts, runtime fields, SQL/PPL, scroll,
PIT, search templates, and unimplemented DSL constructs are rejected in secured
mode. The implementation must enumerate supported constructs and reject unknown
ones; a regex scan of arbitrary query strings is not sufficient.

Initial supported operations are those needed by Discover and the explicit demo:
index discovery, mappings, field capabilities, `_search`, and `_msearch` with
concrete dataset names. The search subset includes match-all, simple fielded
queries, term/terms, exists, range, boolean combinations, sorting, field/source
selection, and Discover's count/date-histogram requests. The builder may narrow
this list if a version-specific safety issue is found, but must document the
limitation and keep a usable Discover workflow. Unsupported behavior must never
fall through to KalDB.

Every `_msearch` item must pass before any item is forwarded. A denied index or
an explicitly forbidden field produces a whole-request `403`, including mixed
allowed/denied multi-searches. Queries, filters, sorts, aggregations, highlighting,
and returned field selectors are all authorization surfaces.

Proposed FLS behavior: an implicit all-fields read returns only visible fields;
an explicit reference to a forbidden field returns `403`. Restrict unfielded
searches to visible fields so hidden values cannot affect hits or counts. Denied
fields and indexes must also disappear from discovery/mapping/field-capability
responses. Include nested fields and wildcard source selections in tests.

## Demo structure and trust boundary

- Add a separate `local/kaldb/permissions` demo profile and start/verify/stop
  targets. Preserve the existing local demo; secured mode must be explicit in
  gateway configuration and fail closed when enabled. This opt-in behavior is
  a proposed compatibility choice requiring design approval.
- Use an isolated Compose project, distinct ports and container names, and a
  network-private KalDB query service. Do not expose a user-accessible direct
  query port that bypasses the gateway.
- Use generated credentials in a gitignored local file. No secrets in committed
  code, example URLs, command output, or test reports. Authenticate actual users;
  do not trust client-supplied user/role headers.
- Create two synthetic datasets and matching empty OpenSearch schema indexes.
  Provide a full reader, an FLS reader, and a user with no dataset access; each
  has the Dashboards tenant/UI rights needed to log in.
- Fixture documents contain public values and recognizable synthetic private
  values, including a nested field. FLS readers see only public fields.
- Add a recorder between the Java gateway and the actual KalDB query service.
  Its test-control interface is private to the verification harness. Count real
  forwarded requests and attach correlation IDs. A positive control must return
  an actual KalDB fixture and increase the count; each denied request must leave
  the count unchanged.
- The recorder is an observer, not an authorization implementation. Java gateway
  unit tests additionally use recording upstreams for fast negative coverage.

The demo owns its fixtures and policy configuration. Metadata/schema changes
must update the empty OpenSearch schema indexes before becoming readable through
the gateway. Broader automatic schema synchronization is outside this change.

## Test matrix and completion evidence

| Case | Expected result | KalDB forwarded requests |
|---|---|---|
| Full reader reads fixture | Actual fixture, including private sentinel | Positive |
| Restricted reader reads public fields | Actual fixture with private values absent | Positive |
| No credentials / invalid credentials | 401 | Zero |
| User lacks dataset access | 403 | Zero |
| Explicit forbidden field in query/filter/sort/aggregation/source | 403 | Zero |
| Mixed allowed/denied `_msearch` | 403, no partial execution | Zero |
| Broad metadata discovery | Only authorized indexes and fields | As required after authorization |
| Private value used in an unfielded search | Cannot match solely through hidden field | Authorized request only |
| Unsupported DSL, DLS, masking, malformed policy, or unavailable authorizer | Fail closed | Zero |
| Role revoked after a successful read | Next request denied | Zero for denied request |
| Direct KalDB access from user-facing network | No route | Zero |

Verify with real OpenSearch Security enabled, API requests for all users, and a
headless Dashboards login/Discover check for full and restricted readers. Record
sanitized statuses, sentinel visibility, and recorder deltas. First establish a
failing test against today's gateway, then test the implementation. Run the
gateway module's complete test suite, Compose/configuration checks, and the demo
verification command. Do not describe the demo as passing if browser checks or
security cases fail.

Before committing to the probe implementation, a feasibility test on pinned
OpenSearch 2.11 must verify FLS on empty schema indexes, multiple effective roles,
nested/parent/multifield names, and incomplete/error responses. This is a gate:
the native FLS integration test is evidence for trying the approach, not proof
that every gateway projection is correct. If it fails, revise the design.

## Design review

A fresh security-focused builder review found no remaining important planning
questions after clarifying conservative DLS/masking rejection and negative
capability tests for the policy reader. These choices and the feasibility gate
are part of the proposed demo scope, not claims about an implemented system.

## References

- [OpenSearch 2.11 FLS and field-capabilities tests](https://github.com/opensearch-project/security/blob/2.11.1.0/src/integrationTest/java/org/opensearch/security/FlsAndFieldMaskingTests.java)
- [OpenSearch 2.11 SecurityFilter](https://github.com/opensearch-project/security/blob/2.11.1.0/src/main/java/org/opensearch/security/filter/SecurityFilter.java)

## Repository and delivery boundaries

Gateway implementation and tests belong in an isolated KalDB feature branch.
Demo orchestration, fixtures, verification, and this design belong here, on an
isolated branch based on `kaldb_support`. Changes to the two repositories should
remain separately reviewable. Do not merge or publish either branch without a
separate instruction. The exact branch names, helper-file split, and test-runner
implementation are left to the builder.

## Decisions requiring approval

Approve the selected gateway implementation, the native empty-index policy
probes plus policy-reader safety check, the bounded read/query scope, the FLS
filter-versus-explicit-denial behavior, and opt-in secured mode. If native
OpenSearch probes cannot establish these guarantees in the pinned version,
report that result and revise the design before implementing a substitute.
