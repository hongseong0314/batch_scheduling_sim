# -*- coding: utf-8 -*-
"""SQLite-backed agent run records for MES Agent Mode inspection."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, Mapping

from src.mes.agent_runtime.run_store import AgentRunRecord, AgentRunStore


class SQLiteAgentRunStore(AgentRunStore):
    """Persistent store with the same surface as ``AgentRunStore``."""

    def __init__(self, db_path: str | Path, max_records: int = 500) -> None:
        self.db_path = Path(db_path)
        self._db_lock = threading.RLock()
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        super().__init__(max_records=max_records)
        self._load_records()
        self._enforce_persistent_retention()

    def start_run(
        self,
        *,
        question: str,
        mode: str,
        model_name: str,
        provider: str,
        max_steps: int,
        prompt_id: str,
        prompt_version: str,
        tool_catalog_version: str,
        model_config: Mapping[str, Any],
        requested_think: bool = False,
        mes_run_id: str = "",
    ) -> AgentRunRecord:
        record = super().start_run(
            question=question,
            mode=mode,
            model_name=model_name,
            provider=provider,
            max_steps=max_steps,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            tool_catalog_version=tool_catalog_version,
            model_config=model_config,
            requested_think=requested_think,
            mes_run_id=mes_run_id,
        )
        self._upsert_record(record)
        self._enforce_persistent_retention()
        return record

    def complete_run(
        self,
        agent_run_id: str,
        *,
        status: str,
        answer: str,
        tool_calls: list[Dict[str, Any]],
        agent_trace: list[Dict[str, Any]],
        duration_ms: int,
        visual_artifacts: list[Dict[str, Any]] | None = None,
    ) -> None:
        super().complete_run(
            agent_run_id,
            status=status,
            answer=answer,
            tool_calls=tool_calls,
            agent_trace=agent_trace,
            duration_ms=duration_ms,
            visual_artifacts=visual_artifacts,
        )
        self._upsert_record(self._records[str(agent_run_id)])

    def fail_run(
        self,
        agent_run_id: str,
        *,
        error: str,
        duration_ms: int,
    ) -> None:
        super().fail_run(agent_run_id, error=error, duration_ms=duration_ms)
        self._upsert_record(self._records[str(agent_run_id)])

    def _init_schema(self) -> None:
        with self._db_lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_runs (
                    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_run_id TEXT UNIQUE NOT NULL,
                    mes_run_id TEXT,
                    created_at TEXT,
                    completed_at TEXT,
                    status TEXT,
                    mode TEXT,
                    provider TEXT,
                    model_name TEXT,
                    question TEXT,
                    duration_ms INTEGER,
                    payload TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_runs_created
                ON agent_runs(created_at)
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_runs_mes_run
                ON agent_runs(mes_run_id)
                """
            )
            self._conn.commit()

    def _load_records(self) -> None:
        with self._db_lock:
            rows = self._conn.execute(
                """
                SELECT payload
                FROM agent_runs
                ORDER BY row_id ASC
                """
            ).fetchall()
        for row in rows:
            record = _record_from_payload(json.loads(row["payload"]))
            self._records[record.agent_run_id] = record
            self._order.append(record.agent_run_id)
        self._enforce_retention()

    def _upsert_record(self, record: AgentRunRecord) -> None:
        payload = record.to_dict(include_steps=True)
        with self._db_lock:
            self._conn.execute(
                """
                INSERT INTO agent_runs(
                    agent_run_id, mes_run_id, created_at, completed_at, status,
                    mode, provider, model_name, question, duration_ms, payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_run_id) DO UPDATE SET
                    mes_run_id = excluded.mes_run_id,
                    completed_at = excluded.completed_at,
                    status = excluded.status,
                    mode = excluded.mode,
                    provider = excluded.provider,
                    model_name = excluded.model_name,
                    question = excluded.question,
                    duration_ms = excluded.duration_ms,
                    payload = excluded.payload
                """,
                (
                    record.agent_run_id,
                    record.mes_run_id,
                    record.created_at,
                    record.completed_at,
                    record.status,
                    record.mode,
                    record.provider,
                    record.model_name,
                    record.question,
                    record.duration_ms,
                    _json(payload),
                ),
            )
            self._conn.commit()

    def _enforce_persistent_retention(self) -> None:
        with self._db_lock:
            rows = self._conn.execute(
                """
                SELECT agent_run_id
                FROM agent_runs
                ORDER BY row_id DESC
                LIMIT -1 OFFSET ?
                """,
                (self.max_records,),
            ).fetchall()
            old_ids = [row["agent_run_id"] for row in rows]
            if old_ids:
                self._conn.executemany(
                    "DELETE FROM agent_runs WHERE agent_run_id = ?",
                    [(agent_run_id,) for agent_run_id in old_ids],
                )
                self._conn.commit()


def _record_from_payload(payload: Dict[str, Any]) -> AgentRunRecord:
    metadata = dict(payload.get("metadata", {}) or {})
    return AgentRunRecord(
        agent_run_id=str(payload.get("agent_run_id", "")),
        question=str(payload.get("question", "")),
        mode=str(payload.get("mode", "")),
        model_name=str(metadata.get("model_name", "")),
        provider=str(metadata.get("provider", "")),
        max_steps=int(metadata.get("max_steps", 0) or 0),
        prompt_id=str(metadata.get("prompt_id", "")),
        prompt_version=str(metadata.get("prompt_version", "")),
        tool_catalog_version=str(metadata.get("tool_catalog_version", "")),
        model_config=dict(metadata.get("model_config", {}) or {}),
        requested_think=bool(metadata.get("requested_think", False)),
        mes_run_id=str(payload.get("mes_run_id", "")),
        status=str(payload.get("status", "running")),
        answer=str(payload.get("answer", "")),
        tool_calls=[dict(item) for item in payload.get("tool_calls", [])],
        agent_trace=[dict(item) for item in payload.get("agent_trace", [])],
        visual_artifacts=[
            dict(item) for item in payload.get("visual_artifacts", [])
        ],
        created_at=str(payload.get("created_at", "")),
        completed_at=str(payload.get("completed_at", "")),
        duration_ms=int(payload.get("duration_ms", 0) or 0),
    )


def _json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
