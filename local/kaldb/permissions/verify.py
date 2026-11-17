#!/usr/bin/env python3
"""Verify real native policies and the KalDB permissions demo without logging secrets."""

import argparse
import json
import subprocess
import time
import urllib.parse


def ui_checks():
    """Verify isolated real logins, rendered KalDB rows, and Dashboards-mediated denials."""
    from demo import DATASETS, STATE, GATEWAY_URL, DASHBOARDS_URL, host_request, native_request, recorder_calls, wait_ready
    from selenium import webdriver
    from selenium.common.exceptions import ElementClickInterceptedException, StaleElementReferenceException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    wait_ready("Dashboards UI", lambda: host_request(DASHBOARDS_URL, "GET", "/api/status", user="admin"))
    credentials = json.loads((STATE / "credentials.json").read_text())
    screenshots = STATE / "screenshots"
    screenshots.mkdir(exist_ok=True)
    evidence = []

    def driver_for(user):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1600,1200")
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(90)
        driver.set_script_timeout(45)
        try:
            driver.get(DASHBOARDS_URL + "/")
            wait = WebDriverWait(driver, 60)
            wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, '[data-test-subj="user-name"]'))
            driver.find_element(By.CSS_SELECTOR, '[data-test-subj="user-name"]').send_keys(user)
            driver.find_element(By.CSS_SELECTOR, '[data-test-subj="password"]').send_keys(credentials[user])
            driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
            wait.until(lambda d: urllib.parse.urlparse(d.current_url).path != "/app/login")
            def confirm_tenant(d):
                try:
                    for element in d.find_elements(By.XPATH, "//button[normalize-space()='Explore on my own'] | //a[normalize-space()='Explore on my own']"):
                        if element.is_displayed():
                            element.click()
                            return False
                    for element in d.find_elements(By.CSS_SELECTOR, '[data-test-subj="confirm"]'):
                        if element.is_displayed() and element.is_enabled():
                            element.click()
                            return True
                except (ElementClickInterceptedException, StaleElementReferenceException):
                    return False
                return False
            tenant_document = driver.find_element(By.TAG_NAME, "body")
            wait.until(confirm_tenant)
            wait.until(EC.staleness_of(tenant_document))
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
            wait.until(lambda d: "Select your tenant" not in d.find_element(By.TAG_NAME, "body").text)
            print("PASS UI " + user + " login and tenant selection", flush=True)
            return driver
        except Exception:
            driver.save_screenshot(str(screenshots / (user + "-login-failure.png")))
            driver.quit()
            raise

    def fetch(driver, path, method="GET", body=None, tenant=None):
        headers = {"osd-xsrf": "permissions-demo", "content-type": "application/json"}
        if tenant:
            headers["securitytenant"] = tenant
        options = {"method": method, "headers": headers}
        if body is not None:
            options["body"] = json.dumps(body)
        return driver.execute_async_script("""
            const done = arguments[arguments.length - 1];
            fetch(arguments[0], arguments[1]).then(async r => done({status:r.status, text:await r.text()}))
              .catch(() => done({status:0, text:'request failed'}));
            """, path, options)

    def console_path(path, method):
        return "/api/console/proxy?" + urllib.parse.urlencode({"path": path, "method": method})

    for user, dataset, other, tenant, other_tenant, marker, title, other_title in (
        ("user1", DATASETS[0], DATASETS[1], "team_a", "team_b", "TEAM_A_ORDER_READY", "Team A", "Team B"),
        ("user2", DATASETS[1], DATASETS[0], "team_b", "team_a", "TEAM_B_ORDER_READY", "Team B", "Team A"),
    ):
        driver = driver_for(user)
        try:
            driver.get(f"{DASHBOARDS_URL}/app/dashboards?security_tenant={tenant}#/view/security-{user}-dashboard")
            wait = WebDriverWait(driver, 90)
            wait.until(lambda d: marker in d.find_element(By.TAG_NAME, "body").text)
            wait.until(lambda d: "Max duration (ms)" in d.find_element(By.TAG_NAME, "body").text)
            text = driver.find_element(By.TAG_NAME, "body").text
            require("\nError\n" not in text, user + " dashboard contains a failed panel")
            require(other_title + " — Security demo" not in text, user + " rendered another dashboard")
            if user == "user2":
                require("PRIVATE_B_SENTINEL" not in text and "private-b@example.invalid" not in text, "User 2 dashboard leaked hidden values")
            driver.save_screenshot(str(screenshots / (user + "-dashboard.png")))
            print("PASS UI " + user + " rendered its own dashboard with actual KalDB records", flush=True)
            evidence.append({"user": user, "dashboard_rendered": True, "fixture_rendered": True})
            driver.get(f"{DASHBOARDS_URL}/app/dashboards?security_tenant={tenant}#/list")
            wait.until(lambda d: title + " — Security demo" in d.find_element(By.TAG_NAME, "body").text)
            require(other_title + " — Security demo" not in driver.find_element(By.TAG_NAME, "body").text,
                    user + " dashboard list exposed another tenant")
            driver.save_screenshot(str(screenshots / (user + "-dashboard-list.png")))
            # Stop dashboard background searches before comparing recorder counters.
            driver.get(DASHBOARDS_URL + "/status")
            time.sleep(0.5)
            own = fetch(driver, console_path(dataset + "/_search", "POST"), "POST", {"size": 10}, tenant)
            require(own["status"] == 200 and marker in own["text"], user + " Dev Tools positive control failed")
            before = recorder_calls()["count"]
            denied = fetch(driver, console_path(other + "/_search", "POST"), "POST", {}, tenant)
            delta = recorder_calls()["count"] - before
            require(denied["status"] == 403 and delta == 0, user + " cross-index Dashboards request reached KalDB")
            print("PASS UI " + user + " other-index denial: HTTP 403, KalDB calls +0", flush=True)
            if user == "user2":
                before = recorder_calls()["count"]
                denied = fetch(driver, console_path(dataset + "/_search", "POST"), "POST",
                               {"query": {"term": {"secret": "PRIVATE_B_SENTINEL"}}}, tenant)
                require(denied["status"] == 403 and recorder_calls()["count"] == before, "Dashboards forbidden-field request reached KalDB")
                print("PASS UI user2 forbidden-field denial: HTTP 403, KalDB calls +0", flush=True)
            other_id = "security-user2-dashboard" if user == "user1" else "security-user1-dashboard"
            denied = fetch(driver, "/api/saved_objects/dashboard/" + other_id, tenant=tenant)
            require(denied["status"] == 404, user + " retrieved another tenant's dashboard")
            denied = fetch(driver, "/api/saved_objects/dashboard/" + other_id + "?security_tenant=" + other_tenant)
            require(denied["status"] in (403, 404), user + " forged another dashboard tenant")
            print("PASS UI " + user + " other dashboard and tenant are inaccessible", flush=True)
        except Exception:
            driver.save_screenshot(str(screenshots / (user + "-failure.png")))
            (STATE / (user + "-failure.txt")).write_text(driver.find_element(By.TAG_NAME, "body").text)
            raise
        finally:
            driver.quit()

    # Apply and restore a real Security role through the logged-in Dashboards Dev Tools API.
    status, roles = native_request("GET", "/_plugins/_security/api/roles/demo_user1")
    require(status == 200, "Cannot snapshot UI role change")
    original = {key: roles["demo_user1"].get(key, []) for key in ("cluster_permissions", "index_permissions", "tenant_permissions")}
    admin = driver_for("admin")
    try:
        admin.get(DASHBOARDS_URL + "/app/dev_tools")
        WebDriverWait(admin, 60).until(lambda d: "Console" in d.find_element(By.TAG_NAME, "body").text)
        modified = json.loads(json.dumps(original)); modified["index_permissions"] = []
        update = fetch(admin, console_path("_plugins/_security/api/roles/demo_user1", "PUT"), "POST", modified, "team_a")
        require(update["status"] in (200, 201), "Dashboards role update failed")
        before = recorder_calls()["count"]
        status, _ = host_request(GATEWAY_URL, "POST", "/" + DATASETS[0] + "/_search", {}, "user1")
        require(status == 403 and recorder_calls()["count"] == before, "Dashboards role update did not revoke the next request")
        print("PASS UI admin changed native permissions through Dashboards; next user request denied with +0 KalDB calls", flush=True)
    finally:
        try:
            try:
                restored = fetch(admin, console_path("_plugins/_security/api/roles/demo_user1", "PUT"), "POST", original, "team_a")["status"]
            except Exception:
                restored = 0
            if restored not in (200, 201):
                restored, _ = native_request("PUT", "/_plugins/_security/api/roles/demo_user1", original)
            require(restored in (200, 201), "Could not restore UI-modified role")
        finally:
            admin.quit()
    (STATE / "ui-report.json").write_text(json.dumps(evidence, indent=2))
    print("PASS two-user Dashboards UI verification; screenshots in local/kaldb/permissions/.state/screenshots", flush=True)


