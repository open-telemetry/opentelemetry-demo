"""Service dependency graph of the Astronomy Shop (from config/services.yaml)."""
import yaml

from agent import config

CFG = yaml.safe_load((config.ROOT / "config" / "services.yaml").read_text(encoding="utf-8"))
DEPS = CFG["dependencies"]
INFRA = set(CFG.get("infra", []))
APP_CONTAINERS = sorted(set(DEPS) | {c for cs in DEPS.values() for c in cs} - {"load-generator"})


def callees(svc: str) -> list:
    return list(DEPS.get(svc, []))


def callers(svc: str) -> list:
    return sorted(s for s, cs in DEPS.items() if svc in cs)


def descendants(svc: str, seen=None) -> set:
    seen = set() if seen is None else seen
    for c in DEPS.get(svc, []):
        if c not in seen:
            seen.add(c)
            descendants(c, seen)
    return seen


def ancestors(svc: str) -> set:
    return {s for s in DEPS if svc in descendants(s)}
