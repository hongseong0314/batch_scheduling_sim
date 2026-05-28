# -*- coding: utf-8 -*-
"""Normalized ledger index helpers for SQLite MES persistence."""

from __future__ import annotations

from typing import Any, Dict, List

from src.mes.domain import Event, MESCommand


class SQLiteLedgerIndexMixin:
    """Maintain run-scoped normalized indexes beside JSON audit records."""

    def _index_command(self, command: MESCommand) -> None:
        payload = command.to_dict()
        validated = dict(command.validated_command or {})
        task_uids = [int(uid) for uid in validated.get("task_uids", [])]
        stage = str(validated.get("stage") or self._stage_from_equipment(validated.get("equipment_id")))
        with self._db_lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO command_ledger_index(
                    run_id, command_id, correlation_id, status, validation_status,
                    equipment_id, stage, task_uids, payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    command.run_id,
                    command.command_id,
                    command.correlation_id,
                    command.status,
                    command.validation_status,
                    validated.get("equipment_id"),
                    stage,
                    self._json(task_uids),
                    self._json(payload),
                ),
            )
            self._conn.execute(
                "DELETE FROM assignment_index WHERE command_id = ?",
                (command.command_id,),
            )
            for uid in task_uids:
                row = {
                    "run_id": command.run_id,
                    "command_id": command.command_id,
                    "correlation_id": command.correlation_id,
                    "candidate_id": validated.get("candidate_id"),
                    "stage": stage,
                    "equipment_id": validated.get("equipment_id"),
                    "task_uid": uid,
                    "task_uids": task_uids,
                    "start_time": validated.get("start_time", 0),
                    "command": payload,
                }
                self._conn.execute(
                    """
                    INSERT INTO assignment_index(
                        run_id, command_id, correlation_id, candidate_id, stage,
                        equipment_id, task_uid, task_uids, start_time, payload
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["run_id"],
                        row["command_id"],
                        row["correlation_id"],
                        row["candidate_id"],
                        row["stage"],
                        row["equipment_id"],
                        row["task_uid"],
                        self._json(task_uids),
                        int(row["start_time"] or 0),
                        self._json(row),
                    ),
                )
                self._index_genealogy_edge(
                    run_id=command.run_id,
                    parent_type="TASK",
                    parent_id=str(uid),
                    child_type="COMMAND",
                    child_id=command.command_id,
                    operation_id=stage,
                    equipment_id=str(validated.get("equipment_id") or ""),
                    event_id="",
                    correlation_id=command.correlation_id,
                    payload=row,
                )
            self._conn.commit()

    def _index_event(self, event: Event) -> None:
        payload = event.to_dict()
        task_uids = self._task_uids_from_event_payload(payload)
        event_time = self._event_time_from_payload(payload)
        with self._db_lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO event_ledger_index(
                    run_id, event_id, correlation_id, event_type, actor_type,
                    equipment_id, operation_id, time, task_uids, payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.run_id,
                    event.event_id,
                    event.correlation_id,
                    event.event_type,
                    event.actor_type,
                    event.equipment_id,
                    event.operation_id,
                    event_time,
                    self._json(task_uids),
                    self._json(payload),
                ),
            )
            if event.equipment_id:
                self._conn.execute(
                    """
                    INSERT INTO equipment_timeline_index(
                        run_id, equipment_id, time, event_type, command_id,
                        correlation_id, task_uids, payload
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.run_id,
                        event.equipment_id,
                        event_time,
                        event.event_type,
                        self._command_id_from_event_payload(payload),
                        event.correlation_id,
                        self._json(task_uids),
                        self._json(payload),
                    ),
                )
            for uid in task_uids:
                self._index_genealogy_edge(
                    run_id=event.run_id,
                    parent_type="TASK",
                    parent_id=str(uid),
                    child_type="EVENT",
                    child_id=event.event_id,
                    operation_id=str(event.operation_id or ""),
                    equipment_id=str(event.equipment_id or ""),
                    event_id=event.event_id,
                    correlation_id=event.correlation_id,
                    payload=payload,
                )
            self._conn.commit()

    def _index_proposal_lifecycle(
        self,
        run_id: str,
        proposal_id: str,
        record_type: str,
        record_id: str,
        correlation_id: str,
        status: str,
        event_time: Any,
        payload: Dict[str, Any],
    ) -> None:
        with self._db_lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO proposal_lifecycle_index(
                    run_id, proposal_id, record_type, record_id, correlation_id,
                    status, event_time, payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    proposal_id,
                    record_type,
                    record_id,
                    correlation_id,
                    status,
                    int(event_time) if event_time is not None else None,
                    self._json(payload),
                ),
            )
            self._conn.commit()

    def _index_tasks_and_lots(self, run_id: str, decision_state: Dict[str, Any]) -> None:
        tasks = decision_state.get("tasks", {}) or {}
        lot_counts: Dict[str, int] = {}
        for row in tasks.values():
            if not isinstance(row, dict):
                continue
            uid = row.get("uid")
            if uid is None:
                continue
            task_uid = int(uid)
            lot_id = str(row.get("job_id") or "")
            lot_counts[lot_id] = lot_counts.get(lot_id, 0) + 1
            self._conn.execute(
                """
                INSERT OR REPLACE INTO task_index(
                    run_id, task_uid, wafer_id, lot_id, latest_location, time, payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    task_uid,
                    f"WAFER_{task_uid}",
                    lot_id,
                    str(row.get("location") or ""),
                    int(decision_state.get("time", 0) or 0),
                    self._json(row),
                ),
            )
        for lot_id, task_count in lot_counts.items():
            payload = {
                "run_id": run_id,
                "lot_id": lot_id,
                "task_count": task_count,
            }
            self._conn.execute(
                """
                INSERT OR REPLACE INTO lot_index(run_id, lot_id, task_count, payload)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, lot_id, task_count, self._json(payload)),
            )

    def _index_genealogy_edge(
        self,
        run_id: str,
        parent_type: str,
        parent_id: str,
        child_type: str,
        child_id: str,
        operation_id: str,
        equipment_id: str,
        event_id: str,
        correlation_id: str,
        payload: Dict[str, Any],
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO genealogy_edge_index(
                run_id, parent_type, parent_id, child_type, child_id,
                operation_id, equipment_id, event_id, correlation_id, payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                parent_type,
                parent_id,
                child_type,
                child_id,
                operation_id,
                equipment_id,
                event_id,
                correlation_id,
                self._json(payload),
            ),
        )

    def _stage_from_equipment(self, equipment_id: Any) -> str:
        if not equipment_id:
            return ""
        first = str(equipment_id)[0].upper()
        return first if first in {"A", "B", "C"} else ""

    def _event_time_from_payload(self, event_payload: Dict[str, Any]) -> int:
        payload = dict(event_payload.get("payload") or {})
        if payload.get("post_time") is not None:
            return int(payload.get("post_time") or 0)
        command = dict(payload.get("command") or {})
        validated = dict(command.get("validated_command") or {})
        if validated.get("start_time") is not None:
            return int(validated.get("start_time") or 0)
        return 0

    def _command_id_from_event_payload(self, event_payload: Dict[str, Any]) -> str:
        payload = dict(event_payload.get("payload") or {})
        command = dict(payload.get("command") or {})
        return str(command.get("command_id") or payload.get("command_id") or "")

    def _task_uids_from_event_payload(self, event_payload: Dict[str, Any]) -> List[int]:
        payload = dict(event_payload.get("payload") or {})
        candidates: List[Any] = []
        for source in (
            payload,
            dict(payload.get("recommended_action") or {}),
            dict(payload.get("validation", {}).get("validated_command") or {}),
            dict(payload.get("command", {}).get("validated_command") or {}),
        ):
            values = source.get("task_uids")
            if isinstance(values, list):
                candidates.extend(values)
        for wafer_id in event_payload.get("wafer_ids") or []:
            suffix = str(wafer_id).split("_")[-1]
            if suffix.isdigit():
                candidates.append(int(suffix))
        return sorted({int(uid) for uid in candidates if str(uid).isdigit()})
