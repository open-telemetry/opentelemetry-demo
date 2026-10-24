"""Tiny test runner (no pytest needed): python -m tests.run"""
import sys
import traceback

from tests import test_action_api, test_agent

fails = 0
names = [(m, n) for m in (test_agent, test_action_api) for n in dir(m) if n.startswith("test_")]
for m, n in names:
    try:
        getattr(m, n)()
        print(f"  PASS {n}")
    except Exception:
        fails += 1
        print(f"  FAIL {n}")
        traceback.print_exc(limit=3)
print(f"\n{len(names) - fails}/{len(names)} passed")
sys.exit(1 if fails else 0)
