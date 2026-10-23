"""The result of one faultctl operation, and the exit code each kind of result maps to."""
from dataclasses import dataclass, field
from enum import Enum


class Outcome(Enum):
    VERIFIED = "verified"  # applied and read back as expected
    UNVERIFIED = "applied-unverified"  # accepted, but the read-back was missing or different
    FAILED = "failed"  # did not (fully) happen
    TIMED_OUT = "timed-out"  # the change may or may not have happened; never retried
    DRY_RUN = "dry-run"  # plan only, nothing changed
    REFUSED = "refused"  # rejected by a safety rule before anything changed


EXIT_CODES = {
    Outcome.VERIFIED: 0,
    Outcome.DRY_RUN: 0,
    Outcome.REFUSED: 2,
    Outcome.UNVERIFIED: 3,
    Outcome.FAILED: 4,
    Outcome.TIMED_OUT: 5,
}
EXIT_UNHEALTHY = 1  # `status` only: something is not running or not healthy


class Refused(Exception):
    """A safety rule forbids this operation. Raised before anything is changed."""


@dataclass
class Result:
    outcome: Outcome
    lines: list[str] = field(default_factory=list)  # human-readable detail, printed indented
    variant: str = "-"  # the variant applied (or planned); "-" when not applicable
    log_error: str | None = None  # set if the ground-truth row could not be written


def exit_code(result: Result) -> int:
    """Exit code for a result; an unwritten ground-truth row counts as a failure."""
    code = EXIT_CODES[result.outcome]
    return max(code, EXIT_CODES[Outcome.FAILED]) if result.log_error else code
