"""Emergency Kill-Switch safety implementation."""
from __future__ import annotations

import os
from pathlib import Path


class KillSwitchEngagedException(Exception):
    """Raised whenever a remediation action is attempted while the kill switch is active."""
    pass


class KillSwitch:
    """Evaluates whether the emergency kill-switch is engaged.
    
    The kill-switch is considered active if:
    1. The environment variable KILL_SWITCH_ENABLED is 'true'/'1'/'yes'
    2. The sentinel file (e.g. .kill_switch) exists on disk.
    """

    def __init__(self, sentinel_path: Path | str = ".kill_switch", env_var: str = "KILL_SWITCH_ENABLED") -> None:
        self.sentinel_path = Path(sentinel_path)
        self.env_var = env_var

    def is_engaged(self) -> bool:
        """Return True if kill switch is activated via environment or sentinel file."""
        env_val = os.environ.get(self.env_var, "").strip().lower()
        if env_val in ("true", "1", "yes", "on"):
            return True

        if self.sentinel_path.exists():
            return True

        return False

    def guard(self) -> None:
        """Assert that the kill switch is not engaged, raising KillSwitchEngagedException otherwise."""
        if self.is_engaged():
            reason = []
            if os.environ.get(self.env_var, "").strip().lower() in ("true", "1", "yes", "on"):
                reason.append(f"environment variable {self.env_var}=true")
            if self.sentinel_path.exists():
                reason.append(f"sentinel file '{self.sentinel_path}' exists")
            reasons_str = " and ".join(reason) if reason else "manual engagement"
            raise KillSwitchEngagedException(
                f"Emergency Kill-Switch is ENGAGED ({reasons_str}). All autonomous actions are halted."
            )

    def engage_sentinel(self) -> None:
        """Create the sentinel file on disk to immediately halt operations."""
        self.sentinel_path.parent.mkdir(parents=True, exist_ok=True)
        self.sentinel_path.touch(exist_ok=True)

    def disengage_sentinel(self) -> None:
        """Remove the sentinel file if present."""
        if self.sentinel_path.exists():
            self.sentinel_path.unlink()
