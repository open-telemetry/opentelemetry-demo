#!/usr/bin/env python3
"""Verify real native policies and the KalDB permissions demo without logging secrets."""

import argparse
import json


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def native_checks(client):
    """Characterize the native authorization guarantees required by the gateway."""
    failures = []

    def check(condition, message):
        print(("PASS " if condition else "FAIL ") + message, flush=True)
        if not condition:
            failures.append(message)

    public = "permissions-demo-public"
    private = "permissions-demo-private"
    status, _ = client("GET", "/_cluster/health", user=None)
    check(status == 401, f"Unauthenticated request: expected 401, got {status}")
    status, _ = client("GET", "/_cluster/health", user="invalid")
    check(status == 401, f"Invalid credentials: expected 401, got {status}")
    for user in ("full_reader", "fls_reader", "mixed_reader"):
        status, result = client("POST", f"/{public}/_search", {"size": 0, "query": {"match_none": {}}}, user)
        shards = result.get("_shards", {})
        check(status == 200 and shards.get("failed") == 0 and shards.get("successful", 0) > 0,
              f"{user} empty-index search authorization")
    for dataset in (public, private):
        status, result = client("GET", f"/{dataset}/_count", user="admin")
        check(status == 200 and result.get("count") == 0, f"{dataset} contains zero telemetry documents")
    status, _ = client("POST", f"/{private}/_search", {"size": 0, "query": {"match_none": {}}}, "fls_reader")
    check(status == 403, f"FLS reader private dataset denial: expected 403, got {status}")
    status, _ = client("POST", f"/{public}/_search", {"size": 0}, "no_access")
    check(status == 403, f"No-access user public dataset denial: expected 403, got {status}")
    visible = {}
    for user in ("full_reader", "fls_reader", "mixed_reader"):
        status, result = client("GET", f"/{public}/_field_caps?fields=*", user=user)
        check(status == 200 and isinstance(result.get("fields"), dict), f"{user} native field capabilities")
        visible[user] = set(result.get("fields", {}))
    check("secret" in visible["full_reader"], "Full reader sees private field (positive control)")
    check("body" in visible["fls_reader"], "FLS reader sees public body field")
    for hidden in ("secret", "customer.email", "events.secret", "body.keyword"):
        check(hidden not in visible["fls_reader"], f"Empty-index FLS hides {hidden}")
    check("customer.region" in visible["fls_reader"], "Public sibling of private object field remains visible")
    check("events.code" in visible["fls_reader"], "Public leaf of a genuine nested field remains visible")
    status, result = client("GET", f"/{public}/_field_caps?fields=*", user="parent_reader")
    parent_fields = set(result.get("fields", {}))
    check(status == 200 and {"customer.region", "events.code"}.issubset(parent_fields),
          "Negative control: 2.11 parent exclusions leave descendants in capabilities; policy must be rejected")
    status, parent_mapping = client("GET", f"/{public}/_mapping", user="parent_reader")
    properties = parent_mapping.get(public, {}).get("mappings", {}).get("properties", {})
    check(status == 200 and "customer" in properties and "events" in properties,
          "Negative control: 2.11 filtered mappings cannot establish parent-exclusion permissions")
    # 2.11 defaults do not let the unrestricted role override FLS from another role.
    check(visible["mixed_reader"] == visible["fls_reader"], "Mixed roles retain the native FLS restriction")
    status, result = client("GET", f"/{public}/_field_caps?fields=body.keyword", user="fls_reader")
    check(status == 200 and "body.keyword" not in result.get("fields", {}),
          "Explicit field-capabilities probe also hides excluded body.keyword")
    status, _ = client("POST", "/permissions-demo-missing/_search", {"size": 0}, "full_reader")
    check(status in (403, 404), f"Missing schema index denied: got {status}")
    status, roles = client("GET", "/_plugins/_security/api/roles", user="policy_reader")
    check(status == 200 and "demo_fls" in roles, f"Policy reader can inspect roles: got {status}")
    check("~body.keyword" in roles.get("demo_fls", {}).get("index_permissions", [{}])[0].get("fls", []),
          "Effective role explicitly excludes body.keyword")
    status, _ = client("PUT", "/_plugins/_security/api/roles/should-not-exist", {"cluster_permissions": []}, "policy_reader")
    check(status == 403, f"Policy reader cannot write roles: got {status}")
    status, _ = client("GET", "/_plugins/_security/api/internalusers", user="policy_reader")
    check(status == 403, f"Policy reader cannot access internal users: got {status}")
    status, mapping = client("GET", f"/{public}/_mapping", user="policy_reader")
    check(status == 200 and "secret" in mapping.get(public, {}).get("mappings", {}).get("properties", {}),
          "Policy reader can inspect complete schema for unsupported features")
    status, _ = client("POST", f"/{public}/_search", {"size": 0}, "policy_reader")
    check(status == 403, f"Policy reader cannot search data: got {status}")
    require(not failures, f"Native feasibility gate failed ({len(failures)} checks); do not implement this oracle")
    print("PASS qualified native policy gate (standalone/object/nested schema; multi-fields unsupported)", flush=True)
    return visible


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["native", "api", "ui", "all"])
    parser.add_argument("--baseline-url", help="Read-only native authentication check against an existing server")
    args = parser.parse_args()
    if args.baseline_url:
        import urllib.error
        import urllib.request
        try:
            with urllib.request.urlopen(args.baseline_url + "/_cluster/health", timeout=10) as response:
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code
        require(status == 401, f"Unauthenticated native request expected 401; got {status}")
        return
    from demo import native_request
    if args.mode == "native":
        native_checks(native_request)
    else:
        raise SystemExit("API/UI verification is not implemented yet")


if __name__ == "__main__":
    main()
