#!/usr/bin/env python3
"""Manage an isolated KalDB/OpenSearch permissions demo with generated credentials."""

import argparse
import json
from pathlib import Path
import secrets
import subprocess
import time

HERE = Path(__file__).resolve().parent
STATE = HERE / ".state"
DATASETS = ("permissions-demo-public", "permissions-demo-private")
USERS = ("admin", "full_reader", "fls_reader", "mixed_reader", "parent_reader", "no_access", "policy_reader")


def compose(*args, **kwargs):
    """Run Compose against this demo's project only."""
    return subprocess.run(["docker", "compose", "-f", str(HERE / "compose.yaml"), *args],
                          cwd=HERE, check=True, **kwargs)


def write_json(path, value):
    """Write JSON, which is also valid YAML for the native Security configuration."""
    path.write_text(json.dumps(value, indent=2) + "\n")
    path.chmod(0o644)


def prepare_state():
    """Generate private state, native identities, roles and a local TLS authority."""
    import bcrypt

    STATE.mkdir(exist_ok=True, mode=0o700)
    credentials_path = STATE / "credentials.json"
    if credentials_path.exists():
        credentials = json.loads(credentials_path.read_text())
    else:
        credentials = {}
    for name in USERS:
        if name not in credentials:
            credentials[name] = secrets.token_urlsafe(30)
    credentials_path.write_text(json.dumps(credentials))
    credentials_path.chmod(0o600)
    certs = STATE / "certs"
    certs.mkdir(exist_ok=True, mode=0o755)
    ca_key = STATE / "ca-key.pem"
    if not (certs / "node.pem").exists():
        commands = [
            ["req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(ca_key),
             "-out", str(certs / "ca.pem"), "-subj", "/CN=KalDB-Permissions-CA", "-days", "7"],
            ["genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(certs / "node-key.pem")],
            ["req", "-new", "-key", str(certs / "node-key.pem"), "-out", str(STATE / "node.csr"), "-subj", "/CN=opensearch"],
        ]
        extension = STATE / "node.ext"
        extension.write_text("subjectAltName=DNS:opensearch,DNS:localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth,clientAuth\n")
        commands.append(["x509", "-req", "-in", str(STATE / "node.csr"), "-CA", str(certs / "ca.pem"),
                         "-CAkey", str(ca_key), "-CAcreateserial", "-out", str(certs / "node.pem"),
                         "-days", "7", "-extfile", str(extension)])
        for command in commands:
            subprocess.run(["openssl", *command], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ca_key.chmod(0o600)
        # The private parent directory protects host access; the bind-mounted
        # cert directory must be readable by OpenSearch's container UID.
        for path in certs.iterdir():
            path.chmod(0o644)
    security = STATE / "security"
    security.mkdir(exist_ok=True, mode=0o755)
    read_actions = ["indices:data/read/*", "indices:admin/mappings/get", "indices:admin/resolve/index"]
    full = {"cluster_permissions": ["cluster_composite_ops_ro", "cluster:monitor/main", "cluster:monitor/health"],
            "index_permissions": [{"index_patterns": list(DATASETS), "allowed_actions": read_actions}]}
    restricted = {"cluster_permissions": full["cluster_permissions"], "index_permissions": [{
        "index_patterns": [DATASETS[0]], "allowed_actions": read_actions,
        "fls": ["~secret", "~customer.email", "~events.secret", "~body.keyword"]}]}
    parent_restricted = {"cluster_permissions": full["cluster_permissions"], "index_permissions": [{
        "index_patterns": [DATASETS[0]], "allowed_actions": read_actions, "fls": ["~customer", "~events"]}]}
    roles = {
        "_meta": {"type": "roles", "config_version": 2},
        "demo_admin": {"cluster_permissions": ["*"],
                       "index_permissions": [{"index_patterns": ["*"], "allowed_actions": ["*"]}],
                       "tenant_permissions": [{"tenant_patterns": ["*"], "allowed_actions": ["kibana_all_write"]}]},
        "demo_full": full, "demo_fls": restricted, "demo_parent": parent_restricted,
        "demo_policy_reader": {"cluster_permissions": [], "index_permissions": []},
        "demo_dashboards": {"cluster_permissions": ["cluster_composite_ops_ro", "cluster:monitor/main", "cluster:monitor/nodes/info"],
                            "index_permissions": [{"index_patterns": [".kibana*", ".opensearch_dashboards*"], "allowed_actions": ["*"]}],
                            "tenant_permissions": [{"tenant_patterns": ["global_tenant"], "allowed_actions": ["kibana_all_write"]}]},
    }
    mappings = {"_meta": {"type": "rolesmapping", "config_version": 2},
                "demo_admin": {"users": ["admin"]},
                "demo_full": {"users": ["full_reader", "mixed_reader"]},
                "demo_fls": {"users": ["fls_reader", "mixed_reader"]},
                "demo_parent": {"users": ["parent_reader"]},
                "demo_policy_reader": {"users": ["policy_reader"]},
                "demo_dashboards": {"users": ["full_reader", "fls_reader", "mixed_reader", "no_access"]}}
    users = {"_meta": {"type": "internalusers", "config_version": 2}}
    for name, password in credentials.items():
        users[name] = {"hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10)).decode(), "backend_roles": []}
    write_json(security / "roles.yml", roles)
    write_json(security / "roles_mapping.yml", mappings)
    write_json(security / "internal_users.yml", users)
    write_json(security / "config.yml", {"_meta": {"type": "config", "config_version": 2}, "config": {"dynamic": {
        "http": {"anonymous_auth_enabled": False}, "authc": {"basic_internal_auth_domain": {
            "http_enabled": True, "transport_enabled": True, "order": 0,
            "http_authenticator": {"type": "basic", "challenge": False}, "authentication_backend": {"type": "intern"}}}}}})
    for filename, kind in [("action_groups.yml", "actiongroups"), ("tenants.yml", "tenants"),
                           ("nodes_dn.yml", "nodesdn"), ("allowlist.yml", "allowlist"), ("audit.yml", "audit")]:
        value = {"_meta": {"type": kind, "config_version": 2}}
        if kind == "audit":
            value["config"] = {"enabled": False, "audit": {"exclude_sensitive_headers": True},
                               "compliance": {"enabled": False}}
        write_json(security / filename, value)
    os_config = {"cluster.name": "kaldb-permissions", "node.name": "permissions-opensearch", "network.host": "0.0.0.0",
                 "plugins.security.allow_default_init_securityindex": True,
                 "plugins.security.nodes_dn": ["CN=opensearch"],
                 "plugins.security.restapi.roles_enabled": ["demo_admin", "demo_policy_reader"],
                 "plugins.security.ssl.transport.pemcert_filepath": "permissions-certs/node.pem",
                 "plugins.security.ssl.transport.pemkey_filepath": "permissions-certs/node-key.pem",
                 "plugins.security.ssl.transport.pemtrustedcas_filepath": "permissions-certs/ca.pem",
                 "plugins.security.ssl.transport.enforce_hostname_verification": True,
                 "plugins.security.ssl.http.enabled": True,
                 "plugins.security.ssl.http.pemcert_filepath": "permissions-certs/node.pem",
                 "plugins.security.ssl.http.pemkey_filepath": "permissions-certs/node-key.pem",
                 "plugins.security.ssl.http.pemtrustedcas_filepath": "permissions-certs/ca.pem"}
    methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
    for endpoint in ["ACTIONGROUPS", "ALLOWLIST", "AUDIT", "CACHE", "CONFIG", "INTERNALUSERS", "NODESDN", "ROLESMAPPING", "TENANTS", "WHITELIST", "SSL", "DISTINGUISHEDNAMES"]:
        os_config["plugins.security.restapi.endpoints_disabled.demo_policy_reader." + endpoint] = methods
    os_config["plugins.security.restapi.endpoints_disabled.demo_policy_reader.ROLES"] = methods[1:]
    write_json(STATE / "opensearch.yml", os_config)


def native_request(method, path, body=None, user="admin"):
    """Request the private native authorizer without credentials in process arguments."""
    credentials = json.loads((STATE / "credentials.json").read_text())
    config = ["url = " + json.dumps("https://localhost:9200" + path), "request = " + json.dumps(method),
              'cacert = "/usr/share/opensearch/config/permissions-certs/ca.pem"', 'max-time = "10"']
    if user is not None:
        password = credentials.get(user, "invalid")
        config.append("user = " + json.dumps(user + ":" + password))
    if body is not None:
        config += ['header = "content-type: application/json"', "data-binary = " + json.dumps(json.dumps(body))]
    result = compose("exec", "-T", "opensearch", "curl", "-sS", "--config", "-", "-w", "\n%{http_code}",
                     input="\n".join(config) + "\n", text=True, capture_output=True)
    payload, status = result.stdout.rsplit("\n", 1)
    try:
        data = json.loads(payload)
    except ValueError:
        data = {"message": payload[:200]}
    return int(status), data


def seed_native(multifields=False):
    """Create schema-only native indexes; telemetry fixtures stay in KalDB."""
    schema = {"mappings": {"properties": {
        "@timestamp": {"type": "date"}, "body": {"type": "text"},
        "secret": {"type": "keyword"}, "customer": {"properties": {"email": {"type": "keyword"}, "region": {"type": "keyword"}}},
        "events": {"type": "nested", "properties": {"code": {"type": "keyword"}, "secret": {"type": "keyword"}}},
        "duration_ms": {"type": "long"}, "level": {"type": "keyword"}}}}
    if multifields:
        schema["mappings"]["properties"]["body"]["fields"] = {"keyword": {"type": "keyword"}}
    for dataset in DATASETS:
        status, _ = native_request("GET", "/" + dataset + "/_mapping")
        if status == 404:
            status, response = native_request("PUT", "/" + dataset, schema)
            if status != 200:
                raise RuntimeError(f"Schema index creation failed: HTTP {status}")
        elif status != 200:
            raise RuntimeError(f"Schema index lookup failed: HTTP {status}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["native-start", "native-stop", "start", "stop", "status"])
    parser.add_argument("--unsafe-multifields", action="store_true",
                        help="Reproduce the rejected multi-field oracle on fresh native indexes")
    args = parser.parse_args()
    if args.action in ("native-stop", "stop"):
        compose("down")
    elif args.action == "status":
        compose("ps")
    elif args.action == "native-start":
        prepare_state()
        compose("up", "-d", "opensearch")
        for attempt in range(90):
            try:
                status, _ = native_request("GET", "/_cluster/health")
                if status == 200:
                    break
            except (subprocess.CalledProcessError, ValueError):
                pass
            time.sleep(1)
        else:
            raise SystemExit("Native authorizer did not become ready; inspect this demo's OpenSearch logs")
        seed_native(args.unsafe_multifields)
        print("Native security ready. Credentials are in local/kaldb/permissions/.state/credentials.json")
    else:
        raise SystemExit("Complete demo startup is not implemented yet")


if __name__ == "__main__":
    main()
