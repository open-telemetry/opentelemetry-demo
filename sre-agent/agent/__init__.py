import sys

# Windows consoles default to cp1252: never crash on a unicode character from the LLM or logs
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
