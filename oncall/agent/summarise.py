from __future__ import annotations

from typing import Any

from oncall.agent.prompts import SUMMARISE_PROMPT
from oncall.ledger import EvidenceLedger
from oncall.tools import REGISTRY, load_all


def summarise(llm: Any, ledger: EvidenceLedger, window_minutes: int = 5) -> str:
    """Checkpoint 1: gather the overview tool outputs, then one LLM call turns them into a symptoms summary."""
    load_all()
    outputs = [
        REGISTRY.call("list_services", {}, ledger),
        REGISTRY.call("get_error_rates", {"window_minutes": window_minutes}, ledger),
    ]
    messages = [{"role": "system", "content": SUMMARISE_PROMPT}, {"role": "user", "content": "\n\n".join(outputs)}]
    return llm.chat(messages).content