def api_checks():
    """Exercise real native policy, real KalDB data, and zero-call denials."""
    from demo import DATASETS, STATE, GATEWAY_URL, DASHBOARDS_URL, host_request, native_request, recorder_calls, compose, wait_ready
    public, private = DATASETS
    evidence = []

    def result(name, status, delta=None):
        evidence.append({"case": name, "status": status, "kaldb_calls": delta})
        print(f"PASS {name}: HTTP {status}" + (f", KalDB calls +{delta}" if delta is not None else ""), flush=True)

    def denied(name, user, path, body=None, expected=403, extra_headers=None):
        before = recorder_calls()["count"]
        status, response = host_request(GATEWAY_URL, "POST", path, body, user, extra_headers=extra_headers)
        delta = recorder_calls()["count"] - before
        require(status == expected, f"{name}: expected HTTP {expected}, got {status}")
        require(delta == 0, f"{name}: rejected request reached KalDB ({delta} calls)")
        result(name, status, delta)
        return response

    for user, dataset, marker in (("user1", public, "TEAM_A_ORDER_READY"), ("user2", private, "TEAM_B_ORDER_READY")):
        before = recorder_calls()["count"]
        status, response = host_request(GATEWAY_URL, "POST", f"/{dataset}/_search", {"size": 10, "query": {"match_all": {}}}, user)
        delta = recorder_calls()["count"] - before
        text = json.dumps(response)
        require(status == 200 and marker in text and delta > 0, f"{user} positive control must return actual assigned KalDB fixtures")
        if user == "user2":
            require("PRIVATE_B_SENTINEL" not in text and "private-b@example.invalid" not in text and "NESTED_PRIVATE_B" not in text,
                    "User 2 FLS must remove private and nested values")
        result(user + " reads actual assigned fixtures", status, delta)
    status, response = host_request(GATEWAY_URL, "POST", f"/{private}/_search", {"size": 10}, "full_reader")
    require(status == 200 and "PRIVATE_B_SENTINEL" in json.dumps(response), "Full-reader private sentinel positive control failed")
    result("full reader sees actual private sentinel", status)
    denied("missing credentials", None, f"/{public}/_search", {}, 401)
    denied("invalid credentials", "invalid", f"/{public}/_search", {}, 401)
    denied("user 1 cannot read index B", "user1", f"/{private}/_search", {})
    denied("user 2 cannot read index A", "user2", f"/{public}/_search", {})
    denied("no-access account", "no_access", f"/{public}/_search", {})
    denied("forged identity headers", "user1", f"/{private}/_search", {}, extra_headers={"x-proxy-user": "admin", "_opendistro_security_user": "admin"})
    denied("native alias writes remain forbidden", "user1", "/_aliases", {"actions": [{"add": {"index": public, "alias": "should-not-exist"}}]})
    for label, body in (
        ("query", {"query": {"term": {"secret": "PRIVATE_B_SENTINEL"}}}),
        ("filter", {"query": {"bool": {"filter": [{"exists": {"field": "secret"}}]}}}),
        ("sort", {"sort": [{"secret": "asc"}]}),
        ("aggregation", {"aggs": {"values": {"terms": {"field": "secret"}}}}),
        ("source", {"_source": ["secret"]}),
        ("wildcard source", {"_source": ["customer.*"]}),
        ("nested source", {"_source": ["events.secret"]}),
        ("fields", {"fields": ["customer.email"]}),
        ("docvalues", {"docvalue_fields": ["secret"]}),
    ):
        denied("hidden field in " + label, "user2", f"/{private}/_search", body)
    mixed = "\n".join(json.dumps(item) for item in [
        {"index": public}, {"query": {"match_all": {}}}, {"index": private}, {"query": {"match_all": {}}}]) + "\n"
    denied("mixed-index multi-search is atomic", "user1", "/_msearch", mixed)
    for label, body in (("scripts", {"script_fields": {"x": {"script": "1"}}}), ("runtime fields", {"runtime_mappings": {}}),
                        ("unknown DSL", {"query": {"script": {}}})):
        denied(label, "user1", f"/{public}/_search", body, 400)
    denied("unregistered index", "user1", "/permissions-demo-missing/_search", {})
    denied("unsupported parent FLS policy", "parent_reader", f"/{public}/_search", {})
    for user, expected in (("user1", public), ("user2", private)):
        for path in ("/_resolve/index/permissions-demo-*", "/_mapping", "/_field_caps?fields=*"):
            status, response = host_request(GATEWAY_URL, "GET", path, user=user)
            require(status == 200 and expected in json.dumps(response), f"{user} metadata discovery failed")
            forbidden_index = private if user == "user1" else public
            require(forbidden_index not in json.dumps(response), f"{user} metadata exposed another index")
            if user == "user2":
                require("secret" not in json.dumps(response) and "customer.email" not in json.dumps(response), "Metadata exposed hidden fields")
        result(user + " metadata contains only assigned index and fields", 200)
    status, response = host_request(GATEWAY_URL, "POST", f"/{private}/_search",
                                  {"query": {"query_string": {"query": "PRIVATE_B_SENTINEL"}}}, "user2")
    require(status == 200 and not response.get("hits", {}).get("hits"), "Unfielded text matched a hidden value")
    result("hidden values cannot influence unfielded search hits", status)
    for user, term in (("full_reader", "PRIVATE_B_SENTINEL"), ("user2", "TEAM_B_ORDER_READY_0")):
        status, response = host_request(GATEWAY_URL, "POST", f"/{private}/_search",
                                      {"query": {"query_string": {"query": term}}}, user)
        require(status == 200 and response.get("hits", {}).get("hits"), user + " unfielded positive control failed")
        result(user + " unfielded visible value matches actual records", status)
    status, response = host_request(GATEWAY_URL, "POST", f"/{public}/_search", {
        "size": 0, "aggs": {"over_time": {"date_histogram": {"field": "@timestamp", "fixed_interval": "1h"}}}}, "user1")
    require(status == 200 and "aggregations" in response, "Visible date histogram failed on actual KalDB")
    result("visible date histogram", status)

    status, roles = native_request("GET", "/_plugins/_security/api/roles/demo_user1")
    require(status == 200, "Cannot snapshot demo-owned role")
    original = {key: roles["demo_user1"].get(key, []) for key in ("cluster_permissions", "index_permissions", "tenant_permissions")}
    try:
        modified = json.loads(json.dumps(original)); modified["index_permissions"] = []
        status, _ = native_request("PUT", "/_plugins/_security/api/roles/demo_user1", modified)
        require(status in (200, 201), "Role revocation failed")
        denied("completed index revocation affects next request", "user1", f"/{public}/_search", {})
    finally:
        status, _ = native_request("PUT", "/_plugins/_security/api/roles/demo_user1", original)
        require(status in (200, 201), "Could not restore demo-owned role")
    for key, value in (("dls", '{"match_all":{}}'), ("masked_fields", ["secret"])):
        try:
            modified = json.loads(json.dumps(original)); modified["index_permissions"][0][key] = value
            status, _ = native_request("PUT", "/_plugins/_security/api/roles/demo_user1", modified)
            require(status in (200, 201), "Unsupported-policy fixture update failed")
            denied("unsupported " + key + " fails closed", "user1", f"/{public}/_search", {})
        finally:
            status, _ = native_request("PUT", "/_plugins/_security/api/roles/demo_user1", original)
            require(status in (200, 201), "Could not restore unsupported-policy fixture")
    try:
        compose("stop", "opensearch", stdout=subprocess.DEVNULL)
        denied("native authority outage fails closed", "user1", f"/{public}/_search", {}, 503)
    finally:
        compose("start", "opensearch", stdout=subprocess.DEVNULL)
        wait_ready("Native authority restored", lambda: native_request("GET", "/_cluster/health"))

    for user, tenant, other_tenant, own_id, other_id in (
        ("user1", "team_a", "team_b", "security-user1-dashboard", "security-user2-dashboard"),
        ("user2", "team_b", "team_a", "security-user2-dashboard", "security-user1-dashboard"),
    ):
        status, _ = host_request(DASHBOARDS_URL, "GET", "/api/saved_objects/dashboard/" + own_id, user=user, tenant=tenant)
        require(status == 200, user + " cannot load its own saved dashboard")
        result(user + " own dashboard saved object", status)
        status, _ = host_request(DASHBOARDS_URL, "GET", "/api/saved_objects/dashboard/" + other_id, user=user, tenant=tenant)
        require(status == 404, user + " can see another tenant's saved dashboard")
        result(user + " other dashboard is absent", status)
        status, _ = host_request(DASHBOARDS_URL, "GET", "/api/saved_objects/dashboard/" + other_id, user=user, tenant=other_tenant)
        require(status in (403, 404), user + " could bypass dashboard isolation with a tenant header")
        result(user + " forged tenant cannot retrieve other dashboard", status)
    for service, port in (("kaldb", 8081), ("recorder", 8089)):
        container = compose("ps", "-q", service, capture_output=True, text=True).stdout.strip()
        networks = json.loads(subprocess.check_output(["docker", "inspect", container], text=True))[0]["NetworkSettings"]["Networks"]
        for address in {service, *(network["IPAddress"] for network in networks.values())}:
            probe = "const net=require('net');const s=net.connect(" + str(port) + "," + json.dumps(address) + ");s.on('connect',()=>process.exit(1));s.on('error',()=>process.exit(0));setTimeout(()=>process.exit(0),3000);"
            test = compose("exec", "-T", "dashboards", "/usr/share/opensearch-dashboards/node/bin/node", "-e", probe, stdout=subprocess.DEVNULL)
            require(test.returncode == 0, "User-facing container can bypass private " + service + " boundary")
        result("user-facing network cannot reach " + service + " by name or IP", 0)
    (STATE / "api-report.json").write_text(json.dumps(evidence, indent=2))
    print(f"PASS API security matrix ({len(evidence)} cases); report: local/kaldb/permissions/.state/api-report.json", flush=True)


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
    for user, own, other, tenant, other_tenant in (
        ("user1", public, private, "team_a", "team_b"),
        ("user2", private, public, "team_b", "team_a"),
    ):
        status, _ = client("POST", f"/{own}/_search", {"size": 0, "query": {"match_none": {}}}, user)
        check(status == 200, f"{user} can read only its assigned index (positive control)")
        status, _ = client("POST", f"/{other}/_search", {"size": 0}, user)
        check(status == 403, f"{user} cannot read the other index")
        status, identity = client("GET", "/_plugins/_security/authinfo", user=user)
        tenants = identity.get("tenants", {})
        check(status == 200 and tenant in tenants and other_tenant not in tenants,
              f"{user} has only its own dashboard tenant")
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
    elif args.mode == "api":
        api_checks()
    elif args.mode == "ui":
        ui_checks()
    elif args.mode == "all":
        native_checks(native_request)
        api_checks()
        ui_checks()
    else:
        raise SystemExit("API/UI verification is not implemented yet")


if __name__ == "__main__":
    main()
