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


def get_recent_changes(lookback_min: int = 60) -> str:
    lookback = max(1, min(int(lookback_min), 1440))
    client, base_url = _get_action_api_client()
    try:
        resp = client.get(f"{base_url}/events", params={"since_minutes": lookback})
        if resp.status_code != 200:
            return f"Action API error HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
    except Exception as e:
        return f"Error contacting Action API: {e}"
    finally:
        client.close()

    events: list[dict[str, Any]] = data.get("events", [])
    if not events:
        return f"No container lifecycle changes or actions recorded in the last {lookback} minutes."

    lines = [f"Recent System Changes & Events (last {lookback}m, {len(events)} events):", ""]
    for ev in events[-15:]:
        ts = ev.get("timestamp", "")
        time_short = ts[11:19] if len(ts) >= 19 else ts
        source = ev.get("source", "docker")
        ev_type = ev.get("type", "unknown")
        service = ev.get("service", "unknown")
        details = ev.get("details", {})
        det_str = f" {details}" if details and isinstance(details, dict) and any(details.values()) else ""
        lines.append(f"[{time_short}] [{source}] {service} -> {ev_type}{det_str}")

    if len(events) > 15:
        lines.append(f"... ({len(events) - 15} earlier events omitted)")

    out = "\n".join(lines)
    return out[:2000]
