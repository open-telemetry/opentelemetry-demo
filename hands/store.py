# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0
"""Durable SQLite storage for plans, approvals, idempotency, kill latch, and audit."""

import json
from pathlib import Path
import sqlite3
from typing import Any


class HandsStore:
    def __init__(self, directory: Path | str):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db_path = self.directory / "hands.sqlite"
        self.db = sqlite3.connect(self.db_path, timeout=5)
        self.db.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self.db:
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS plans (
                    plan_digest TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    data TEXT NOT NULL
                )
                """
            )
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    plan_digest TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    approved_at TEXT NOT NULL,
                    data TEXT NOT NULL
                )
                """
            )
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS dispatches (
                    plan_digest TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    attempt_id TEXT NOT NULL,
                    dispatched_at TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS kill_switch (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    engaged INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    reason TEXT NOT NULL
                )
                """
            )
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS action_audit (
                    attempt_id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    plan_digest TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    dispatched_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    data TEXT NOT NULL
                )
                """
            )
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS verifications (
                    incident_id TEXT NOT NULL,
                    plan_digest TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    verified_at TEXT NOT NULL,
                    data TEXT NOT NULL,
                    PRIMARY KEY (incident_id, plan_digest)
                )
                """
            )

    def save_plan(self, plan: dict) -> None:
        with self.db:
            self.db.execute(
                """
                INSERT OR REPLACE INTO plans (plan_digest, incident_id, action_type, target, created_at, data)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    plan["plan_digest"],
                    plan["incident_id"],
                    plan["action_type"],
                    plan["target"],
                    plan.get("created_at", ""),
                    json.dumps(plan),
                ),
            )

    def get_plan(self, plan_digest: str) -> dict | None:
        cur = self.db.execute("SELECT data FROM plans WHERE plan_digest = ?", (plan_digest,))
        row = cur.fetchone()
        return json.loads(row["data"]) if row else None

    def list_plans(self, limit: int = 50) -> list[dict]:
        cur = self.db.execute("SELECT data FROM plans ORDER BY created_at DESC LIMIT ?", (limit,))
        return [json.loads(row["data"]) for row in cur.fetchall()]

    def save_approval(self, approval: dict) -> None:
        with self.db:
            self.db.execute(
                """
                INSERT OR REPLACE INTO approvals (plan_digest, incident_id, decision, operator, approved_at, data)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    approval["plan_digest"],
                    approval["incident_id"],
                    approval["decision"],
                    approval["operator"],
                    approval["approved_at"],
                    json.dumps(approval),
                ),
            )

    def get_approval(self, plan_digest: str) -> dict | None:
        cur = self.db.execute("SELECT data FROM approvals WHERE plan_digest = ?", (plan_digest,))
        row = cur.fetchone()
        return json.loads(row["data"]) if row else None

    def record_dispatch(self, incident_id: str, plan_digest: str, attempt_id: str, dispatched_at: str, status: str) -> None:
        with self.db:
            self.db.execute(
                """
                INSERT INTO dispatches (plan_digest, incident_id, attempt_id, dispatched_at, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (plan_digest, incident_id, attempt_id, dispatched_at, status),
            )

    def is_dispatched(self, plan_digest: str) -> bool:
        cur = self.db.execute("SELECT 1 FROM dispatches WHERE plan_digest = ?", (plan_digest,))
        return cur.fetchone() is not None

    def set_kill_switch(self, engaged: bool, updated_at: str, operator: str, reason: str) -> None:
        with self.db:
            self.db.execute(
                """
                INSERT OR REPLACE INTO kill_switch (id, engaged, updated_at, operator, reason)
                VALUES (1, ?, ?, ?, ?)
                """,
                (1 if engaged else 0, updated_at, operator, reason),
            )

    def get_kill_switch(self) -> dict:
        cur = self.db.execute("SELECT engaged, updated_at, operator, reason FROM kill_switch WHERE id = 1")
        row = cur.fetchone()
        if not row:
            return {
                "engaged": False,
                "updated_at": "",
                "operator": "",
                "reason": "",
            }
        return {
            "engaged": bool(row["engaged"]),
            "updated_at": row["updated_at"],
            "operator": row["operator"],
            "reason": row["reason"],
        }

    def save_audit(self, attempt: dict) -> None:
        with self.db:
            self.db.execute(
                """
                INSERT OR REPLACE INTO action_audit
                (attempt_id, incident_id, plan_digest, action_type, target, dispatched_at, status, duration_ms, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt["attempt_id"],
                    attempt["incident_id"],
                    attempt["plan_digest"],
                    attempt["action_type"],
                    attempt["target"],
                    attempt["dispatched_at"],
                    attempt["status"],
                    attempt["duration_ms"],
                    json.dumps(attempt),
                ),
            )

    def list_audits(self, limit: int = 50) -> list[dict]:
        cur = self.db.execute("SELECT data FROM action_audit ORDER BY dispatched_at DESC LIMIT ?", (limit,))
        return [json.loads(row["data"]) for row in cur.fetchall()]

    def save_verification(self, verif: dict) -> None:
        with self.db:
            self.db.execute(
                """
                INSERT OR REPLACE INTO verifications (incident_id, plan_digest, verdict, verified_at, data)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    verif["incident_id"],
                    verif["plan_digest"],
                    verif["verdict"],
                    verif["verified_at"],
                    json.dumps(verif),
                ),
            )

    def get_verification(self, incident_id: str, plan_digest: str) -> dict | None:
        cur = self.db.execute(
            "SELECT data FROM verifications WHERE incident_id = ? AND plan_digest = ?",
            (incident_id, plan_digest),
        )
        row = cur.fetchone()
        return json.loads(row["data"]) if row else None

    def close(self) -> None:
        self.db.close()
