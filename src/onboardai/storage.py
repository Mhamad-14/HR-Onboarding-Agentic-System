"""Sandboxed operational database and explicit cross-thread employee memory."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langgraph.store.memory import InMemoryStore


class TransientITError(ConnectionError):
    """Known retryable failure raised by the simulated IT service."""


class OperationsDatabase:
    """A real, local side-effect boundary used instead of external HR/IT systems."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.it_attempts: dict[str, int] = {}
        self._setup()

    def _setup(self) -> None:
        with self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS it_tickets (
                    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL UNIQUE,
                    employee_id TEXT NOT NULL,
                    requested_access TEXT NOT NULL,
                    status TEXT NOT NULL,
                    risk_flags TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    approved_at TEXT
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def create_draft_it_ticket(
        self,
        *,
        case_id: str,
        employee_id: str,
        requested_access: list[str],
        risk_flags: list[str],
        fail_first_attempt: bool = False,
    ) -> dict[str, Any]:
        attempt = self.it_attempts.get(case_id, 0) + 1
        self.it_attempts[case_id] = attempt
        print(f"[create_draft_it_ticket] attempt #{attempt}")
        if fail_first_attempt and attempt == 1:
            print("[create_draft_it_ticket] simulated transient network error")
            raise TransientITError("simulated transient IT service failure")

        now = datetime.now(UTC).isoformat()
        with self.lock, self.connection:
            self.connection.execute(
                """
                INSERT INTO it_tickets (
                    case_id, employee_id, requested_access, status, risk_flags, created_at
                ) VALUES (?, ?, ?, 'DRAFT', ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET
                    requested_access=excluded.requested_access,
                    risk_flags=excluded.risk_flags
                """,
                (
                    case_id,
                    employee_id,
                    json.dumps(requested_access),
                    json.dumps(risk_flags),
                    now,
                ),
            )
            row = self.connection.execute(
                "SELECT * FROM it_tickets WHERE case_id = ?", (case_id,)
            ).fetchone()
        return dict(row) if row else {}

    def approve_it_ticket(self, case_id: str) -> str:
        now = datetime.now(UTC).isoformat()
        with self.lock, self.connection:
            cursor = self.connection.execute(
                "UPDATE it_tickets SET status='APPROVED', approved_at=? WHERE case_id=?",
                (now, case_id),
            )
        if cursor.rowcount != 1:
            raise LookupError(f"No draft IT ticket exists for {case_id}")
        return f"IT ticket for {case_id} marked APPROVED"

    def record_event(self, case_id: str, event_type: str, payload: dict[str, Any]) -> None:
        with self.lock, self.connection:
            self.connection.execute(
                "INSERT INTO audit_events (case_id, event_type, payload, created_at) "
                "VALUES (?, ?, ?, ?)",
                (case_id, event_type, json.dumps(payload), datetime.now(UTC).isoformat()),
            )

    def list_events(self, case_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM audit_events WHERE case_id=? ORDER BY event_id", (case_id,)
        ).fetchall()
        return [dict(row) for row in rows]


class EmployeeMemory:
    """Separate LangGraph Store for safe facts that must cross thread boundaries."""

    def __init__(self, store: InMemoryStore | None = None):
        self.store = store or InMemoryStore()

    @staticmethod
    def namespace(employee_id: str) -> tuple[str, str]:
        return ("employees", employee_id)

    def remember_preferences(
        self,
        employee_id: str,
        *,
        preferred_language: str,
        training_format: str,
    ) -> None:
        self.store.put(
            self.namespace(employee_id),
            "onboarding_preferences",
            {
                "preferred_language": preferred_language,
                "training_format": training_format,
            },
        )

    def recall_preferences(self, employee_id: str) -> dict[str, str] | None:
        item = self.store.get(self.namespace(employee_id), "onboarding_preferences")
        return dict(item.value) if item else None

    def record_completed_training(self, employee_id: str, courses: list[str]) -> None:
        self.store.put(
            self.namespace(employee_id),
            "completed_training",
            {"courses": courses},
        )
