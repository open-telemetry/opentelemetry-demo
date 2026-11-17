# OpenSearch 2.11 security demo — verification

The two-user demo passed with actual KalDB data and native OpenSearch/Dashboards
2.11.1 Security plugins. Both repositories use `codex/security-demo-2.11-review`.
Nothing was merged; 3.9 remains parked.

- Gateway source: [KalDB review branch](https://github.com/kaldb/kaldb/tree/codex/security-demo-2.11-review), tested gateway commit `b23b4b8f`.
- Demo and [walkthrough](../../../local/kaldb/permissions/README.md): [OTel review branch](https://github.com/kaldb/opentelemetry-demo/tree/codex/security-demo-2.11-review).
- Java gateway: `mvn -q -f contrib/dashboards-gateway/pom.xml package` passed **34/34** tests.
- `verify.py all` passed the qualified native gate, **50/50 API cases**, and real Chrome checks for both dashboard users and an admin.
- Both users rendered only their own dashboard and actual fixture rows. Cross-index and hidden-field data requests returned HTTP403 with **zero KalDB calls**. Tenant forgery could not retrieve the other dashboard.
- Admin edited native permissions through Dashboards; the next user data request was denied before KalDB. Policy restoration passed.
- Permission presets `both`, `none`, and restoration were also exercised against actual services.
- Clean startup, Compose validation, Python/shell syntax, existing KalDB startup regression, and diff checks passed.

A fresh independent whole-change review found wildcard CPU exhaustion, excessive
selector/query work, incomplete native policy acceptance, ignored query semantics,
and URL selector handling. Five new regression methods failed on the reviewed
code, then passed with the fixes; the complete 34-test suite and final live gate
passed afterward. The review's URL-selector Minor was regraded Important and fixed.
No deferred reviewer minors remain.

The fixes use budgeted glob matching, immutable schema-leaf decisions, constant-time
literal field lookup, shared per-request work limits, typed complete policy checks,
and authorized metadata subsets. Unsupported `post_filter` and query-string
options fail before KalDB rather than silently changing results.

Generated credentials, API/UI reports, and screenshots are ignored under
`local/kaldb/permissions/.state/`. Do not commit those files. The local security
stack is stopped after testing so the previously running demo can be restored.
See the walkthrough for startup/resource requirements and the precise bounded
policy/query scope; this is not a production deployment qualification.

## Rulings I made

Historical rulings are retained in order. Later explicit user steering supersedes
the earlier temporary 3.9 choice. Each entry records its reason and cost/risk.

- Task 1: Ruling: the initial mixed-role test expected an unrestricted role to override FLS; changed the characterization to the observed pinned native behavior (restriction retained) — native policy must decide role merging — wrong expectations would incorrectly reject native behavior.

- Task 1: Ruling: use 3.9.0 for the isolated new demo, and adopt the documented whole-index denial for multi-field mappings and aliases — user prioritizes a demonstrable bounded scope tomorrow and the approved spec permits narrowing for version-specific safety issues; this does not substitute a policy engine — cost is rejecting whole multi-field indexes and additional 3.x UI compatibility work. Existing demo stays unchanged.

- Task 1: Ruling: add actual nested schema fields and a parent-exclusion user to the feasibility gate before gateway work — customer was an object, not a nested mapping — cost is a slightly larger fixture and native test matrix.

- Task 2: Ruling: 2.11 field caps AND filtered mappings expose descendants under exact excluded parents. Support exact negative leaf FLS only; reject include/wildcard/regex rules and any exclusion targeting a schema container. Native probes still determine effective visible leaves; this is unsupported-policy rejection, not a local role-merging engine — cost is rejecting more complex FLS policies.

- Task 2: Ruling: allow policy reader only mapping GET on registered schema indexes, in addition to role GET, so hidden unsupported multi-fields cannot escape schema validation — full schema is policy structure, never a user permission grant; reader search and writes remain forbidden — cost is exposing schema names to that private service identity.

- Task 3: Ruling: Armeria canonicalizes percent-encoded unreserved letters before the application sees the request. Verify authorization of the canonical private index instead of requiring rejection of its alternate spelling — authorization belongs to concrete dataset identity — cost is accepting equivalent authorized URL spellings.

- Task 5: Ruling: native root multi-get is allowed only when every doc names a saved-object system index; mixed data/system envelopes reject before forwarding — actual Dashboards saved-object bulk lookup requires it, native Security still authorizes all reads — cost is maintaining this native routing contract. New unit test RED→GREEN.

- Task 5: Ruling: permit and remove empty script_fields only, while retaining rejection of every nonempty script request; allow native Dashboards timeout and track_total_hits transport parameters — real pinned 2.11 search strategy emits these on normal dashboards reads — cost is bounded compatibility surface. Empty-script regression observed 400 RED then passed; transport parameter regression RED observed, GREEN package in progress.

- Task 5: First actual Team A table rendered all three KalDB fixture rows in browser. Metric failed because KalDB rejects size:0 without a concrete aggregation ("Hits or aggregation should be requested"). Ruling: use the native max(duration_ms) metric (12ms positive API control), rather than extend core count-only query semantics in this permissions branch — the user requested a two-user security showcase, and existing max aggregation supports it — cost is leaving count-only KalDB queries unsupported. Browser test now also requires the metric label and absence of failed panels. Native Console appends pretty=true; added transport regression RED and allowed this formatting parameter.

- Task 5: Ruling: prioritize two isolated user dashboard sessions with real saved-search panels, native tenant isolation, and browser-cookie Console requests over the earlier full/FLS-reader Discover navigation — user's later explicit requirement is two indexes and different dashboards for two users — cost is no separate Discover-page acceptance claim; full-reader private sentinel remains an API positive control.

- Verification Ruling: combine Tasks4/5 final runtime qualification into one cold-start verify.py all gate — it runs native, API, and browser suites sequentially without interactive traffic affecting recorder counters — cost is a shared completion gate rather than duplicate identical live API runs. Final native/API/UI output will close both tasks only on full success.

- Final: Ruling: keep 3.9 parked — explicit user steering — cost is no 3.9 compatibility claim.

- Final: Ruling: retain documented rejection of data scroll/PIT, SQL/PPL, complex FLS, DLS/masking and multi-fields/aliases — supported scope is a bounded 2.11 demo — cost is rejecting those policies/operations.

- Final: Ruling: retain max-duration panel and two-dashboard acceptance instead of core count-only/Discover work — both demonstrated real native security and actual KalDB fixtures — cost is no count-only or separate Discover acceptance claim.

- Final: Ruling: keep schema synchronization operator-managed — automatic KalDB/native schema synchronization is outside this demo, and unknown response fields are projected away — cost is operational maintenance and conservative failures if schemas diverge.

- Final: Ruling: retain isolated local trust boundary rather than add production deployment hardening — user requested a local demo, published ports are loopback and KalDB/policy/control remain private — cost is requiring a separate deployment/security review before production use.

- Final: Ruling: reject post_filter and query-string operator/options rather than approximate them — KalDB ignores post_filter and the previous rewrite lost AND; merging post_filter into query would alter aggregation semantics — cost is a narrower documented query grammar that fails before KalDB instead of returning incorrect results.

- Final: Ruling: apply fixed selector/query/schema budgets shared across multi-search — availability must hold even for malicious syntactically Basic requests before native authentication — cost is rejecting oversized legitimate requests in this bounded demo.

## Deferred minors

None from the final independent review. The URL-selector finding was fixed.

