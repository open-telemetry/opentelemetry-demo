"""Abstract base class for fault controllers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class FaultController(ABC):
    """Interface for injecting and reverting faults in the target system."""

    @abstractmethod
    def inject_fault(self, fault_name: str, variant: str = "on") -> bool:
        """Activate a specific fault."""
        pass

    @abstractmethod
    def revert_fault(self, fault_name: str) -> bool:
        """Deactivate a specific fault."""
        pass

    @abstractmethod
    def list_available_faults(self) -> List[str]:
        """List all supported fault identifiers."""
        pass

    @abstractmethod
    def get_fault_state(self, fault_name: str) -> Dict[str, Any]:
        """Query current state of a fault."""
        pass
