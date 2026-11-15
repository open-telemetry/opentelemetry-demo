# Native permission probe feasibility

Status: the approved OpenSearch 2.11.1 oracle failed its feasibility gate.
Gateway implementation has not started. This report contains synthetic schema
names and field names only; it contains no passwords or telemetry.

## Reproduction

From this repository's implementation worktree:

```sh
uv run --with-requirements local/kaldb/permissions/requirements.txt python local/kaldb/permissions/demo.py native-start
uv run --with-requirements local/kaldb/permissions/requirements.txt python local/kaldb/permissions/verify.py native
```

The second command deliberately exits nonzero. Do not treat the environment as a
working permissions demo. Stop this isolated environment with `demo.py native-stop`.
The existing OTel/KalDB stack is a separate Compose project.

## Results

The native checks ran against `opensearchproject/opensearch:2.11.1`, with Security
enabled, generated internal users/passwords, a private CA, and empty schema
indexes. Of 25 assertions, 23 passed and two failed.

| Check | Observed |
| --- | --- |
| Missing and invalid credentials | 401 |
| Authorized search on empty public schema index | 200, successful shard, no failed shards |
| Restricted reader searches private dataset | 403 |
| No-access reader searches public dataset | 403 |
| Both schema indexes | Zero documents |
| Full reader field capabilities | Includes `secret` |
| Restricted field capabilities | Hides `secret` and `customer.email`; keeps `customer.region` |
| Mixed full and restricted roles | Retains restricted field visibility with the pinned defaults |
| Policy reader role GET | 200, includes the configured FLS definition |
| Policy reader role PUT and internal-users GET | 403 |
| Restricted `fields=*` capabilities | **Includes excluded `body.keyword`** |
| Restricted `fields=body.keyword` capabilities | **Also includes excluded `body.keyword`** |

The native role response confirms the exclusion is applied in the configuration:

```json
{"fls": ["~secret", "~customer.email", "~body.keyword"]}
```

Nevertheless, both field-capability requests report:

```json
{"body.keyword": {"keyword": {"type": "keyword", "searchable": true, "aggregatable": true}}}
```

This disproves the proposed use of field capabilities as a complete effective
field-permission oracle. It is not evidence that KalDB leaked data: the gateway
has not been changed and the native indexes contain no documents.

## Source investigation

The pinned [Security metadata field filter](https://github.com/opensearch-project/security/blob/2.11.1.0/src/main/java/org/opensearch/security/OpenSearchSecurityPlugin.java#L1862)
tests FLS patterns after passing field names through `handleKeyword`. That helper
removes the `.keyword` suffix. Thus `~body.keyword` is compared to `body` for
metadata filtering and does not remove `body.keyword` from field capabilities.
The [Lucene FLS reader](https://github.com/opensearch-project/security/blob/2.11.1.0/src/main/java/org/opensearch/security/configuration/DlsFlsFilterLeafReader.java#L140)
constructs field exclusions differently. Metadata visibility alone therefore
cannot establish the required guarantee.

The mixed-role test's initial expectation of unrestricted access was corrected
after observing native behavior. The gateway must follow the native result;
it must not implement its own role-merging rules.

## Adopted bounded revision

Following the user's request to update OpenSearch and target a demo tomorrow,
the new isolated demo uses 3.9.0. The original 25-assertion matrix was also run
unchanged against that release: 23 passed and the same two multi-field checks
failed. The native 3.9 field filter shares field restriction code with data
filtering, but that code still normalizes `.keyword` names. Upgrading alone does
not meet the demo's independent multi-field permission requirement.

Keep the Java gateway and native policy authority, but narrow the secured demo
to indexes **without any multi-field mappings**:

1. Before any KalDB request, require a complete mapping from the native schema
   index. Reject the entire index if any mapping contains a `fields` definition
   or field aliases. Do not infer multi-field permissions from field capabilities.
2. Register demo schemas with standalone text/keyword fields and object/nested
   leaves. Remove `body.keyword` from the supported fixture schema, keeping
   `body` as text. Explicit `body.keyword` requests remain denied as unknown.
3. Treat object/nested parent names as containers, never as grants to all their
   children. Build projections from authorized leaf names only.
4. Retain the failing multi-field reproduction as a negative control. Add
   gateway/integration checks proving such a schema receives a denial and zero
   KalDB calls. Repeat the native feasibility gate on the qualified schemas,
   including genuine nested fields and parent exclusions, before implementing
   the remaining gateway behavior.
5. Document multi-fields as unsupported in secured mode. A future version that
   supports them must prove an exact native oracle with these regression cases.

This preserves a usable Discover/index/FLS demo and avoids implementing a local
FLS policy engine. Its cost is whole-index denial when multi-fields are present.
An alternative would be to expand the design to a native Security extension or a
different pinned OpenSearch version, then prove that approach with this same
gate before continuing. No alternative has been implemented or represented as
passing. The original reproduction can be repeated on a fresh isolated native
project with `demo.py native-start --unsafe-multifields`; it must still fail the
native gate. The default fixture schemas omit multi-fields.
