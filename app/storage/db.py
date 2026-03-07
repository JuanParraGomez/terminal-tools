from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._init()

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    selected_tool TEXT NOT NULL,
                    selected_profile TEXT NOT NULL,
                    input_summary TEXT,
                    cwd TEXT,
                    command_json TEXT,
                    result_json TEXT,
                    stdout_path TEXT,
                    stderr_path TEXT,
                    summary TEXT,
                    error TEXT,
                    context_id TEXT,
                    context_freshness TEXT,
                    used_context_sections_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    name TEXT,
                    metadata_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS context_snapshots (
                    context_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL
                )
                """
            )

    def upsert_task(self, payload: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks(
                    task_id, created_at, started_at, finished_at, status, selected_tool, selected_profile,
                    input_summary, cwd, command_json, result_json, stdout_path, stderr_path, summary, error,
                    context_id, context_freshness, used_context_sections_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(task_id) DO UPDATE SET
                    started_at=excluded.started_at,
                    finished_at=excluded.finished_at,
                    status=excluded.status,
                    cwd=excluded.cwd,
                    command_json=excluded.command_json,
                    result_json=excluded.result_json,
                    stdout_path=excluded.stdout_path,
                    stderr_path=excluded.stderr_path,
                    summary=excluded.summary,
                    error=excluded.error,
                    context_id=excluded.context_id,
                    context_freshness=excluded.context_freshness,
                    used_context_sections_json=excluded.used_context_sections_json
                """,
                (
                    payload["task_id"],
                    payload["created_at"],
                    payload.get("started_at"),
                    payload.get("finished_at"),
                    payload["status"],
                    payload["selected_tool"],
                    payload["selected_profile"],
                    payload.get("input_summary"),
                    payload.get("cwd"),
                    json.dumps(payload.get("command")),
                    json.dumps(payload.get("result", {})),
                    payload.get("stdout_path"),
                    payload.get("stderr_path"),
                    payload.get("summary"),
                    payload.get("error"),
                    payload.get("context_id"),
                    payload.get("context_freshness"),
                    json.dumps(payload.get("used_context_sections", [])),
                ),
            )

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            return self._task_row_to_dict(row) if row else None

    def list_tasks(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [self._task_row_to_dict(r) for r in rows]

    def create_session(self, session_id: str, name: str | None, metadata: dict[str, Any]) -> dict[str, Any]:
        created_at = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO sessions(session_id, created_at, name, metadata_json) VALUES(?,?,?,?)",
                (session_id, created_at, name, json.dumps(metadata)),
            )
        return {
            "session_id": session_id,
            "created_at": created_at,
            "name": name,
            "metadata": metadata,
        }

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
            if not row:
                return None
            return {
                "session_id": row["session_id"],
                "created_at": row["created_at"],
                "name": row["name"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
            }

    def save_context_snapshot(self, context_id: str, snapshot: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO context_snapshots(context_id, created_at, snapshot_json) VALUES(?,?,?)",
                (context_id, snapshot["created_at"], json.dumps(snapshot)),
            )

    def get_latest_context_snapshot(self) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT snapshot_json FROM context_snapshots ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            return json.loads(row["snapshot_json"]) if row else None

    @staticmethod
    def _task_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "task_id": row["task_id"],
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "status": row["status"],
            "selected_tool": row["selected_tool"],
            "selected_profile": row["selected_profile"],
            "input_summary": row["input_summary"],
            "cwd": row["cwd"],
            "command": json.loads(row["command_json"] or "null"),
            "result": json.loads(row["result_json"] or "{}"),
            "stdout_path": row["stdout_path"],
            "stderr_path": row["stderr_path"],
            "summary": row["summary"],
            "error": row["error"],
            "context_id": row["context_id"],
            "context_freshness": row["context_freshness"],
            "used_context_sections": json.loads(row["used_context_sections_json"] or "[]"),
        }
