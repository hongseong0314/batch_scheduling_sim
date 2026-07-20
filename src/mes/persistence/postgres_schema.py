# -*- coding: utf-8 -*-
"""PostgreSQL DDL contract for the production data backbone."""

from __future__ import annotations

from typing import Any, Dict, List


POSTGRES_SCHEMA_VERSION = "production_data_backbone_v1"
MIGRATION_FILES = [
    "src/mes/persistence/migrations/postgres/001_production_data_backbone_v1.sql"
]


TABLES: Dict[str, Dict[str, Any]] = {
    "raw_source_records": {
        "purpose": "Immutable source evidence from MES/FDC/RMS/ERP.",
        "columns": {
            "record_id": {"type": "TEXT", "nullable": False, "primary_key": True},
            "run_id": {"type": "TEXT", "nullable": False},
            "source_system": {"type": "TEXT", "nullable": False},
            "source_table": {"type": "TEXT", "nullable": False},
            "source_pk": {"type": "TEXT", "nullable": False},
            "entity_type": {"type": "TEXT", "nullable": False},
            "operation_id": {"type": "TEXT", "nullable": False, "default": "''"},
            "equipment_id": {"type": "TEXT", "nullable": False, "default": "''"},
            "lot_id": {"type": "TEXT", "nullable": False, "default": "''"},
            "unit_id": {"type": "TEXT", "nullable": False, "default": "''"},
            "recipe_id": {"type": "TEXT", "nullable": False, "default": "''"},
            "event_time": {"type": "BIGINT", "nullable": True},
            "ingest_time": {"type": "BIGINT", "nullable": True},
            "decision_time": {"type": "BIGINT", "nullable": True},
            "schema_version": {"type": "TEXT", "nullable": False},
            "status": {"type": "TEXT", "nullable": False},
            "payload": {"type": "JSONB", "nullable": False, "default": "'{}'::jsonb"},
            "metadata": {"type": "JSONB", "nullable": False, "default": "'{}'::jsonb"},
        },
    },
    "canonical_ingestion_records": {
        "purpose": "Standardized append-only event records replayed into the digital twin.",
        "columns": {
            "record_id": {"type": "TEXT", "nullable": False, "primary_key": True},
            "run_id": {"type": "TEXT", "nullable": False},
            "raw_record_id": {"type": "TEXT", "nullable": False},
            "entity_type": {"type": "TEXT", "nullable": False},
            "canonical_id": {"type": "TEXT", "nullable": False},
            "canonical_namespace": {"type": "TEXT", "nullable": False},
            "operation_id": {"type": "TEXT", "nullable": False, "default": "''"},
            "equipment_id": {"type": "TEXT", "nullable": False, "default": "''"},
            "lot_id": {"type": "TEXT", "nullable": False, "default": "''"},
            "unit_id": {"type": "TEXT", "nullable": False, "default": "''"},
            "recipe_id": {"type": "TEXT", "nullable": False, "default": "''"},
            "event_type": {"type": "TEXT", "nullable": False, "default": "''"},
            "event_time": {"type": "BIGINT", "nullable": True},
            "ingest_time": {"type": "BIGINT", "nullable": True},
            "decision_time": {"type": "BIGINT", "nullable": True},
            "attributes": {"type": "JSONB", "nullable": False, "default": "'{}'::jsonb"},
            "measurements": {"type": "JSONB", "nullable": False, "default": "'{}'::jsonb"},
            "quality_result": {"type": "JSONB", "nullable": False, "default": "'{}'::jsonb"},
            "payload": {"type": "JSONB", "nullable": False, "default": "'{}'::jsonb"},
            "schema_version": {"type": "TEXT", "nullable": False},
        },
    },
    "source_key_mappings": {
        "purpose": "Maps legacy source keys to stable AI MES canonical ids.",
        "columns": {
            "mapping_id": {"type": "TEXT", "nullable": False, "primary_key": True},
            "run_id": {"type": "TEXT", "nullable": False},
            "source_system": {"type": "TEXT", "nullable": False},
            "source_table": {"type": "TEXT", "nullable": False},
            "source_pk": {"type": "TEXT", "nullable": False},
            "entity_type": {"type": "TEXT", "nullable": False},
            "canonical_namespace": {"type": "TEXT", "nullable": False},
            "canonical_id": {"type": "TEXT", "nullable": False},
            "status": {"type": "TEXT", "nullable": False},
            "event_time": {"type": "BIGINT", "nullable": True},
            "ingest_time": {"type": "BIGINT", "nullable": True},
            "decision_time": {"type": "BIGINT", "nullable": True},
            "source_payload": {"type": "JSONB", "nullable": False, "default": "'{}'::jsonb"},
            "metadata": {"type": "JSONB", "nullable": False, "default": "'{}'::jsonb"},
        },
    },
    "action_proposals": {
        "purpose": "AI MES recommendation intents submitted to legacy review boundary.",
        "columns": {
            "proposal_id": {"type": "TEXT", "nullable": False, "primary_key": True},
            "run_id": {"type": "TEXT", "nullable": False},
            "correlation_id": {"type": "TEXT", "nullable": False},
            "proposal_type": {"type": "TEXT", "nullable": False},
            "status": {"type": "TEXT", "nullable": False},
            "direct_equipment_control": {"type": "BOOLEAN", "nullable": False},
            "decision_time": {"type": "BIGINT", "nullable": True},
            "payload": {"type": "JSONB", "nullable": False, "default": "'{}'::jsonb"},
        },
    },
    "action_proposal_reviews": {
        "purpose": "Human or system review records for action proposals.",
        "columns": {
            "review_id": {"type": "TEXT", "nullable": False, "primary_key": True},
            "proposal_id": {"type": "TEXT", "nullable": False},
            "run_id": {"type": "TEXT", "nullable": False},
            "correlation_id": {"type": "TEXT", "nullable": False},
            "review_status": {"type": "TEXT", "nullable": False},
            "reviewer_id": {"type": "TEXT", "nullable": False, "default": "''"},
            "reviewed_at": {"type": "BIGINT", "nullable": True},
            "payload": {"type": "JSONB", "nullable": False, "default": "'{}'::jsonb"},
        },
    },
    "legacy_decisions": {
        "purpose": "How legacy MES accepted, rejected, or modified an AI proposal.",
        "columns": {
            "decision_id": {"type": "TEXT", "nullable": False, "primary_key": True},
            "proposal_id": {"type": "TEXT", "nullable": False},
            "run_id": {"type": "TEXT", "nullable": False},
            "correlation_id": {"type": "TEXT", "nullable": False},
            "legacy_status": {"type": "TEXT", "nullable": False},
            "decision_time": {"type": "BIGINT", "nullable": True},
            "payload": {"type": "JSONB", "nullable": False, "default": "'{}'::jsonb"},
        },
    },
    "outcome_records": {
        "purpose": "Observed execution and quality outcomes for policy evaluation.",
        "columns": {
            "outcome_id": {"type": "TEXT", "nullable": False, "primary_key": True},
            "proposal_id": {"type": "TEXT", "nullable": False},
            "run_id": {"type": "TEXT", "nullable": False},
            "correlation_id": {"type": "TEXT", "nullable": False},
            "outcome_status": {"type": "TEXT", "nullable": False},
            "event_time": {"type": "BIGINT", "nullable": True},
            "ingest_time": {"type": "BIGINT", "nullable": True},
            "payload": {"type": "JSONB", "nullable": False, "default": "'{}'::jsonb"},
        },
    },
    "ingestion_job_runs": {
        "purpose": "Execution ledger for scheduled and backfill ingestion jobs.",
        "columns": {
            "job_run_id": {"type": "TEXT", "nullable": False, "primary_key": True},
            "job_id": {"type": "TEXT", "nullable": False},
            "run_id": {"type": "TEXT", "nullable": False},
            "adapter_id": {"type": "TEXT", "nullable": False},
            "mode": {"type": "TEXT", "nullable": False},
            "status": {"type": "TEXT", "nullable": False},
            "window_start": {"type": "BIGINT", "nullable": True},
            "window_end": {"type": "BIGINT", "nullable": True},
            "raw_count": {"type": "INTEGER", "nullable": False, "default": "0"},
            "canonical_count": {"type": "INTEGER", "nullable": False, "default": "0"},
            "error_count": {"type": "INTEGER", "nullable": False, "default": "0"},
            "started_at": {"type": "BIGINT", "nullable": True},
            "finished_at": {"type": "BIGINT", "nullable": True},
            "metadata": {"type": "JSONB", "nullable": False, "default": "'{}'::jsonb"},
        },
    },
}


