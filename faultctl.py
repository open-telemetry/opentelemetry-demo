#!/usr/bin/env python3
"""faultctl - minimal practice-incident injector for the OpenTelemetry demo.

DEV/TEST TOOL ONLY. Keep it outside the agent package: the agent must never
import, call, or read this file or the flagd config (that is the answer key).

Usage (run from anywhere; point it at your demo checkout):
  export FAULTCTL_DEMO_DIR=~/opentelemetry-demo
  faultctl.py list
  faultctl.py inject cart-fail                 # preset
  faultctl.py inject --flag cartFailure --variant on
  faultctl.py inject --stop checkout           # container down
  faultctl.py inject --starve recommendation --cpus 0.2 --memory 100m
  faultctl.py status
  faultctl.py reset                            # restores everything

Env vars:
  FAULTCTL_DEMO_DIR      demo checkout (default: current dir)
  FAULTCTL_FLAGD_FILE    flag file relative to it (default: src/flagd/demo.flagd.json)
  FAULTCTL_COMPOSE_ARGS  extra args, e.g. "-f compose.yaml"
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

DEMO_DIR = Path(os.environ.get("FAULTCTL_DEMO_DIR", ".")).expanduser().resolve()
FLAGD_FILE = DEMO_DIR / os.environ.get("FAULTCTL_FLAGD_FILE", "src/flagd/demo.flagd.json")
COMPOSE = ["docker", "compose"] + shlex.split(os.environ.get("FAULTCTL_COMPOSE_ARGS", ""))
STATE = DEMO_DIR / ".faultctl_state.json"

# Flag names differ between demo versions, so each preset lists candidates;
# the first one that exists in your flag file is used.
PRESETS = {
    "payment-fail":        {"flag": ["paymentFailure", "paymentServiceFailure"], "variant": ["100%", "on"]},
    "payment-unreachable": {"flag": ["paymentUnreachable", "paymentServiceUnreachable"], "variant": ["on"]},
    "cart-fail":           {"flag": ["cartFailure", "cartServiceFailure"], "variant": ["on"]},
    "product-fail":        {"flag": ["productCatalogFailure"], "variant": ["on"]},
    "memory-leak":         {"flag": ["recommendationCacheFailure", "recommendationServiceCacheFailure"], "variant": ["on"]},
    "ad-fail":             {"flag": ["adFailure", "adServiceFailure"], "variant": ["on"]},
    "ad-cpu":              {"flag": ["adHighCpu", "adServiceHighCpu"], "variant": ["on"]},
    "ad-gc":               {"flag": ["adManualGc", "adServiceManualGc"], "variant": ["on"]},
    "traffic-flood":       {"flag": ["loadgeneratorFloodHomepage"], "variant": ["on"]},
    "kafka-lag":           {"flag": ["kafkaQueueProblems"], "variant": ["on"]},
    "cache-down":          {"stop": "valkey-cart"},   # confirm: docker compose config --services
    "db-down":             {"stop": "postgresql"},
}


def die(msg):
    sys.exit(f"faultctl: {msg}")


def dc(*args, capture=False):
    cmd = COMPOSE + list(args)
    if capture:
        return subprocess.check_output(cmd, cwd=DEMO_DIR).decode().strip()
    subprocess.run(cmd, cwd=DEMO_DIR, check=True)


def load_flags():
    if not FLAGD_FILE.exists():
        die(f"flag file not found: {FLAGD_FILE} (set FAULTCTL_DEMO_DIR / FAULTCTL_FLAGD_FILE)")
    return json.loads(FLAGD_FILE.read_text())


def save_flags(data):
    # Write in place (same inode) so Docker bind mounts keep seeing the file.
    with open(FLAGD_FILE, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"flags": {}, "stopped": [], "starved": []}


def save_state(st):
    STATE.write_text(json.dumps(st, indent=2))


def inject_flag(candidates, variants, restart_flagd=False):
    data = load_flags()
    flags = data["flags"]
    name = next((c for c in candidates if c in flags), None)
    if not name:
        die(f"none of {candidates} found. Available flags: {sorted(flags)}")
    options = flags[name].get("variants", {})
    variant = next((v for v in variants if v in options), None)
    if not variant:
        die(f"flag {name}: variants {variants} not found. Options: {list(options)}")
    if "targeting" in flags[name]:
        print(f"warning: {name} has targeting rules that may override defaultVariant; check it took effect")
    st = load_state()
    st["flags"].setdefault(name, flags[name]["defaultVariant"])  # remember original once
    flags[name]["defaultVariant"] = variant
    save_flags(data)
    save_state(st)
    if restart_flagd:
        dc("restart", "flagd")
    print(f"injected flag {name} = {variant}")


def inject_stop(service):
    dc("stop", service)
    st = load_state()
    if service not in st["stopped"]:
        st["stopped"].append(service)
    save_state(st)
    print(f"stopped service {service}")


def inject_starve(service, cpus, memory):
    cid = dc("ps", "-q", service, capture=True)
    if not cid:
        die(f"service {service} is not running")
    cmd = ["docker", "update"]
    if cpus:
        cmd += ["--cpus", str(cpus)]
    if memory:
        cmd += ["--memory", memory, "--memory-swap", memory]
    subprocess.run(cmd + [cid], check=True)
    st = load_state()
    if service not in st["starved"]:
        st["starved"].append(service)
    save_state(st)
    print(f"limited {service}: cpus={cpus} memory={memory}")


def reset(restart_flagd=False):
    st = load_state()
    if st["flags"]:
        data = load_flags()
        for name, original in st["flags"].items():
            if name in data["flags"]:
                data["flags"][name]["defaultVariant"] = original
        save_flags(data)
        print(f"restored flags: {', '.join(st['flags'])}")
    if st["stopped"]:
        dc("start", *st["stopped"])
        print(f"restarted: {', '.join(st['stopped'])}")
    if st["starved"]:
        dc("up", "-d", "--force-recreate", *st["starved"])  # drops docker-update limits
        print(f"recreated: {', '.join(st['starved'])}")
    if restart_flagd:
        dc("restart", "flagd")
    STATE.unlink(missing_ok=True)
    print("reset complete")


def status():
    st = load_state()
    print("active faults:", json.dumps(st, indent=2) if any(st.values()) else "none")


def main():
    p = argparse.ArgumentParser(description="Practice-incident injector (team dev tool)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="show presets")
    sub.add_parser("status", help="show faults this tool injected")
    r = sub.add_parser("reset", help="undo everything this tool injected")
    r.add_argument("--restart-flagd", action="store_true")
    i = sub.add_parser("inject", help="inject a fault")
    i.add_argument("preset", nargs="?", choices=sorted(PRESETS))
    i.add_argument("--flag")
    i.add_argument("--variant", default="on")
    i.add_argument("--stop", metavar="SERVICE")
    i.add_argument("--starve", metavar="SERVICE")
    i.add_argument("--cpus")
    i.add_argument("--memory")
    i.add_argument("--restart-flagd", action="store_true")
    a = p.parse_args()

    if a.cmd == "list":
        for n, spec in sorted(PRESETS.items()):
            print(f"{n:22} {spec.get('flag') or 'stop ' + spec['stop']}")
    elif a.cmd == "status":
        status()
    elif a.cmd == "reset":
        reset(a.restart_flagd)
    elif a.cmd == "inject":
        if a.preset:
            spec = PRESETS[a.preset]
            if "stop" in spec:
                inject_stop(spec["stop"])
            else:
                inject_flag(spec["flag"], spec["variant"], a.restart_flagd)
        elif a.flag:
            inject_flag([a.flag], [a.variant], a.restart_flagd)
        elif a.stop:
            inject_stop(a.stop)
        elif a.starve:
            if not (a.cpus or a.memory):
                die("--starve needs --cpus and/or --memory")
            inject_starve(a.starve, a.cpus, a.memory)
        else:
            die("give a preset, --flag, --stop or --starve")


if __name__ == "__main__":
    main()
