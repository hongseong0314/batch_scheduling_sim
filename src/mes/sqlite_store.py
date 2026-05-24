# -*- coding: utf-8 -*-
"""SQLite-backed MES audit store.

This keeps the same public surface as ``InMemoryMESStore`` while adding a local
database for the FastAPI MVP. JSON record persistence, schema DDL, and
normalized ledger indexing live in focused persistence mixins.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from src.mes.domain import (
    AIRecommendation,
    Equipment,
    Event,
    FeatureSnapshot,
    Lot,
    MESCommand,
    Recipe,
    RuleValidationResult,
    Wafer,
)
from src.mes.persistence.sqlite_ledger_index import SQLiteLedgerIndexMixin
from src.mes.persistence.sqlite_records import SQLiteRecordMixin
from src.mes.persistence.sqlite_schema import SQLiteSchemaMixin
from src.mes.store import InMemoryMESStore


class SQLiteMESStore(
    SQLiteLedgerIndexMixin,
    SQLiteRecordMixin,
    SQLiteSchemaMixin,
    InMemoryMESStore,
):
    """Write-through SQLite store with an in-memory query cache."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.cache_limit = int(os.environ.get("MES_STORE_CACHE_LIMIT", "5000"))
        self._db_lock = threading.RLock()
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        super().__init__()
        legacy = not self._table_exists("schema_meta")
        self._init_schema()
        if legacy or self._schema_version() != self.SCHEMA_VERSION:
            self.clear_all_persistent_state()
            self._set_schema_version(self.SCHEMA_VERSION)
        self._load_cache()

    def start_run(
        self,
        run_id: str,
        reason: str = "startup",
        time: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        row = super().start_run(run_id, reason=reason, time=time, metadata=metadata)
        payload = dict(row)
        with self._db_lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO run_index(run_id, start_time, reason, status, payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    payload["run_id"],
                    int(payload.get("start_time", 0) or 0),
                    payload.get("reason", ""),
                    payload.get("status", "ACTIVE"),
                    self._json(payload),
                ),
            )
            self._conn.commit()
        return row

    def add_feature_snapshot(self, snapshot: FeatureSnapshot) -> None:
        super().add_feature_snapshot(snapshot)
        self._upsert(
            "feature_snapshots",
            snapshot.feature_snapshot_id,
            snapshot.correlation_id,
            snapshot.to_dict(),
        )
        self.record_state_snapshot(
            source=f"feature_snapshot:{snapshot.layer_id}",
            decision_state=snapshot.decision_state,
            correlation_id=snapshot.correlation_id,
            layer_id=snapshot.layer_id,
            snapshot_id=snapshot.feature_snapshot_id,
            run_id=snapshot.run_id,
        )

    def add_recommendation(self, recommendation: AIRecommendation) -> None:
        super().add_recommendation(recommendation)
        self._upsert(
            "recommendations",
            recommendation.recommendation_id,
            recommendation.correlation_id,
            recommendation.to_dict(),
        )

    def add_validation(self, validation: RuleValidationResult) -> None:
        super().add_validation(validation)
        self._insert(
            "validations",
            None,
            validation.correlation_id,
            validation.to_dict(),
        )

    def add_command(self, command: MESCommand) -> None:
        super().add_command(command)
        self._upsert(
            "commands",
            command.command_id,
            command.correlation_id,
            command.to_dict(),
        )
        self._index_command(command)

    def add_event(self, event: Event) -> None:
        super().add_event(event)
        self._insert("events", event.event_id, event.correlation_id, event.to_dict())
        self._index_event(event)

    def upsert_lot(self, lot: Lot) -> None:
        super().upsert_lot(lot)
        self._upsert("lots", lot.lot_id, "", lot.to_dict())

    def upsert_wafer(self, wafer: Wafer) -> None:
        super().upsert_wafer(wafer)
        self._upsert("wafers", wafer.wafer_id, "", wafer.to_dict())

    def upsert_equipment(self, equipment: Equipment) -> None:
        super().upsert_equipment(equipment)
        self._upsert("equipment", equipment.equipment_id, "", equipment.to_dict())

    def upsert_recipe(self, recipe: Recipe) -> None:
        super().upsert_recipe(recipe)
        self._upsert("recipes", recipe.recipe_id, "", recipe.to_dict())

    def clear_runtime_state(self) -> None:
        super().clear_runtime_state()
        with self._db_lock:
            for table in ("lots", "wafers", "equipment", "recipes"):
                self._conn.execute(f"DELETE FROM {table}")
            self._conn.commit()

    def clear_audit_state(self) -> None:
        super().clear_audit_state()
        with self._db_lock:
            for table in (
                "feature_snapshots",
                "recommendations",
                "commands",
                "validations",
                "events",
            ):
                self._conn.execute(f"DELETE FROM {table}")
            for table in self.INDEX_TABLES:
                self._conn.execute(f"DELETE FROM {table}")
            self._conn.commit()

    def clear_all_persistent_state(self) -> None:
        super().clear_runtime_state()
        super().clear_audit_state()
        with self._db_lock:
            for table in tuple(self.TABLES) + self.INDEX_TABLES:
                self._conn.execute(f"DELETE FROM {table}")
            self._conn.commit()

    def record_command_executed(
        self,
        command_id: str,
        step_result: Optional[Dict[str, Any]] = None,
        post_decision_state: Optional[Dict[str, Any]] = None,
    ) -> Optional[MESCommand]:
        command = super().record_command_executed(
            command_id,
            step_result=step_result,
            post_decision_state=post_decision_state,
        )
        if command is not None:
            self._upsert(
                "commands",
                command.command_id,
                command.correlation_id,
                command.to_dict(),
            )
            self._index_command(command)
        return command

    def record_state_snapshot(
        self,
        source: str,
        decision_state: Dict[str, Any],
        correlation_id: str = "",
        layer_id: str = "",
        snapshot_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        row = super().record_state_snapshot(
            source=source,
            decision_state=decision_state,
            correlation_id=correlation_id,
            layer_id=layer_id,
            snapshot_id=snapshot_id,
            run_id=run_id,
        )
        with self._db_lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO state_snapshot_index(
                    run_id, snapshot_id, source, correlation_id, layer_id, time, payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["run_id"],
                    row["snapshot_id"],
                    row["source"],
                    row["correlation_id"],
                    row["layer_id"],
                    row["time"],
                    self._json(row),
                ),
            )
            self._index_tasks_and_lots(row["run_id"], decision_state)
            self._conn.commit()
        return row
