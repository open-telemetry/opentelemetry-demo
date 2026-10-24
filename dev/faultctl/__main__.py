"""faultctl: inject and reset practice incidents. Developer tooling, never used by the agent.

  python -m dev.faultctl list
  python -m dev.faultctl inject <id> [--variant V] [--dry-run]
  python -m dev.faultctl reset <id> [--dry-run]
  python -m dev.faultctl reset-all [--yes] [--dry-run]
  python -m dev.faultctl status

Exit codes: 0 verified (or dry-run ok), 1 status found something unhealthy, 2 refused or
bad usage, 3 applied but unverified, 4 failed, 5 timed out (never retried).
"""
import argparse
import sys
import time
from datetime import datetime

from dev.faultctl import flags
from dev.faultctl.catalog import CATALOGUE, COMPOSE_PROJECT, CONTAINER, DEFAULT_BASE_URL, Incident
from dev.faultctl.docker_ops import ContainerOps, DockerCli, DockerError, DockerTimeout, health_of
from dev.faultctl.ground_truth import DEFAULT_PATH, GroundTruthLog
from dev.faultctl.outcome import EXIT_CODES, EXIT_UNHEALTHY, Outcome, Refused, Result, exit_code


class Faultctl:
    """Runs one inject/reset: validate, act (or plan), verify, and always write a ground-truth row."""

    def __init__(self, http, docker, ground_truth: GroundTruthLog, sleep=time.sleep):
        self.http = http
        self.containers = ContainerOps(docker, COMPOSE_PROJECT, sleep)
        self.ground_truth = ground_truth

    def inject(self, incident_id: str, variant: str | None, dry_run: bool) -> Result:
        return self._run("inject", incident_id, variant, dry_run)

    def reset(self, incident_id: str, dry_run: bool) -> Result:
        return self._run("reset", incident_id, None, dry_run)

    def _run(self, action: str, incident_id: str, variant: str | None, dry_run: bool) -> Result:
        started = datetime.now().astimezone().isoformat(timespec="seconds")
        incident = CATALOGUE.get(incident_id)
        try:
            if incident is None:
                raise Refused(f"unknown incident {incident_id!r}; `list` shows the allowlist")
            result = self._apply(action, incident, variant, dry_run)
        except Refused as exc:
            result = Result(Outcome.REFUSED, [str(exc)], variant or "-")
        try:
            log_operation(self.ground_truth, started, action, incident_id, result)
        except OSError as exc:
            result.log_error = f"GROUND TRUTH NOT WRITTEN ({exc}); record this operation by hand"
        return result

    def _apply(self, action: str, incident: Incident, variant: str | None, dry_run: bool) -> Result:
        if incident.mechanism == CONTAINER:
            if variant:
                raise Refused(f"{incident.id} is a container incident and has no variants")
            if action == "inject":
                return self.containers.stop(incident, dry_run)
            return self.containers.start(incident, dry_run)
        if action == "inject":
            variant = variant or incident.inject_variant
            if variant == incident.rest_variant:
                raise Refused(f"variant {variant!r} is the resting state; use `reset {incident.id}` instead")
        else:
            variant = incident.rest_variant
        return flags.set_flag(self.http, incident, variant, dry_run)


def log_operation(gt: GroundTruthLog, started: str, action: str, incident_id: str, result: Result,
                  note: str | None = None) -> None:
    incident = CATALOGUE.get(incident_id)
    note = note if note is not None else (result.lines[0] if result.lines else "")
    gt.append(started, action, incident_id, incident.mechanism if incident else "-",
              incident.target if incident else "-", result.variant, result.outcome.value, note)


def print_result(action: str, incident_id: str, result: Result) -> None:
    print(f"[{result.outcome.value}] {action} {incident_id}")
    for line in result.lines + ([result.log_error] if result.log_error else []):
        print(f"    {line}")


def worst_exit_code(results: list[Result]) -> int:
    return max((exit_code(r) for r in results), default=0)


def cmd_list() -> int:
    print(f"{'id':34} {'mechanism':10} {'target':30} inject-default")
    for i in CATALOGUE.values():
        print(f"{i.id:34} {i.mechanism:10} {i.target:30} {i.inject_variant or '-'}")
    return 0


