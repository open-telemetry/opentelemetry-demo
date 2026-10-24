import json
import subprocess
from datetime import datetime, timezone

from tests.test_containers import FakeDocker, inspect_entry
from tools.deploys import build_rows, deploy_history, parse_time
from tools.containers import parse_inspect

NOW = datetime(2026, 10, 23, 18, 0, 0, tzinfo=timezone.utc)


def entry(name, started, restarts=0, status="running"):
    return inspect_entry(name, name, status, restarts=restarts, started=started)


# Most containers came up together at 15:32; valkey-cart was started again at 17:40.
ENTRIES = [
    entry("cart", "2026-10-23T15:32:35.123456789Z"),
    entry("payment", "2026-10-23T15:32:40.000000000Z"),
    entry("checkout", "2026-10-23T15:32:36.5Z"),
    entry("valkey-cart", "2026-10-23T17:39:58.000000000Z"),
    entry("email", "2026-10-23T15:32:37Z", restarts=3),
    entry("flagd", "2026-10-23T17:59:00Z"),
]


def rows():
    return {r["name"]: r for r in build_rows(parse_inspect(json.dumps(ENTRIES[:5])), NOW)}


def test_parse_time_handles_nanoseconds_short_fractions_and_never_started():
    assert parse_time("2026-10-23T15:32:35.123456789Z") == datetime(2026, 10, 23, 15, 32, 35, 123456, tzinfo=timezone.utc)
    assert parse_time("2026-10-23T15:32:35Z").second == 35
    assert parse_time("0001-01-01T00:00:00Z") is None and parse_time(None) is None and parse_time("garbage") is None


def test_age_is_seconds_since_start_and_newest_start_comes_first():
    r = rows()
    assert r["cart"]["age_seconds"] == 8844  # 15:32:35.12 to 18:00:00, rounded down
    assert list(r)[0] == "valkey-cart"


def test_a_container_started_long_after_the_others_is_flagged_and_so_is_a_restart_count():
    r = rows()
    assert r["valkey-cart"]["restarted_recently"] is True
    assert r["email"]["restarted_recently"] is True and r["email"]["restart_count"] == 3
    assert r["cart"]["restarted_recently"] is False and r["payment"]["restarted_recently"] is False


def test_data_with_summary_notes_and_the_flag_container_removed():
    docker = FakeDocker(inspect=ENTRIES, ids="a\nb\nc\nd\ne\nf\n")
    result = deploy_history(runner=docker)
    assert result.state == "data" and "flagd" not in json.dumps(result.to_dict())
    assert set(result.extra["summary"]["restarted_recently"]) == {"valkey-cart", "email"}
    assert any("force-recreate" in n for n in result.notes)
    assert any("1 items removed by sanitiser" in n for n in result.notes)
    assert result.total_items == 5


def test_a_whole_stack_start_is_called_out():
    same = [entry(n, "2026-10-23T17:55:00Z") for n in ("cart", "payment", "checkout")]
    result = deploy_history(runner=FakeDocker(inspect=same, ids="a\nb\nc\n"))
    assert any("whole-stack start" in n for n in result.notes)
    assert result.extra["summary"]["restarted_recently"] == []


def test_no_containers_is_no_data():
    result = deploy_history(runner=FakeDocker(ids=""))
    assert result.state == "no_data" and any("no containers" in n for n in result.notes)


def test_only_the_flag_containers_left_is_no_data():
    result = deploy_history(runner=FakeDocker(inspect=[entry("flagd", "2026-10-23T17:59:00Z")], ids="a\n"))
    assert result.state == "no_data"


def test_docker_problems_are_backend_error():
    for fail in ("missing", "timeout", "daemon"):
        result = deploy_history(runner=FakeDocker(fail=fail))
        assert result.state == "backend_error" and result.error, fail


def test_unparseable_inspect_output_is_backend_error():
    def runner(args, capture_output, text, timeout):
        return subprocess.CompletedProcess(args, 0, "a\n" if args[1] == "ps" else "not json", "")
    assert deploy_history(runner=runner).state == "backend_error"


def test_invalid_project_name_is_backend_error_without_running_docker():
    docker = FakeDocker()
    result = deploy_history(project="bad name; rm -rf /", runner=docker)
    assert result.state == "backend_error" and docker.calls == []
