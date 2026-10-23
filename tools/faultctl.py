#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import httpx

INCIDENTS_CATALOG = [
    {"id": 1, "name": "paymentFailure=100%", "component": "payment", "type": "flag", "args": ["paymentFailure", "100%"], "expected_fix": "flag-off paymentFailure"},
    {"id": 2, "name": "cartFailure=50%", "component": "cart", "type": "flag", "args": ["cartFailure", "50%"], "expected_fix": "flag-off cartFailure"},
    {"id": 3, "name": "productCatalogFailure=on", "component": "product-catalog", "type": "flag", "args": ["productCatalogFailure", "on"], "expected_fix": "flag-off productCatalogFailure"},
    {"id": 4, "name": "recommendationCacheFailure=on", "component": "recommendation", "type": "flag", "args": ["recommendationCacheFailure", "on"], "expected_fix": "flag-off recommendationCacheFailure + restart"},
    {"id": 5, "name": "adHighCpu=on", "component": "ad", "type": "flag", "args": ["adHighCpu", "on"], "expected_fix": "flag-off adHighCpu"},
    {"id": 6, "name": "adManualGc=on", "component": "ad", "type": "flag", "args": ["adManualGc", "on"], "expected_fix": "flag-off adManualGc"},
    {"id": 7, "name": "loadGeneratorFloodHomepage=on", "component": "frontend", "type": "flag", "args": ["loadGeneratorFloodHomepage", "on"], "expected_fix": "throttle load"},
    {"id": 8, "name": "docker stop payment", "component": "payment", "type": "stop", "args": ["payment"], "expected_fix": "restart payment"},
    {"id": 9, "name": "docker stop valkey-cart", "component": "valkey-cart", "type": "stop", "args": ["valkey-cart"], "expected_fix": "restart valkey-cart"},
    {"id": 10, "name": "docker stop astronomy-db", "component": "astronomy-db", "type": "stop", "args": ["astronomy-db"], "expected_fix": "restart astronomy-db"},
    {"id": 11, "name": "starve-cpu ad 0.1", "component": "ad", "type": "starve-cpu", "args": ["ad", "0.1"], "expected_fix": "escalate (no approved fix)"},
    {"id": 12, "name": "emailMemoryLeak=100x", "component": "email", "type": "flag", "args": ["emailMemoryLeak", "100x"], "expected_fix": "flag-off emailMemoryLeak + restart"},
    {"id": 13, "name": "combo cartFailure=50% + adHighCpu=on", "component": "cart+ad", "type": "combo", "args": [], "expected_fix": "two actions, two rounds"},
    {"id": 14, "name": "no fault (negative control)", "component": "none", "type": "noop", "args": [], "expected_fix": "no alert, no action"},
    {"id": 15, "name": "kafkaQueueProblems=3sec", "component": "fraud-detection/kafka", "type": "flag", "args": ["kafkaQueueProblems", "3sec"], "expected_fix": "correct diagnosis or escalate"},
]


def _get_flagd_ui_url() -> str:
    if os.environ.get("FLAGD_UI_URL"):
        return os.environ["FLAGD_UI_URL"]
    try:
        out = subprocess.check_output(["docker", "port", "flagd-ui", "4000"], text=True)
        for line in out.strip().splitlines():
            parts = line.strip().split(":")
            if len(parts) >= 2:
                port = parts[-1]
                return f"http://localhost:{port}"
    except Exception:
        pass
    return "http://localhost:4000"


def _get_locust_url() -> str:
    if os.environ.get("LOAD_GENERATOR_URL"):
        return os.environ["LOAD_GENERATOR_URL"]
    try:
        out = subprocess.check_output(["docker", "port", "load-generator", "8089"], text=True)
        for line in out.strip().splitlines():
            parts = line.strip().split(":")
            if len(parts) >= 2:
                port = parts[-1]
                return f"http://localhost:{port}"
    except Exception:
        pass
    return "http://localhost:8089"


