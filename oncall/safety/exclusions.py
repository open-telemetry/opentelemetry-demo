"""Services and spans every tool hides from the agent and the UI (RULES.md hard rule 2).

The flag service and its UI must never be read to diagnose, so tools drop them
from queries, results and evidence, together with the spans other services make
when they call them. Import from here instead of naming them.
"""

import re

EXCLUDED_SERVICES: frozenset[str] = frozenset({"flagd", "flagd-ui"})

# Span names that contain "flag" in any case: flag-service RPCs made by other
# services (flagd.evaluation.v2.Service/EventStream), flagSync, the flag UI's
# own spans, and the proxy routes to it.
FLAG_SPAN = re.compile(r"flag", re.IGNORECASE)

# PromQL label matchers that remove excluded services and flag spans from a selector.
PROMQL_EXCLUDE = 'service_name!~"{}",span_name!~"(?i).*flag.*"'.format(
    "|".join(sorted(EXCLUDED_SERVICES))
)

# Flag-service names that must never appear in a recorded fixture file (CI greps
# oncall/ for them); the recorder replaces them.
FIXTURE_SCRUB = re.compile(r"flagd-ui|flagd|ofrep", re.IGNORECASE)


def is_excluded(service: str | None) -> bool:
    return service in EXCLUDED_SERVICES


def is_excluded_span(span_name: str | None) -> bool:
    return bool(span_name and FLAG_SPAN.search(span_name))
