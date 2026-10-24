"""Adapter from our report format to the official one.

oncall/report/schema.json IS the schema, so this stays the identity; keeping it
means a future format change is a one-file change.
"""


def to_official(report: dict) -> dict:
    return report
