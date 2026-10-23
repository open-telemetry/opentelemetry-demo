import os
from typing import Any

import httpx

FLAGD_UI_URL = os.environ.get("FLAGD_UI_URL", "http://flagd-ui:4000")


def set_flag(flag: str, variant: str) -> tuple[bool, str, dict[str, Any] | None]:
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{FLAGD_UI_URL}/api/read-file")
            if resp.status_code != 200:
                return False, f"Failed to read flags from flagd-ui: HTTP {resp.status_code}", None
            flags_data = resp.json()
    except Exception as e:
        return False, f"Failed to connect to flagd-ui: {e}", None

    flags_dict = flags_data.get("flags", {})
    if flag not in flags_dict:
        return False, f"Flag '{flag}' not found in flags file", None

    flag_obj = flags_dict[flag]
    previous_state = {
        "flag": flag,
        "defaultVariant": flag_obj.get("defaultVariant"),
        "targeting": flag_obj.get("targeting"),
    }

    flag_obj["defaultVariant"] = variant

    if flag == "productCatalogFailure" and "targeting" in flag_obj:
        flag_obj["targeting"] = {
            "if": [
                {
                    "==": [
                        {
                            "var": "product_id"
                        },
                        "OLJCESPC7Z"
                    ]
                },
                "off",
                "off"
            ]
        }

    try:
        with httpx.Client(timeout=10.0) as client:
            write_resp = client.post(f"{FLAGD_UI_URL}/api/write-to-file", json={"data": flags_data})
            if write_resp.status_code != 200:
                return False, f"Failed to write flags to flagd-ui: HTTP {write_resp.status_code}", None
    except Exception as e:
        return False, f"Failed to write to flagd-ui: {e}", None

    return True, f"Flag '{flag}' successfully set to {variant}", previous_state


def rollback_flag(previous_state: dict[str, Any]) -> tuple[bool, str]:
    flag = previous_state.get("flag")
    if not flag:
        return False, "Missing flag name in previous state"

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{FLAGD_UI_URL}/api/read-file")
            if resp.status_code != 200:
                return False, f"Failed to read flags from flagd-ui: HTTP {resp.status_code}"
            flags_data = resp.json()
    except Exception as e:
        return False, f"Failed to connect to flagd-ui: {e}"

    flags_dict = flags_data.get("flags", {})
    if flag not in flags_dict:
        return False, f"Flag '{flag}' not found in flags file"

    flag_obj = flags_dict[flag]
    if "defaultVariant" in previous_state:
        flag_obj["defaultVariant"] = previous_state["defaultVariant"]
    if "targeting" in previous_state:
        if previous_state["targeting"] is None:
            flag_obj.pop("targeting", None)
        else:
            flag_obj["targeting"] = previous_state["targeting"]

    try:
        with httpx.Client(timeout=10.0) as client:
            write_resp = client.post(f"{FLAGD_UI_URL}/api/write-to-file", json={"data": flags_data})
            if write_resp.status_code != 200:
                return False, f"Failed to write flags to flagd-ui during rollback: HTTP {write_resp.status_code}"
    except Exception as e:
        return False, f"Failed to write to flagd-ui during rollback: {e}"

    return True, f"Flag '{flag}' rolled back successfully"
