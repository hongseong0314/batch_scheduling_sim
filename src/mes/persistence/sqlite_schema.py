# -*- coding: utf-8 -*-
"""SQLite schema helpers for MES persistence."""

from __future__ import annotations


SCHEMA_VERSION = "legacy_ingestion_v1"
TABLES = {
    "lots": "lot_id",
    "wafers": "wafer_id",
    "equipment": "equipment_id",
    "recipes": "recipe_id",
    "source_key_mappings": "mapping_id",
    "legacy_decisions": "decision_id",
    "outcome_records": "outcome_id",
    "raw_source_records": "record_id",
    "canonical_ingestion_records": "record_id",
    "feature_snapshots": "feature_snapshot_id",
    "recommendations": "recommendation_id",
    "commands": "command_id",
    "validations": "",
    "events": "",
}
INDEX_TABLES = (
    "run_index",
    "task_index",
    "lot_index",
    "assignment_index",
    "equipment_timeline_index",
    "command_ledger_index",
    "event_ledger_index",
    "state_snapshot_index",
    "genealogy_edge_index",
    "source_key_mapping_index",
    "proposal_lifecycle_index",
    "raw_source_record_index",
    "canonical_ingestion_index",
)


class SQLiteSchemaMixin:
    """Schema constants and DDL for SQLite-backed stores."""

    SCHEMA_VERSION = SCHEMA_VERSION
    TABLES = TABLES
    INDEX_TABLES = INDEX_TABLES

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        for table in self.TABLES:
            self._conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT,
                    correlation_id TEXT,
                    payload TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_corr ON {table}(correlation_id)"
            )
            self._conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_record ON {table}(record_id)"
            )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_index (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT UNIQUE NOT NULL,
                start_time INTEGER,
                reason TEXT,
                status TEXT,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_index (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                task_uid INTEGER NOT NULL,
                wafer_id TEXT,
                lot_id TEXT,
                latest_location TEXT,
                time INTEGER,
                payload TEXT NOT NULL,
                UNIQUE(run_id, task_uid)
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lot_index (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                lot_id TEXT NOT NULL,
                task_count INTEGER,
                payload TEXT NOT NULL,
                UNIQUE(run_id, lot_id)
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS assignment_index (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                command_id TEXT NOT NULL,
                correlation_id TEXT,
                candidate_id TEXT,
                stage TEXT,
                equipment_id TEXT,
                task_uid INTEGER,
                task_uids TEXT,
                start_time INTEGER,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS equipment_timeline_index (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                equipment_id TEXT,
                time INTEGER,
                event_type TEXT,
                command_id TEXT,
                correlation_id TEXT,
                task_uids TEXT,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS command_ledger_index (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                command_id TEXT UNIQUE NOT NULL,
                correlation_id TEXT,
                status TEXT,
                validation_status TEXT,
                equipment_id TEXT,
                stage TEXT,
                task_uids TEXT,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS event_ledger_index (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                event_id TEXT UNIQUE NOT NULL,
                correlation_id TEXT,
                event_type TEXT,
                actor_type TEXT,
                equipment_id TEXT,
                operation_id TEXT,
                time INTEGER,
                task_uids TEXT,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS state_snapshot_index (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                snapshot_id TEXT UNIQUE NOT NULL,
                source TEXT,
                correlation_id TEXT,
                layer_id TEXT,
                time INTEGER,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS genealogy_edge_index (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                parent_type TEXT,
                parent_id TEXT,
                child_type TEXT,
                child_id TEXT,
                operation_id TEXT,
                equipment_id TEXT,
                event_id TEXT,
                correlation_id TEXT,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS source_key_mapping_index (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                mapping_id TEXT UNIQUE NOT NULL,
                source_system TEXT NOT NULL,
                source_table TEXT NOT NULL,
                source_pk TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                canonical_id TEXT NOT NULL,
                status TEXT,
                ingest_time INTEGER,
                event_time INTEGER,
                decision_time INTEGER,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS proposal_lifecycle_index (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                proposal_id TEXT NOT NULL,
                record_type TEXT NOT NULL,
                record_id TEXT NOT NULL,
                correlation_id TEXT,
                status TEXT,
                event_time INTEGER,
                payload TEXT NOT NULL,
                UNIQUE(record_type, record_id)
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_source_record_index (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                record_id TEXT UNIQUE NOT NULL,
                source_system TEXT NOT NULL,
                source_table TEXT NOT NULL,
                source_pk TEXT NOT NULL,
                source_key TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                operation_id TEXT,
                equipment_id TEXT,
                lot_id TEXT,
                unit_id TEXT,
                recipe_id TEXT,
                status TEXT,
                ingest_time INTEGER,
                event_time INTEGER,
                decision_time INTEGER,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS canonical_ingestion_index (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                record_id TEXT UNIQUE NOT NULL,
                raw_record_id TEXT,
                entity_type TEXT NOT NULL,
                canonical_id TEXT NOT NULL,
                operation_id TEXT,
                equipment_id TEXT,
                lot_id TEXT,
                unit_id TEXT,
                recipe_id TEXT,
                event_type TEXT,
                ingest_time INTEGER,
                event_time INTEGER,
                decision_time INTEGER,
                payload TEXT NOT NULL
            )
            """
        )
        for table in self.INDEX_TABLES:
            self._conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_run ON {table}(run_id)"
            )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_source_key_mapping_lookup
            ON source_key_mapping_index(source_system, source_table, source_pk, entity_type)
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_proposal_lifecycle_proposal
            ON proposal_lifecycle_index(proposal_id, record_type)
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_raw_source_record_lookup
            ON raw_source_record_index(source_system, source_table, source_pk, entity_type)
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_canonical_ingestion_lookup
            ON canonical_ingestion_index(canonical_id, entity_type)
            """
        )
        self._conn.commit()

    def _table_exists(self, table: str) -> bool:
        with self._db_lock:
            row = self._conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = ?
                """,
                (table,),
            ).fetchone()
        return row is not None

    def _schema_version(self) -> str:
        with self._db_lock:
            row = self._conn.execute(
                "SELECT value FROM schema_meta WHERE key = 'schema_version'"
            ).fetchone()
        return str(row["value"]) if row else ""

    def _set_schema_version(self, version: str) -> None:
        with self._db_lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO schema_meta(key, value)
                VALUES ('schema_version', ?)
                """,
                (version,),
            )
            self._conn.commit()