INDEXES = {
    "idx_raw_source_records_source_key": (
        "raw_source_records",
        ("run_id", "source_system", "source_table", "source_pk", "entity_type"),
    ),
    "idx_canonical_ingestion_entity": (
        "canonical_ingestion_records",
        ("run_id", "entity_type", "canonical_id"),
    ),
    "idx_canonical_ingestion_time": (
        "canonical_ingestion_records",
        ("run_id", "event_time", "ingest_time"),
    ),
    "idx_source_key_mappings_lookup": (
        "source_key_mappings",
        ("run_id", "source_system", "source_table", "source_pk", "entity_type"),
    ),
    "idx_action_proposals_correlation": (
        "action_proposals",
        ("run_id", "correlation_id", "status"),
    ),
    "idx_ingestion_job_runs_adapter": (
        "ingestion_job_runs",
        ("run_id", "adapter_id", "status"),
    ),
}


def postgres_schema_contract() -> Dict[str, Any]:
    return {
        "schema_version": POSTGRES_SCHEMA_VERSION,
        "storage_target": "postgresql",
        "migration_files": list(MIGRATION_FILES),
        "tables": TABLES,
        "indexes": {
            name: {"table": table, "columns": list(columns)}
            for name, (table, columns) in INDEXES.items()
        },
        "invariants": [
            "Raw source records are immutable evidence.",
            "Canonical ingestion records are append-only replay inputs.",
            "Source key mappings preserve source-to-canonical identity.",
            "Action proposals are recommendation intents, not direct equipment control.",
            "Ingestion job runs are auditable and repeatable.",
        ],
    }


def postgres_ddl_statements() -> List[str]:
    statements: List[str] = []
    for table_name, table in TABLES.items():
        statements.append(_create_table_statement(table_name, table["columns"]))
    for index_name, (table_name, columns) in INDEXES.items():
        joined = ", ".join(columns)
        statements.append(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({joined});"
        )
    return statements


def _create_table_statement(table_name: str, columns: Dict[str, Dict[str, Any]]) -> str:
    definitions = []
    for column_name, spec in columns.items():
        definition = f"{column_name} {spec['type']}"
        if not spec.get("nullable", True):
            definition += " NOT NULL"
        if "default" in spec:
            definition += f" DEFAULT {spec['default']}"
        if spec.get("primary_key"):
            definition += " PRIMARY KEY"
        definitions.append(definition)
    return f"CREATE TABLE IF NOT EXISTS {table_name} (\n  " + ",\n  ".join(definitions) + "\n);"