def cmd_status(http, docker) -> int:
    """Health of the demo's containers and its front doors. Says nothing about which faults are active."""
    unhealthy = False
    try:
        containers = docker.project_containers(COMPOSE_PROJECT)
    except (DockerError, DockerTimeout) as exc:
        print(f"docker: {exc}")
        return EXIT_CODES[Outcome.FAILED]
    print(f"containers in compose project {COMPOSE_PROJECT!r} ({len(containers)}):")
    print(f"  {'name':22} {'state':12} {'health':10} restarts")
    for info in sorted(containers, key=lambda c: c["Name"]):
        state, health = info["State"]["Status"], health_of(info)
        if state != "running" or health not in (None, "healthy"):
            unhealthy = True
        print(f"  {info['Name'].lstrip('/'):22} {state:12} {health or '-':10} {info.get('RestartCount', '?')}")
    if not containers:
        unhealthy = True
        print("  (none found)")
    for label, path in [("shop front page", flags.FRONT_DOOR_PATH), ("flag UI", flags.READ_PATH)]:
        try:
            code = http.get_status(path)
        except (flags.HttpTimeout, flags.HttpFailure) as exc:
            code = f"unreachable ({exc})"
        if code != 200:
            unhealthy = True
        print(f"{label}: HTTP {code}")
    return EXIT_UNHEALTHY if unhealthy else 0


def cmd_reset_all(ctl: Faultctl, yes: bool, dry_run: bool, confirm=input) -> int:
    ids = list(CATALOGUE)
    if not dry_run and not yes:
        print(f"This resets {len(ids)} incidents: {', '.join(ids)}")
        print("(flags go back to their resting variant; stopped containers are started.)")
        try:
            answer = confirm("Type 'yes' to continue: ")
        except EOFError:
            answer = ""
        if answer.strip().lower() != "yes":
            print("aborted; nothing was changed")
            return EXIT_CODES[Outcome.REFUSED]
    results = []
    for incident_id in ids:
        result = ctl.reset(incident_id, dry_run)
        print_result("reset", incident_id, result)
        results.append(result)
    return worst_exit_code(results)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m dev.faultctl", description=__doc__.split("\n")[0])
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="front proxy URL; must be loopback")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="show the allowlisted incidents")
    inject = sub.add_parser("inject", help="start an incident")
    inject.add_argument("incident")
    inject.add_argument("--variant", help="flag incidents only; must be a live variant of the flag")
    inject.add_argument("--dry-run", action="store_true")
    reset = sub.add_parser("reset", help="end one incident")
    reset.add_argument("incident")
    reset.add_argument("--dry-run", action="store_true")
    reset_all = sub.add_parser("reset-all", help="end every catalogued incident")
    reset_all.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    reset_all.add_argument("--dry-run", action="store_true")
    sub.add_parser("status", help="container and service health (not which faults are active)")
    return parser


def main(argv=None, *, http=None, docker=None, ground_truth_path=DEFAULT_PATH, sleep=time.sleep,
         confirm=input) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "list":
        return cmd_list()
    gt = GroundTruthLog(ground_truth_path)
    try:
        http = http or flags.FlagUiHttp(args.base_url)
    except Refused as exc:
        print(f"refused: {exc}")
        if args.command in ("inject", "reset", "reset-all"):
            started = datetime.now().astimezone().isoformat(timespec="seconds")
            incident_id = "all" if args.command == "reset-all" else args.incident
            action = "reset" if args.command == "reset-all" else args.command
            try:
                log_operation(gt, started, action, incident_id, Result(Outcome.REFUSED, [str(exc)]))
            except OSError as log_exc:
                print(f"GROUND TRUTH NOT WRITTEN ({log_exc})")
        return EXIT_CODES[Outcome.REFUSED]
    docker = docker or DockerCli()

    if args.command == "status":
        return cmd_status(http, docker)
    ctl = Faultctl(http, docker, gt, sleep)
    if args.command == "reset-all":
        return cmd_reset_all(ctl, args.yes, args.dry_run, confirm)
    if args.command == "inject":
        result = ctl.inject(args.incident, args.variant, args.dry_run)
    else:
        result = ctl.reset(args.incident, args.dry_run)
    print_result(args.command, args.incident, result)
    return exit_code(result)


if __name__ == "__main__":
    sys.exit(main())
