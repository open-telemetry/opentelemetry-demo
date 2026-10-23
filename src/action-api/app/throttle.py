import os
from typing import Any

import httpx

LOAD_GENERATOR_URL = os.environ.get("LOAD_GENERATOR_URL", "http://load-generator:8089")


def throttle_load_generator(users: int, spawn_rate: float) -> tuple[bool, str, dict[str, Any] | None]:
    previous_users = 5
    try:
        with httpx.Client(timeout=10.0) as client:
            stats_resp = client.get(f"{LOAD_GENERATOR_URL}/stats/requests")
            if stats_resp.status_code == 200:
                stats = stats_resp.json()
                previous_users = stats.get("user_count", 5)
    except Exception:
        pass

    previous_state = {
        "users": previous_users,
        "spawn_rate": 1.0,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{LOAD_GENERATOR_URL}/swarm",
                data={"user_count": int(users), "spawn_rate": float(spawn_rate)},
            )
            if resp.status_code != 200:
                return False, f"Locust swarm returned HTTP {resp.status_code}", None
    except Exception as e:
        return False, f"Failed to connect to Locust load generator: {e}", None

    return True, f"Throttled load generator to {users} users at spawn rate {spawn_rate}", previous_state


def rollback_throttle(previous_state: dict[str, Any]) -> tuple[bool, str]:
    users = previous_state.get("users", 5)
    spawn_rate = previous_state.get("spawn_rate", 1.0)
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{LOAD_GENERATOR_URL}/swarm",
                data={"user_count": int(users), "spawn_rate": float(spawn_rate)},
            )
            if resp.status_code != 200:
                return False, f"Locust rollback returned HTTP {resp.status_code}"
    except Exception as e:
        return False, f"Failed to restore Locust load generator: {e}"

    return True, f"Restored load generator to {users} users"
