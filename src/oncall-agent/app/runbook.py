from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


RUNBOOK_PATH = Path(__file__).parent / "runbook.yaml"


class RunbookEntry(BaseModel):
    id: str
    description: str
    applies_to: dict[str, Any]
    action: str
    params: dict[str, Any]
    risk: str
    reason_template: str
    expected_recovery_signal: str
    rollback_action: str | None = None


def _load_runbooks() -> list[RunbookEntry]:
    with open(RUNBOOK_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [RunbookEntry(**r) for r in data.get("runbooks", [])]


RUNBOOKS: list[RunbookEntry] = _load_runbooks()


def find_matching_runbooks(
    cause_category: str,
    component: str,
) -> list[RunbookEntry]:
    """Return runbook entries that match the diagnosis, least-invasive first.

    Preference order: flag operations (set_feature_flag) before restarts.
    """
    comp_norm = component.lower().strip()
    cat_norm = cause_category.lower().strip()
    matches: list[RunbookEntry] = []

    for rb in RUNBOOKS:
        cat_list = [c.lower() for c in rb.applies_to.get("cause_categories", [])]
        hints = [h.lower() for h in rb.applies_to.get("component_hints", [])]

        cat_match = cat_norm in cat_list
        # Component hint match: either direct match, or hint appears in component name, or no hints at all
        if hints:
            comp_match = any(
                hint == comp_norm or hint in comp_norm or comp_norm in hint
                for hint in hints
            )
        else:
            comp_match = True

        if cat_match and comp_match:
            matches.append(rb)

    # Sort: flag operations first (low-risk), restart/throttle second
    def sort_key(rb: RunbookEntry) -> int:
        if rb.action == "set_feature_flag":
            return 0
        if rb.action == "throttle_load_generator":
            return 1
        return 2

    matches.sort(key=sort_key)
    return matches


def resolve_params(rb: RunbookEntry, component: str | dict[str, Any]) -> dict[str, Any]:
    """Resolve template variables in params (e.g. {component})."""
    comp_str = component if isinstance(component, str) else str(component.get("component", ""))
    resolved: dict[str, Any] = {}
    for k, v in rb.params.items():
        if isinstance(v, str):
            resolved[k] = v.replace("{component}", comp_str)
        else:
            resolved[k] = v
    return resolved
