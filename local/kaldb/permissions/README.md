# KalDB security demo — OpenSearch 2.11 review snapshot

**Work in progress:** native 2.11 authentication, index/FLS probes, and two-user
tenant isolation have passed. Gateway enforcement has tested index/field checks,
atomic multi-search, and response projection. Both users have received actual
KalDB fixtures through the gateway. Full dashboard provisioning, the API matrix,
and browser verification are still being completed. This snapshot is not yet a
verified end-to-end demo. The 3.9 experiment is parked on a separate branch.

| Login | Index | Dashboard tenant |
| --- | --- | --- |
| `user1` | `permissions-demo-public` | `team_a` |
| `user2` | `permissions-demo-private` | `team_b` |

Each tenant contains its own dashboard and supporting saved objects. User 2 also
has FLS exclusions for `secret`, `customer.email`, and `events.secret`.

Requires Docker, Java 21, Maven, and `uv`; browser verification also needs Chrome.
Use a KalDB checkout containing the paired gateway changes on
[`codex/security-demo-2.11-review`](https://github.com/kaldb/kaldb/tree/codex/security-demo-2.11-review).
From this OTel repository root:

```sh
uv run --with-requirements local/kaldb/permissions/requirements.txt python local/kaldb/permissions/demo.py start --kaldb-home /path/to/kaldb
uv run --with-requirements local/kaldb/permissions/requirements.txt python local/kaldb/permissions/verify.py api
```

Startup builds the selected checkout, starts isolated services, registers two
datasets, ingests synthetic records, and provisions both native tenants. Use
`--skip-build` to reuse existing jars from that checkout. Cached Python packages
can be used with `uv run --offline`.

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
the standard demo. `demo.py showcase` runs API checks and prints dashboard links;
the final browser walkthrough is still in progress.

To inspect configuration in Dashboards, log in as admin and open **Security →
Roles → demo_user1** or `demo_user2`. Index permissions select the dataset; tenant
permissions select `team_a` or `team_b` with `kibana_all_read`. Role mappings bind
each role to its user. Supported FLS uses exact excluded leaf names. Native
Security governs saved dashboard access; the Java gateway enforces data access
before KalDB.

Only the gateway (loopback 29201) and Dashboards (loopback 25601) are published.
KalDB query/setup endpoints, native OpenSearch, and recorder control are private.
API verification checks positive fixtures, zero-call denials, role revocation,
unsupported policies, and authority outage, restoring demo-owned policies afterward.
Run the API matrix before opening interactive dashboards so background queries
do not affect counter comparisons. A complete passing run writes sanitized
`.state/api-report.json`.

Secured mode rejects multi-field/alias schemas, parent/include/wildcard/regex FLS,
DLS, masking, scripts, runtime fields, and unimplemented query operations. This
is a bounded security demo, not full OpenSearch query compatibility.

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
