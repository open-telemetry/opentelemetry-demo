import re
from pathlib import Path

from oncall.tools import REGISTRY, load_all

ONCALL = Path(__file__).resolve().parents[1]
BANNED = re.compile(r"flagd|feature_flag|ofrep|flag_?ctl", re.IGNORECASE)
READ_PATH = ("tools", "clients", "agent")


def test_only_guard_names_the_flag_service():
    offenders = []
    for path in (p for folder in READ_PATH for p in (ONCALL / folder).rglob("*.py")):
        if BANNED.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(ONCALL)))
    assert offenders == []


def test_no_tool_exposes_flags():
    load_all()
    names = [spec["function"]["name"] for spec in REGISTRY.openai_specs()]
    assert not any("flag" in name for name in names)