def set_flag(name: str, variant: str) -> None:
    base = _get_flagd_ui_url()
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(f"{base}/api/read-file")
        if resp.status_code != 200:
            print(f"Error reading flags: HTTP {resp.status_code}")
            sys.exit(1)
        data = resp.json()

    flags = data.get("flags", {})
    if name not in flags:
        print(f"Error: flag '{name}' not found in flags file")
        sys.exit(1)

    flag_obj = flags[name]
    variants = flag_obj.get("variants", {})
    if variant not in variants and variant != "off":
        print(f"Warning: variant '{variant}' not in variants {list(variants.keys())}")

    flag_obj["defaultVariant"] = variant

    if name == "productCatalogFailure" and "targeting" in flag_obj:
        flag_obj["targeting"]["if"][1] = "on" if variant != "off" else "off"

    with httpx.Client(timeout=10.0) as client:
        w_resp = client.post(f"{base}/api/write-to-file", json={"data": data})
        if w_resp.status_code != 200:
            print(f"Error writing flags: HTTP {w_resp.status_code}")
            sys.exit(1)

    print(f"Injected flag: {name} = {variant}")


def stop_service(service: str) -> None:
    print(f"Stopping service '{service}' via docker stop...")
    subprocess.check_call(["docker", "stop", service])
    print(f"Service '{service}' stopped.")


def pause_service(service: str) -> None:
    print(f"Pausing service '{service}' via docker pause...")
    subprocess.check_call(["docker", "pause", service])
    print(f"Service '{service}' paused.")


def unpause_service(service: str) -> None:
    print(f"Unpausing service '{service}' via docker unpause...")
    subprocess.check_call(["docker", "unpause", service])
    print(f"Service '{service}' unpaused.")


def starve_cpu(service: str, cpus: str) -> None:
    print(f"Limiting CPU for '{service}' to {cpus} cpus...")
    subprocess.check_call(["docker", "update", "--cpus", str(cpus), service])
    print(f"Service '{service}' CPU limit set to {cpus}.")


def starve_mem(service: str, mb: str) -> None:
    print(f"Limiting memory for '{service}' to {mb}M...")
    subprocess.check_call(["docker", "update", "-m", f"{mb}M", "--memory-swap", f"{mb}M", service])
    print(f"Service '{service}' memory limit set to {mb}M.")


def reset_all() -> None:
    print("Resetting all failure injections to clean baseline...")

    # 1. Unpause any paused containers
    try:
        paused = subprocess.check_output(
            ["docker", "ps", "-q", "--filter", "status=paused"],
            text=True,
        ).strip().split()
        for cid in paused:
            subprocess.run(["docker", "unpause", cid], check=False)
    except Exception:
        pass

    # 2. Restart stopped containers
    try:
        exited = subprocess.check_output(
            ["docker", "ps", "-a", "-q", "--filter", "status=exited"],
            text=True,
        ).strip().split()
        for cid in exited:
            subprocess.run(["docker", "start", cid], check=False)
    except Exception:
        pass

    # 3. Reset all flags to default "off" via flagd-ui
    try:
        base = _get_flagd_ui_url()
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{base}/api/read-file")
            if resp.status_code == 200:
                data = resp.json()
                for fname, fval in data.get("flags", {}).items():
                    fval["defaultVariant"] = "off"
                    if "targeting" in fval:
                        fval["targeting"]["if"][1] = "off"
                        fval["targeting"]["if"][2] = "off"
                client.post(f"{base}/api/write-to-file", json={"data": data})
    except Exception as e:
        print(f"Note: error resetting flags via flagd-ui: {e}")

    # 4. Restore git clean state for demo.flagd.json (Hard Rule 6)
    try:
        subprocess.run(["git", "checkout", "--", "src/flagd/demo.flagd.json"], check=False)
    except Exception:
        pass

    # 5. Restore Locust users to 5
    try:
        locust_url = _get_locust_url()
        with httpx.Client(timeout=5.0) as client:
            client.post(f"{locust_url}/swarm", data={"user_count": 5, "spawn_rate": 1.0})
    except Exception:
        pass

    # 6. Reset CPU and memory limits for ad container if starved
    try:
        subprocess.run(["docker", "update", "--cpus", "0", "-m", "300M", "--memory-swap", "300M", "ad"], check=False)
    except Exception:
        pass

    print("All faults successfully reset. System returned to clean baseline.")


