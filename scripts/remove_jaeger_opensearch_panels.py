#!/usr/bin/env python3
import json
from pathlib import Path

DASHBOARDS = [
    Path("src/grafana/provisioning/dashboards/okapi/demo-dashboard.json"),
    Path("src/grafana/provisioning/dashboards/okapi/opentelemetry-collector.json"),
    Path("src/grafana/provisioning/dashboards/okapi/apm-dashboard.json"),
]

REMOVE_TYPES = {"jaeger", "grafana-opensearch-datasource"}


def panel_uses_removed_ds(panel):
    ds = panel.get("datasource")
    if isinstance(ds, dict) and ds.get("type") in REMOVE_TYPES:
        return True
    for target in panel.get("targets", []) or []:
        ds_t = target.get("datasource")
        if isinstance(ds_t, dict) and ds_t.get("type") in REMOVE_TYPES:
            return True
    return False


def clean_panels(panels):
    cleaned = []
    for panel in panels or []:
        if panel.get("type") == "row" and "panels" in panel:
            panel["panels"] = clean_panels(panel.get("panels"))
            if not panel["panels"] and panel_uses_removed_ds(panel):
                continue
            cleaned.append(panel)
            continue
        if panel_uses_removed_ds(panel):
            continue
        cleaned.append(panel)
    return cleaned


def clean_dashboard(data):
    data["panels"] = clean_panels(data.get("panels"))

    templating = data.get("templating", {})
    if "list" in templating:
        new_list = []
        for v in templating.get("list", []):
            q = v.get("query")
            name = v.get("name", "")
            text = v.get("text", "")
            if q in ("jaeger", "grafana-opensearch-datasource"):
                continue
            if name in ("jaeger_datasource", "opensearch_datasource"):
                continue
            if text in ("Jaeger", "OpenSearch"):
                continue
            new_list.append(v)
        templating["list"] = new_list
        data["templating"] = templating

    if isinstance(data.get("description"), str):
        data["description"] = (
            data["description"]
            .replace("Jaeger", "Okapi")
            .replace("OpenSearch", "Okapi")
        )

    if isinstance(data.get("title"), str):
        data["title"] = data["title"].replace(
            "Jaeger, Prometheus, OpenSearch", "Prometheus"
        )

    return data


def main():
    for path in DASHBOARDS:
        data = json.loads(path.read_text())
        data = clean_dashboard(data)
        path.write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    main()
