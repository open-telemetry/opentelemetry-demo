#!/usr/bin/env python3
"""Manage an isolated KalDB/OpenSearch permissions demo with generated credentials."""

import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time
import zipfile
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
STATE = HERE / ".state"
DATASETS = ("permissions-demo-public", "permissions-demo-private")
USERS = ("admin", "user1", "user2", "dashboards_server", "full_reader", "fls_reader", "mixed_reader", "parent_reader", "no_access", "policy_reader")
GATEWAY_URL = "http://127.0.0.1:29201"
DASHBOARDS_URL = "http://127.0.0.1:25601"


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
        "demo_policy_reader": {"cluster_permissions": [], "index_permissions": [{
            "index_patterns": list(DATASETS), "allowed_actions": ["indices:admin/mappings/get"]}]},
        "demo_dashboards": {"cluster_permissions": ["cluster_composite_ops_ro", "cluster:monitor/main", "cluster:monitor/nodes/info"],
                            "index_permissions": [{"index_patterns": [".kibana*", ".opensearch_dashboards*"], "allowed_actions": ["*"]}],
                            "tenant_permissions": [{"tenant_patterns": ["global_tenant"], "allowed_actions": ["kibana_all_write"]}]},
    }
    for user, dataset, tenant in (("user1", DATASETS[0], "team_a"), ("user2", DATASETS[1], "team_b")):
        permission = {"index_patterns": [dataset], "allowed_actions": read_actions}
        if user == "user2":
            permission["fls"] = ["~secret", "~customer.email", "~events.secret"]
        roles["demo_" + user] = {
            "cluster_permissions": full["cluster_permissions"] + ["cluster:monitor/nodes/info"],
            "index_permissions": [permission],
            "tenant_permissions": [{"tenant_patterns": [tenant], "allowed_actions": ["kibana_all_read"]}],
        }
    mappings = {"_meta": {"type": "rolesmapping", "config_version": 2},
                "demo_admin": {"users": ["admin"]},
                "demo_full": {"users": ["full_reader", "mixed_reader"]},
                "demo_fls": {"users": ["fls_reader", "mixed_reader"]},
                "demo_parent": {"users": ["parent_reader"]},
                "demo_policy_reader": {"users": ["policy_reader"]},
                "demo_dashboards": {"users": ["full_reader", "fls_reader", "mixed_reader", "no_access"]}}
    mappings.update({"demo_user1": {"users": ["user1"]}, "demo_user2": {"users": ["user2"]},
                     "kibana_server": {"users": ["dashboards_server"]}})
    users = {"_meta": {"type": "internalusers", "config_version": 2}}
    for name, password in credentials.items():
        users[name] = {"hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10)).decode(), "backend_roles": []}
    write_json(security / "roles.yml", roles)
    write_json(security / "roles_mapping.yml", mappings)
    write_json(security / "internal_users.yml", users)
    policy_credentials = STATE / "gateway-policy.json"
    policy_credentials.write_text(json.dumps({"username": "policy_reader", "password": credentials["policy_reader"]}))
    policy_credentials.chmod(0o600)
    write_json(security / "config.yml", {"_meta": {"type": "config", "config_version": 2}, "config": {"dynamic": {
        "kibana": {"multitenancy_enabled": True, "private_tenant_enabled": False,
                   "default_tenant": "team_a", "server_username": "dashboards_server", "index": ".kibana"},
        "http": {"anonymous_auth_enabled": False}, "authc": {"basic_internal_auth_domain": {
            "http_enabled": True, "transport_enabled": True, "order": 0,
            "http_authenticator": {"type": "basic", "challenge": False}, "authentication_backend": {"type": "intern"}}}}}})
    for filename, kind in [("action_groups.yml", "actiongroups"), ("tenants.yml", "tenants"),
                           ("nodes_dn.yml", "nodesdn"), ("allowlist.yml", "allowlist"), ("audit.yml", "audit")]:
        value = {"_meta": {"type": kind, "config_version": 2}}
        if kind == "tenants":
            value.update({"team_a": {"reserved": False, "description": "User 1 dashboard"},
                          "team_b": {"reserved": False, "description": "User 2 dashboard"}})
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
    # Host access is protected by the private .state directory; this file is
    # mounted into the Dashboards container only, whose service UID must read it.
    write_json(STATE / "dashboards.yml", {
        "server.host": "0.0.0.0", "server.name": "kaldb-permissions",
        "opensearch.hosts": ["http://gateway:9200"],
        "opensearch.username": "dashboards_server", "opensearch.password": credentials["dashboards_server"],
        "opensearch.requestHeadersAllowlist": ["securitytenant", "Authorization"],
        "opensearch_security.multitenancy.enabled": True,
        "opensearch_security.multitenancy.tenants.enable_global": True,
        "opensearch_security.multitenancy.tenants.enable_private": False,
        "opensearch_security.multitenancy.tenants.preferred": ["team_a", "team_b"],
        "opensearch_security.readonly_mode.roles": ["demo_user1", "demo_user2"],
        "opensearch_security.cookie.secure": False,
        "home.disableWelcomeScreen": True,
        "home.disableNewThemeModal": True,
    })


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


def host_request(base, method, path, body=None, user=None, tenant=None, extra_headers=None):
    """Call loopback endpoints with generated credentials kept out of command arguments."""
    headers = {"Content-Type": "application/json", "osd-xsrf": "permissions-demo"}
    if user:
        credentials = json.loads((STATE / "credentials.json").read_text())
        headers["Authorization"] = "Basic " + base64.b64encode((user + ":" + credentials.get(user, "invalid")).encode()).decode()
    if tenant:
        headers["securitytenant"] = tenant
    if extra_headers:
        headers.update(extra_headers)
    data = None if body is None else (body if isinstance(body, str) else json.dumps(body)).encode()
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        response = urllib.request.urlopen(request, timeout=40)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        payload = response.read()
        try:
            value = json.loads(payload)
        except ValueError:
            value = {"message": payload[:200].decode(errors="replace")}
        return response.status, value


def kaldb_request(port, method, path, body=None, content_type="application/json"):
    """Use the private setup interface; its ports are never published."""
    config = ["url = " + json.dumps(f"http://localhost:{port}" + path), "request = " + json.dumps(method),
              'max-time = "30"', "header = " + json.dumps("content-type: " + content_type)]
    if body is not None:
        config.append("data-binary = " + json.dumps(body if isinstance(body, str) else json.dumps(body)))
    result = compose("exec", "-T", "kaldb", "curl", "-sS", "--config", "-", "-w", "\n%{http_code}",
                     input="\n".join(config) + "\n", text=True, capture_output=True)
    payload, status = result.stdout.rsplit("\n", 1)
    try:
        result = json.loads(payload) if payload else {}
    except ValueError:
        result = {"message": payload[:200]}
    return int(status), result


def recorder_calls():
    """Read the recorder's control interface from its private network namespace."""
    command = "import urllib.request; print(urllib.request.urlopen('http://recorder-control:8089/__test__/calls').read().decode())"
    return json.loads(compose("exec", "-T", "recorder", "python", "-c", command, capture_output=True, text=True).stdout)


def wait_ready(label, request, attempts=90):
    """Wait for a real success without treating transient errors as readiness."""
    for _ in range(attempts):
        try:
            status, _ = request()
            if status == 200:
                print(label + " ready", flush=True)
                return
        except (OSError, subprocess.CalledProcessError, ValueError):
            pass
        time.sleep(2)
    raise RuntimeError(label + " did not become ready; inspect this isolated project's logs")


def build_runtime(kaldb_home, skip_build):
    """Build from the selected KalDB checkout and package only runtime artifacts."""
    source = Path(kaldb_home).resolve()
    if not (source / "contrib/dashboards-gateway/src/main/java/com/slack/astra/contrib/dashboardsgateway/GatewayAuthorization.java").is_file():
        raise RuntimeError("--kaldb-home must point to the KalDB permissions branch")
    if not skip_build:
        for arguments in (["-pl", "astra", "-am", "-DskipTests", "package"],
                          ["-f", "contrib/dashboards-gateway/pom.xml", "-DskipTests", "package"]):
            with (STATE / "runtime-build.log").open("a") as log:
                subprocess.run(["mvn", "-q", *arguments], cwd=source, stdout=log, stderr=subprocess.STDOUT, check=True)
    runtime = STATE / "runtime"
    runtime.mkdir(exist_ok=True)
    with zipfile.ZipFile(source / "contrib/dashboards-gateway/target/tools-dashboards-gateway.jar") as archive:
        if "com/slack/astra/contrib/dashboardsgateway/GatewayAuthorization.class" not in archive.namelist():
            raise RuntimeError("Selected gateway jar lacks secured mode; rebuild the permissions branch")
    for origin, target in [("astra/target/astra.jar", "astra.jar"),
                           ("contrib/dashboards-gateway/target/tools-dashboards-gateway.jar", "gateway.jar"),
                           ("config/config.yaml", "config.yaml")]:
        shutil.copyfile(source / origin, runtime / target)
    fields = {"body": "TEXT", "secret": "KEYWORD", "level": "KEYWORD", "duration_ms": "LONG"}
    write_json(runtime / "ingest-schema.json", {"fields": {key: {"type": kind} for key, kind in fields.items()}})
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    write_json(runtime / "build.json", {"source": str(source), "revision": revision, "opensearch": "2.11.1"})
    compose("build", "kaldb")


def seed_kaldb():
    """Register two datasets and ingest distinct synthetic records into actual KalDB."""
    rpc_prefix = "/slack.proto.astra.ManagerApiService/"
    rpc_type = "application/json; charset=utf-8; protocol=gRPC"
    wait_ready("KalDB manager", lambda: kaldb_request(8083, "POST", rpc_prefix + "ListDatasetMetadata", {}, rpc_type))
    status, catalog = kaldb_request(8083, "POST", rpc_prefix + "ListPartitionMetadata", {}, rpc_type)
    if status != 200:
        raise RuntimeError(f"Partition listing failed: HTTP {status}")
    if not any(item.get("partitionId") == "0" for item in catalog.get("partitionMetadata", [])):
        status, _ = kaldb_request(8083, "POST", rpc_prefix + "CreatePartition", {"partitionId": "0", "maxCapacity": "2000000000"}, rpc_type)
        if status != 200:
            raise RuntimeError(f"Partition creation failed: HTTP {status}")
    status, catalog = kaldb_request(8083, "POST", rpc_prefix + "ListDatasetMetadata", {}, rpc_type)
    if status != 200:
        raise RuntimeError(f"Dataset listing failed: HTTP {status}")
    existing = {item["name"] for item in catalog.get("datasetMetadata", [])}
    for name in DATASETS:
        body = {"name": name, "owner": "permissions-demo@localhost", "serviceNamePattern": name}
        if name not in existing:
            status, _ = kaldb_request(8083, "POST", rpc_prefix + "CreateDatasetMetadata", body, rpc_type)
            if status != 200:
                raise RuntimeError(f"Dataset creation failed: HTTP {status}")
        status, _ = kaldb_request(8083, "POST", rpc_prefix + "UpdatePartitionAssignment",
                                  {"name": name, "throughputBytes": "10000000", "partitionIds": ["0"]}, rpc_type)
        if status != 200:
            raise RuntimeError(f"Dataset assignment failed: HTTP {status}")
    wait_ready("KalDB bulk ingestion", lambda: kaldb_request(8086, "GET", "/health"))
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    for group, dataset in zip(("A", "B"), DATASETS):
        records = []
        for i in range(3):
            records.extend([{"index": {"_index": dataset, "_id": f"permissions-{group}-{i}"}}, {
                "@timestamp": timestamp, "body": f"TEAM_{group}_ORDER_READY_{i}", "level": "INFO",
                "duration_ms": 10 + i, "secret": f"PRIVATE_{group}_SENTINEL",
                "customer": {"region": "us-west" if group == "A" else "us-east", "email": f"private-{group.lower()}@example.invalid"},
                "events": {"code": "READY", "secret": f"NESTED_PRIVATE_{group}"},
            }])
        ndjson = "\n".join(json.dumps(record) for record in records) + "\n"
        status, response = kaldb_request(8086, "POST", "/_bulk", ndjson, "application/x-ndjson")
        if status != 200 or response.get("errors"):
            raise RuntimeError(f"KalDB fixture ingestion failed: HTTP {status}")
    for user, dataset in (("user1", DATASETS[0]), ("user2", DATASETS[1])):
        def fixture_ready():
            status, result = host_request(GATEWAY_URL, "POST", "/" + dataset + "/_search", {"size": 10, "query": {"match_all": {}}}, user)
            if status == 200 and len(result.get("hits", {}).get("hits", [])) >= 3:
                return 200, result
            return 503, {}
        wait_ready(user + " actual KalDB records", fixture_ready)


def seed_dashboards():
    """Create each dashboard inside its own real Security tenant."""
    wait_ready("Dashboards", lambda: host_request(DASHBOARDS_URL, "GET", "/api/status", user="admin"))
    def tenant_template_ready():
        status, response = native_request("GET", "/_index_template/tenant_template")
        templates = response.get("index_templates", [])
        mappings = templates[0].get("index_template", {}).get("template", {}).get("mappings", {}) if templates else {}
        return (200 if status == 200 and mappings.get("properties", {}).get("type", {}).get("type") == "keyword" else 503), {}
    wait_ready("Native tenant saved-object template", tenant_template_ready)
    for user, dataset, tenant, group in (("user1", DATASETS[0], "team_a", "A"), ("user2", DATASETS[1], "team_b", "B")):
        pattern_id, search_id, metric_id, dashboard_id = [f"security-{user}-{kind}" for kind in ("index", "search", "metric", "dashboard")]
        status, caps = native_request("GET", "/" + dataset + "/_field_caps?fields=*", user=user)
        if status != 200:
            raise RuntimeError("Cannot obtain user's native dashboard fields")
        fields = []
        for name, definitions in caps["fields"].items():
            if name.startswith("_") or "object" in definitions or "nested" in definitions:
                continue
            kind, capability = next(iter(definitions.items()))
            display_type = "date" if kind == "date" else "number" if kind in ("long", "integer", "double") else "string"
            fields.append({"name": name, "type": display_type, "esTypes": [kind], "count": 0,
                           "scripted": False, "searchable": capability["searchable"], "aggregatable": capability["aggregatable"],
                           "readFromDocValues": capability["aggregatable"]})
        index_ref = [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": pattern_id}]
        search_source = json.dumps({"indexRefName": index_ref[0]["name"], "query": {"language": "kuery", "query": ""}, "filter": []})
        objects = [
            ("index-pattern", pattern_id, {"title": dataset, "timeFieldName": "@timestamp", "fields": json.dumps(fields)}, []),
            ("search", search_id, {"title": f"Team {group} records", "columns": ["body", "level", "customer.region"],
                                   "sort": [["@timestamp", "desc"]], "kibanaSavedObjectMeta": {"searchSourceJSON": search_source}}, index_ref),
            ("visualization", metric_id, {"title": f"Team {group} max duration", "visState": json.dumps({"title": "Max duration", "type": "metric",
                "params": {"fontSize": 60}, "aggs": [{"id": "1", "enabled": True, "type": "max", "schema": "metric", "params": {"field": "duration_ms", "customLabel": "Max duration (ms)"}}]}),
                "uiStateJSON": "{}", "kibanaSavedObjectMeta": {"searchSourceJSON": search_source}}, index_ref),
        ]
        panels = [{"version": "2.11.1", "type": kind, "panelRefName": f"panel_{i}", "panelIndex": str(i),
                   "embeddableConfig": {}, "gridData": {"x": 0, "y": i * 8, "w": 48, "h": 8 if i == 0 else 16, "i": str(i)}}
                  for i, kind in enumerate(("visualization", "search"))]
        objects.append(("dashboard", dashboard_id, {"title": f"Team {group} — Security demo", "description": f"Only {user} can access this tenant and {dataset}",
            "panelsJSON": json.dumps(panels), "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
            "timeRestore": True, "timeFrom": "now-24h", "timeTo": "now", "version": 1,
            "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"language": "kuery", "query": ""}, "filter": []})}},
            [{"name": "panel_0", "type": "visualization", "id": metric_id}, {"name": "panel_1", "type": "search", "id": search_id}]))
        for kind, object_id, attributes, references in objects:
            status, _ = host_request(DASHBOARDS_URL, "POST", f"/api/saved_objects/{kind}/{object_id}?overwrite=true",
                                     {"attributes": attributes, "references": references}, "admin", tenant)
            if status != 200:
                raise RuntimeError(f"Saved object {kind} creation failed: HTTP {status}")
        status, found = host_request(DASHBOARDS_URL, "GET", "/api/saved_objects/_find?type=index-pattern&per_page=100", user=user, tenant=tenant)
        if status != 200 or not any(item.get("id") == pattern_id for item in found.get("saved_objects", [])):
            raise RuntimeError("Tenant index pattern is not searchable; inspect native saved-object migrations before using the demo")
        status, _ = host_request(DASHBOARDS_URL, "POST", "/api/opensearch-dashboards/settings",
                                 {"changes": {"defaultIndex": pattern_id}}, "admin", tenant)
        if status != 200:
            raise RuntimeError(f"Tenant default index setup failed: HTTP {status}")
        print(f"{user}: {DASHBOARDS_URL}/app/dashboards?security_tenant={tenant}#/view/{dashboard_id}", flush=True)


def set_permissions(user, access="own", tenant_access="own"):
    """Apply a preset to the real native role for one of the two showcase users."""
    if user not in ("user1", "user2") or access not in ("own", "none", "both") or tenant_access not in ("own", "none", "both"):
        raise ValueError("Unknown demo-owned permission preset")
    role_name = "demo_" + user
    role = json.loads((STATE / "security/roles.yml").read_text())[role_name]
    if access == "none":
        role["index_permissions"] = []
    elif access == "both":
        role["index_permissions"][0]["index_patterns"] = list(DATASETS)
    if tenant_access == "none":
        role["tenant_permissions"] = []
    elif tenant_access == "both":
        role["tenant_permissions"][0]["tenant_patterns"] = ["team_a", "team_b"]
    status, _ = native_request("PUT", "/_plugins/_security/api/roles/" + role_name, role)
    if status not in (200, 201):
        raise RuntimeError(f"Native role update failed: HTTP {status}")
    print(f"Updated {role_name}: index access={access}, dashboard tenant access={tenant_access}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["native-start", "native-stop", "start", "stop", "status", "permissions", "showcase"])
    parser.add_argument("--kaldb-home", default=os.environ.get("KALDB_HOME"))
    parser.add_argument("--skip-build", action="store_true", help="Reuse existing jars from the selected KalDB checkout")
    parser.add_argument("--user", choices=["user1", "user2"], default="user1")
    parser.add_argument("--access", choices=["own", "none", "both"], default="own")
    parser.add_argument("--tenant-access", choices=["own", "none", "both"], default="own")
    parser.add_argument("--unsafe-multifields", action="store_true",
                        help="Reproduce the rejected multi-field oracle on fresh native indexes")
    args = parser.parse_args()
    if args.action in ("native-stop", "stop"):
        compose("down")
    elif args.action == "status":
        compose("ps")
    elif args.action == "permissions":
        set_permissions(args.user, args.access, args.tenant_access)
    elif args.action == "showcase":
        from verify import api_checks
        api_checks()
        for user, tenant in (("user1", "team_a"), ("user2", "team_b")):
            print(f"Log in as {user}: {DASHBOARDS_URL}/app/dashboards?security_tenant={tenant}#/view/security-{user}-dashboard")
        print("Login values are in local/kaldb/permissions/.state/credentials.json")
    elif args.action in ("native-start", "start"):
        prepare_state()
        if args.action == "start":
            if not args.kaldb_home:
                raise SystemExit("Provide --kaldb-home pointing to the KalDB permissions branch")
            build_runtime(args.kaldb_home, args.skip_build)
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
        if args.action == "start":
            compose("up", "-d")
            wait_ready("Secured Java gateway", lambda: host_request(GATEWAY_URL, "GET", "/_astra/gateway/health"))
            status, _ = host_request(GATEWAY_URL, "POST", "/" + DATASETS[0] + "/_search", {"query": {"match_none": {}}})
            if status != 401:
                raise RuntimeError("Gateway did not enforce authentication; refusing fixture setup")
            seed_kaldb()
            seed_dashboards()


if __name__ == "__main__":
    main()
