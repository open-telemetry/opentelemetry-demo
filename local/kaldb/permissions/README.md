# KalDB permissions demo — native feasibility harness

This work is in progress. The qualified OpenSearch 3.9.0 schema passed all 28
native permission checks. The Java gateway and full Dashboards demo have not
been implemented. Secured mode will reject whole indexes containing multi-fields
or aliases; fixture schemas use standalone text/keyword and object/nested fields.

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
`PERMISSIONS_OPENSEARCH_IMAGE` can select an exact image for a version comparison.

To stop only this isolated project:

```sh
uv run --with-requirements local/kaldb/permissions/requirements.txt python local/kaldb/permissions/demo.py native-stop
```
