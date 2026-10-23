from typing import Any

import httpx

from app.config import ACTION_API_URL, HOST_FALLBACK_URLS


def _get_action_api_client() -> tuple[httpx.Client, str]:
    urls = [ACTION_API_URL, HOST_FALLBACK_URLS.get("action_api", "http://localhost:8201")]
    for url in urls:
        try:
            client = httpx.Client(timeout=10.0)
            resp = client.get(f"{url}/health")
            if resp.status_code == 200:
                return client, url
            client.close()
        except Exception:
            pass
    return httpx.Client(timeout=10.0), urls[0]


def get_container_health(service: str = "") -> str:
    client, base_url = _get_action_api_client()
    try:
        if service and isinstance(service, str) and service.strip():
            svc = service.strip()
            resp = client.get(f"{base_url}/containers/{svc}")
            if resp.status_code == 404:
                return f"Container '{svc}' not found."
            if resp.status_code != 200:
                return f"Action API error HTTP {resp.status_code}: {resp.text[:200]}"
            c = resp.json()
            mem_mb = c.get("memory_usage_bytes", 0) / (1024 * 1024)
            limit_mb = c.get("memory_limit_bytes", 0) / (1024 * 1024)
            mem_str = (
                f"{mem_mb:.1f}MB / {limit_mb:.1f}MB ({(mem_mb/limit_mb*100):.1f}%)"
                if limit_mb > 0
                else f"{mem_mb:.1f}MB"
            )

            lines = [
                f"Container Health: {c.get('name')}",
                f"- State: {c.get('state')} (status: {c.get('status')})",
                f"- Health: {c.get('health', 'none')}",
                f"- Restarts: {c.get('restart_count', 0)}",
                f"- OOMKilled: {c.get('oom_killed', False)} (exit code: {c.get('exit_code', 0)})",
                f"- CPU: {c.get('cpu_percent', 0.0):.2f}%",
                f"- Memory: {mem_str}",
                f"- StartedAt: {c.get('started_at', '')}",
            ]
            out = "\n".join(lines)
            return out[:2000]

        resp = client.get(f"{base_url}/containers")
        if resp.status_code != 200:
            return f"Action API error HTTP {resp.status_code}: {resp.text[:200]}"
        containers: list[dict[str, Any]] = resp.json()
    except Exception as e:
        return f"Error contacting Action API: {e}"
    finally:
        client.close()

    if not containers:
        return "No containers found."

    def sort_key(c: dict[str, Any]) -> tuple[int, int, int]:
        is_bad_state = 1 if c.get("state") != "running" or c.get("health") == "unhealthy" else 0
        restarts = c.get("restart_count", 0)
        oom = 1 if c.get("oom_killed") else 0
        return (is_bad_state, oom, restarts)

    containers.sort(key=sort_key, reverse=True)

    lines = [
        "| Service | State | Health | Restarts | OOM | CPU% | Memory |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in containers[:18]:
        name = c.get("name", "unknown")
        state = c.get("state", "unknown")
        health = c.get("health", "none")
        restarts = c.get("restart_count", 0)
        oom = "YES" if c.get("oom_killed") else "no"
        cpu = f"{c.get('cpu_percent', 0.0):.1f}%"
        mem_mb = c.get("memory_usage_bytes", 0) / (1024 * 1024)
        limit_mb = c.get("memory_limit_bytes", 0) / (1024 * 1024)
        mem_str = f"{mem_mb:.0f}M/{(limit_mb):.0f}M" if limit_mb > 0 else f"{mem_mb:.0f}M"

        lines.append(f"| {name} | {state} | {health} | {restarts} | {oom} | {cpu} | {mem_str} |")

    if len(containers) > 18:
        lines.append(f"... ({len(containers) - 18} more containers)")

    out = "\n".join(lines)
    return out[:2000]
