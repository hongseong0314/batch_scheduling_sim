# -*- coding: utf-8 -*-
"""SQLite JSON record helpers for MES persistence."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, Iterable, List, Optional

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


class SQLiteRecordMixin:
    """JSON record persistence and cache loading helpers."""

    def normalized_index_counts(self, run_id: Optional[str] = None) -> Dict[str, int]:
        return {
            table: self._count_table(table, run_id=run_id)
            for table in self.INDEX_TABLES
        }

    def normalized_index_rows(
        self,
        index_name: str,
        run_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        name = str(index_name)
        if name not in self.INDEX_TABLES:
            raise ValueError(f"unknown ledger index: {name}")
        limit = max(1, min(1000, int(limit)))
        with self._db_lock:
            if run_id is None:
                rows = self._conn.execute(
                    f"""
                    SELECT *
                    FROM {name}
                    ORDER BY row_id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    f"""
                    SELECT *
                    FROM {name}
                    WHERE run_id = ?
                    ORDER BY row_id DESC
                    LIMIT ?
                    """,
                    (run_id, limit),
                ).fetchall()
        return [self._index_row_to_dict(row) for row in reversed(rows)]

    def runs(self) -> List[Dict[str, Any]]:
        with self._db_lock:
            rows = self._conn.execute(
                """
                SELECT payload
                FROM run_index
                ORDER BY row_id ASC
                """
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def _load_cache(self) -> None:
        self._runs = self.runs()
        for payload in self._rows("lots", limit=self.cache_limit):
            lot = Lot(**payload)
            self._lots[lot.lot_id] = lot
        for payload in self._rows("wafers", limit=self.cache_limit):
            wafer = Wafer(**payload)
            self._wafers[wafer.wafer_id] = wafer
        for payload in self._rows("equipment", limit=self.cache_limit):
            equipment = Equipment(**payload)
            self._equipment[equipment.equipment_id] = equipment
        for payload in self._rows("recipes", limit=self.cache_limit):
            recipe = Recipe(**payload)
            self._recipes[recipe.recipe_id] = recipe
        for payload in self._rows("feature_snapshots", limit=self.cache_limit):
            snapshot = FeatureSnapshot(**payload)
            self._feature_snapshots[snapshot.feature_snapshot_id] = snapshot
        for payload in self._rows("recommendations", limit=self.cache_limit):
            recommendation = AIRecommendation(**payload)
            self._recommendations[recommendation.recommendation_id] = recommendation
        for payload in self._rows("validations", limit=self.cache_limit):
            self._validations.append(RuleValidationResult(**payload))
        for payload in self._rows("commands", limit=self.cache_limit):
            command = MESCommand(**payload)
            self._commands[command.command_id] = command
        for payload in self._rows("events", limit=self.cache_limit):
            self._events.append(Event(**payload))

    def _rows(
        self,
        table: str,
        limit: Optional[int] = None,
    ) -> Iterable[Dict[str, Any]]:
        if limit is not None and limit > 0:
            with self._db_lock:
                rows = self._conn.execute(
                    f"""
                    SELECT payload FROM (
                        SELECT row_id, payload
                        FROM {table}
                        ORDER BY row_id DESC
                        LIMIT ?
                    )
                    ORDER BY row_id ASC
                    """,
                    (int(limit),),
                ).fetchall()
            for row in rows:
                yield json.loads(row["payload"])
            return

        with self._db_lock:
            rows = self._conn.execute(
                f"SELECT payload FROM {table} ORDER BY row_id ASC"
            ).fetchall()
        for row in rows:
            yield json.loads(row["payload"])

    def _count_table(self, table: str, run_id: Optional[str] = None) -> int:
        with self._db_lock:
            if run_id is None:
                row = self._conn.execute(
                    f"SELECT COUNT(*) AS count FROM {table}"
                ).fetchone()
            else:
                row = self._conn.execute(
                    f"SELECT COUNT(*) AS count FROM {table} WHERE run_id = ?",
                    (run_id,),
                ).fetchone()
        return int(row["count"] if row else 0)

    def _index_row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        item = {key: row[key] for key in row.keys()}
        payload = item.get("payload")
        if isinstance(payload, str):
            try:
                item["payload"] = json.loads(payload)
            except json.JSONDecodeError:
                item["payload"] = payload
        for key in ("task_uids",):
            value = item.get(key)
            if isinstance(value, str):
                try:
                    item[key] = json.loads(value)
                except json.JSONDecodeError:
                    item[key] = value
        return item

    def _json(self, payload: Any) -> str:
        return json.dumps(payload, sort_keys=True)

    def _upsert(
        self,
        table: str,
        record_id: str,
        correlation_id: str,
        payload: Dict[str, Any],
    ) -> None:
        with self._db_lock:
            existing = self._conn.execute(
                f"SELECT row_id FROM {table} WHERE record_id = ? ORDER BY row_id DESC LIMIT 1",
                (record_id,),
            ).fetchone()
            data = json.dumps(payload, sort_keys=True)
            if existing is None:
                self._insert(table, record_id, correlation_id, payload)
                return
            self._conn.execute(
                f"""
                UPDATE {table}
                SET correlation_id = ?, payload = ?
                WHERE row_id = ?
                """,
                (correlation_id, data, existing["row_id"]),
            )
            self._conn.commit()

    def _insert(
        self,
        table: str,
        record_id: Optional[str],
        correlation_id: str,
        payload: Dict[str, Any],
    ) -> None:
        with self._db_lock:
            self._conn.execute(
                f"""
                INSERT INTO {table}(record_id, correlation_id, payload)
                VALUES (?, ?, ?)
                """,
                (record_id, correlation_id, json.dumps(payload, sort_keys=True)),
            )
            self._conn.commit()

