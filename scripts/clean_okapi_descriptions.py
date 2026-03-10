#!/usr/bin/env python3
import json
from pathlib import Path

TARGET = Path("src/grafana/provisioning/dashboards/okapi/apm-dashboard.json")


def clean(obj):
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k == "description" and isinstance(v, str):
                if "OpenSearch" in v or "Jager" in v or "Jaeger" in v:
                    obj[k] = (
                        v.replace("OpenSearch", "Okapi")
                        .replace("Jager", "Okapi")
                        .replace("Jaeger", "Okapi")
                    )
            else:
                clean(v)
    elif isinstance(obj, list):
        for it in obj:
            clean(it)


def main():
    data = json.loads(TARGET.read_text())
    clean(data)
    TARGET.write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    main()