def list_incidents() -> None:
    print(f"{'#':3} | {'Injection':35} | {'Component':18} | {'Expected Fix'}")
    print("-" * 85)
    for inc in INCIDENTS_CATALOG:
        print(f"{inc['id']:3} | {inc['name']:35} | {inc['component']:18} | {inc['expected_fix']}")


def inject_incident(inc_id: int) -> None:
    matched = next((inc for inc in INCIDENTS_CATALOG if inc["id"] == inc_id), None)
    if not matched:
        print(f"Error: Incident #{inc_id} not found in catalog.")
        sys.exit(1)

    print(f"Injecting Incident #{matched['id']}: {matched['name']}")
    itype = matched["type"]
    args = matched["args"]

    if itype == "flag":
        set_flag(args[0], args[1])
    elif itype == "stop":
        stop_service(args[0])
    elif itype == "pause":
        pause_service(args[0])
    elif itype == "starve-cpu":
        starve_cpu(args[0], args[1])
    elif itype == "combo":
        set_flag("cartFailure", "50%")
        set_flag("adHighCpu", "on")
    elif itype == "noop":
        print("Negative control: no fault injected.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test-only fault injector for OpenTelemetry Demo oncall evaluation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # flag
    flag_parser = subparsers.add_parser("flag", help="Set a feature flag variant")
    flag_parser.add_argument("name", help="Flag name")
    flag_parser.add_argument("variant", help="Variant value (e.g. 100%, 50%, on, off)")

    # stop
    stop_parser = subparsers.add_parser("stop", help="Stop a service container")
    stop_parser.add_argument("service", help="Service container name")

    # pause / unpause
    pause_parser = subparsers.add_parser("pause", help="Pause a service container")
    pause_parser.add_argument("service", help="Service container name")

    unpause_parser = subparsers.add_parser("unpause", help="Unpause a service container")
    unpause_parser.add_argument("service", help="Service container name")

    # starve-cpu
    cpu_parser = subparsers.add_parser("starve-cpu", help="Throttle container CPU limit")
    cpu_parser.add_argument("service", help="Service container name")
    cpu_parser.add_argument("cpus", help="CPU quota (e.g. 0.1)")

    # starve-mem
    mem_parser = subparsers.add_parser("starve-mem", help="Throttle container memory limit")
    mem_parser.add_argument("service", help="Service container name")
    mem_parser.add_argument("mb", help="Memory in MB (e.g. 50)")

    # reset
    subparsers.add_parser("reset", help="Reset all injected faults to clean baseline")

    # list
    subparsers.add_parser("list", help="List practice incident catalog")

    # inject
    inj_parser = subparsers.add_parser("inject", help="Inject a specific incident by ID (#1 to #15)")
    inj_parser.add_argument("id", type=int, help="Incident ID number (1-15)")

    args = parser.parse_args()

    if args.command == "flag":
        set_flag(args.name, args.variant)
    elif args.command == "stop":
        stop_service(args.service)
    elif args.command == "pause":
        pause_service(args.service)
    elif args.command == "unpause":
        unpause_service(args.service)
    elif args.command == "starve-cpu":
        starve_cpu(args.service, args.cpus)
    elif args.command == "starve-mem":
        starve_mem(args.service, args.mb)
    elif args.command == "reset":
        reset_all()
    elif args.command == "list":
        list_incidents()
    elif args.command == "inject":
        inject_incident(args.id)


if __name__ == "__main__":
    main()
