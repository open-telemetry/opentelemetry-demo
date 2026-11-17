# KalDB security demo — OpenSearch 2.11

This isolated demo uses the real OpenSearch and Dashboards **2.11.1 Security
plugins** to manage users, roles, and tenants. The Java gateway checks native
permissions before querying actual KalDB data. The 3.9 experiment is parked on
a separate branch.

| Login | Index | Dashboard tenant |
| --- | --- | --- |
| `user1` | `permissions-demo-public` | `team_a` |
| `user2` | `permissions-demo-private` | `team_b` |

Each tenant contains its own dashboard and supporting saved objects. User 2 also
has FLS exclusions for `secret`, `customer.email`, and `events.secret`.

Requires Docker with 8 GiB available to this isolated stack, Java 21, Maven, and
`uv`; browser verification also needs Chrome. Stop other large demo stacks first.
Use a KalDB checkout containing the paired gateway changes on
[`codex/security-demo-2.11-review`](https://github.com/kaldb/kaldb/tree/codex/security-demo-2.11-review).
From this OTel repository root:

```sh
./local/kaldb/permissions/security_demo.sh start --kaldb-home /path/to/kaldb
./local/kaldb/permissions/security_demo.sh verify all
./local/kaldb/permissions/security_demo.sh showcase
```

Startup builds the selected checkout, starts isolated services, registers two
datasets, ingests synthetic records, and provisions both native tenants. Use
`--skip-build` to reuse existing jars from that checkout. Cached Python packages
can be used with `uv run --offline`.

`stop` removes this isolated project's containers and their synthetic runtime
state. Starting again provisions the fixtures anew; generated login values stay
in `.state/`. The script does not stop or alter other Compose projects.

After successful provisioning, use separate browser profiles:

- [User 1 dashboard](http://127.0.0.1:25601/app/dashboards?security_tenant=team_a#/view/security-user1-dashboard)
- [User 2 dashboard](http://127.0.0.1:25601/app/dashboards?security_tenant=team_b#/view/security-user2-dashboard)

Login values are in ignored `local/kaldb/permissions/.state/credentials.json`.
Open that local file for each password; scripts do not print them.

## Set permissions

These commands update real native Security roles for demo-owned users:

```sh
# Revoke user 1's data access while retaining its dashboard tenant.
uv run --with-requirements local/kaldb/permissions/requirements.txt python local/kaldb/permissions/demo.py permissions --user user1 --access none

# Restore its original index and tenant rights.
uv run --with-requirements local/kaldb/permissions/requirements.txt python local/kaldb/permissions/demo.py permissions --user user1 --access own --tenant-access own
```

`--access own|none|both` controls indexes; `--tenant-access own|none|both` controls
saved dashboards separately. Restore both users to their own index/tenant before
the standard demo. `demo.py showcase` runs API checks and prints dashboard links.

To inspect configuration in Dashboards, log in as admin and open **Security →
Roles → demo_user1** or `demo_user2`. Index permissions select the dataset; tenant
permissions select `team_a` or `team_b` with `kibana_all_read`. Role mappings bind
each role to its user. Supported FLS uses exact excluded leaf names. Native
Security governs saved dashboard access; the Java gateway enforces data access
before KalDB.

## Five-minute walkthrough

1. Run `verify all` before opening interactive sessions. It logs in with fresh
   Chrome profiles, checks actual fixture rows, and writes sanitized API/UI
   reports plus screenshots under `.state/`. Keep automatic refresh paused so
   interactive queries do not interfere with the recorder's zero-call checks.
2. Open the user 1 link in one browser profile and log in as `user1`. Confirm
   the `team_a` tenant if prompted. The dashboard displays Team A records and
   maximum duration (12 ms). Its dashboard list contains only **Team A — Security demo**.
3. Open the user 2 link in another browser profile as `user2`, selecting
   `team_b`. It displays Team B records. Team A's dashboard is absent. The
   restricted index pattern excludes `secret`, `customer.email`, and
   `events.secret`; those values are also removed from gateway responses.
4. Log in as `admin` in a third profile. Open **Security → Roles → demo_user1**.
   Index permissions grant `read` on `permissions-demo-public`; tenant
   permissions grant `kibana_all_read` on `team_a`. **Mapped users** contains
   `user1`. Inspect `demo_user2` to see its excluded leaf fields and own tenant.
5. Run the revoke command above. Refresh user 1's dashboard: its saved layout
   remains available, but its data requests fail with HTTP 403. Restore access
   with `--access own --tenant-access own` and refresh again. The verification
   scripts prove that each denied data request adds zero KalDB calls.

For an explicit request from a logged-in Dashboards session, use **Dev Tools →
Console**. User 1's own request succeeds and its other-index request fails:

```http
POST permissions-demo-public/_search
{"size": 10}

POST permissions-demo-private/_search
{"size": 10}
```

As user 2, `POST permissions-demo-private/_search` succeeds; adding
`{"query":{"term":{"secret":"PRIVATE_B_SENTINEL"}}}` fails with HTTP 403.
The automated UI check exercises this same Console proxy using browser cookies.
The native read-only UI mode can hide Dev Tools for data users; in that case,
use the browser-mediated automated check, or temporarily omit the
`opensearch_security.readonly_mode.roles` setting to expose Console. This
display setting never grants data permissions. Admin can always use Console
to change the real role, for example:

```http
PUT _plugins/_security/api/roles/demo_user1
{
  "cluster_permissions": ["cluster_composite_ops_ro", "cluster:monitor/main", "cluster:monitor/health", "cluster:monitor/nodes/info"],
  "index_permissions": [],
  "tenant_permissions": [{"tenant_patterns":["team_a"],"allowed_actions":["kibana_all_read"]}]
}
```

Restore the role with the script after experimenting. Index rights govern data;
tenant rights govern saved dashboards. A tenant grant alone cannot authorize a
KalDB query. To change FLS in the native role editor, choose **Exclude** and
literal leaf names (`secret`, `customer.email`, `events.secret`). The stored
role JSON uses `~` prefixes for these exclusions.

Only the gateway (loopback 29201) and Dashboards (loopback 25601) are published.
KalDB query/setup endpoints, native OpenSearch, and recorder control are private.
API verification checks positive fixtures, zero-call denials, role revocation,
unsupported policies, and authority outage, restoring demo-owned policies afterward.
Run the API matrix before opening interactive dashboards so background queries
do not affect counter comparisons. A complete passing run writes sanitized
`.state/api-report.json`. Browser verification writes `.state/ui-report.json`
only after both users render actual data and the admin role-change check passes.

Secured mode rejects multi-field/alias schemas, parent/include/wildcard/regex FLS,
DLS, masking, scripts, runtime fields, `post_filter`, and unimplemented query operations. This
is a bounded security demo, not full OpenSearch query compatibility.
Literal `query_string`/`simple_query_string` supports `query`, `fields`, and
`default_field`; operator and other options are rejected instead of ignored.
Use structured supported queries for filters. URL `fields` selectors apply only
to `_field_caps`; unsupported search URL field selectors fail before KalDB.
Wildcard matching has a shared work limit. Each request allows up to 2,048
field selectors and query nodes, 4,096 expanded text clauses, and schemas of up
to 2,048 leaves. Multi-search shares these budgets across all items. Metadata
discovery allows at most 32 index selectors of 128 characters each. Excessive
requests fail closed; these are demo limits, not tunable production quotas.
The dashboard's maximum-duration panel uses a concrete aggregation. KalDB's
count-only `size: 0` requests remain unsupported in this branch.

See the [evidence and proposed design revision](../../../docs/superpowers/specs/2026-11-15-kaldb-permissions-native-feasibility.md).

Run the isolated native harness from the repository root:

```sh
uv run --with-requirements local/kaldb/permissions/requirements.txt python local/kaldb/permissions/demo.py native-start
uv run --with-requirements local/kaldb/permissions/requirements.txt python local/kaldb/permissions/verify.py native
```

Verification reports checks without printing passwords. Native OpenSearch has no published host port. The
helper accesses it through this Compose project's container.

Generated credentials and certificates live in ignored `.state/`. Credential
values are passed to native curl over standard input, never process arguments.
Certificates are local test certificates valid for seven days. Generated state
must not be committed or used outside this local demo.

To reproduce the unsafe oracle, stop this isolated project first and start it
with `demo.py native-start --unsafe-multifields`, then run native verification.
That schema must fail the multi-field assertions; do not use it for the demo.

To stop only this isolated project:

```sh
uv run --with-requirements local/kaldb/permissions/requirements.txt python local/kaldb/permissions/demo.py native-stop
```
