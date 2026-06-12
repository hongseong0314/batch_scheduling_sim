# -*- coding: utf-8 -*-
"""Production data contracts and diagnostics for canonical MES ingestion."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence

from src.mes.domain import SourceKeyMapping
from src.mes.ingestion import CanonicalIngestionRecord, RawSourceRecord


PRODUCTION_SCHEMA_VERSION = "canonical-production-data-v1"
SUPPORTED_CANONICAL_ENTITY_TYPES = (
    "LOT",
    "UNIT",
    "WAFER",
    "EQUIPMENT",
    "RECIPE",
    "EVENT",
    "ASSIGNMENT",
    "QUALITY",
)


def canonical_schema_contract(
    sqlite_schema_version: str = "",
    sqlite_tables: Optional[Dict[str, str]] = None,
    normalized_indexes: Optional[Sequence[str]] = None,
    normalized_index_counts: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Return the canonical production data contract used by AI MES V1.

    This is intentionally explicit rather than inferred from the current SQLite
    implementation. SQLite is the MVP persistence layer; the contract is the
    shape we want to preserve when the production target becomes PostgreSQL.
    """
    return {
        "schema_version": PRODUCTION_SCHEMA_VERSION,
        "status": "POSTGRESQL_READY_CONTRACT_DRAFT",
        "storage_target": "postgresql",
        "current_mvp_backend": {
            "backend": "sqlite_json_plus_indexes",
            "schema_version": sqlite_schema_version,
            "tables": dict(sqlite_tables or {}),
            "normalized_indexes": list(normalized_indexes or []),
            "normalized_index_counts": dict(normalized_index_counts or {}),
        },
        "canonical_entity_types": list(SUPPORTED_CANONICAL_ENTITY_TYPES),
        "tables": _table_contracts(),
        "time_semantics": {
            "event_time": "When the manufacturing event occurred in the source system.",
            "ingest_time": "When AI MES received and standardized the source record.",
            "decision_time": "When a policy used the record for a recommendation.",
        },
        "id_semantics": {
            "canonical_id": "Stable AI MES entity id used across legacy source systems.",
            "source_key": "Original legacy key tuple: source_system/source_table/source_pk.",
            "mapping_id": "Stable mapping id for one source key to one canonical entity.",
        },
        "invariants": [
            "Raw source payloads are retained as evidence.",
            "Source keys map to canonical ids before policy execution.",
            "Canonical ids remain stable across ingestion batches.",
            "Event time, ingest time, and decision time are stored separately.",
            "AI MES emits recommendation intents or action proposals, not direct equipment control.",
            "Policy stacks consume canonical decision state, not source-specific table rows.",
        ],
    }


def data_quality_diagnostics(
    raw_records: Iterable[RawSourceRecord],
    canonical_records: Iterable[CanonicalIngestionRecord],
    mappings: Iterable[SourceKeyMapping],
    operation_ids: Optional[Sequence[str]] = None,
    at_time: Optional[int] = None,
) -> Dict[str, Any]:
    """Inspect raw/canonical/mapping records for production data readiness."""
    raw_items = list(raw_records)
    canonical_items = _filter_by_time(list(canonical_records), at_time=at_time)
    mapping_items = list(mappings)
    operations = [str(item) for item in operation_ids or []]
    issues: List[Dict[str, Any]] = []

    _append_duplicate_id_issues(
        issues,
        "DUPLICATE_RAW_RECORD_ID",
        [record.record_id for record in raw_items],
        "raw source record",
    )
    _append_duplicate_id_issues(
        issues,
        "DUPLICATE_CANONICAL_RECORD_ID",
        [record.record_id for record in canonical_items],
        "canonical ingestion record",
    )
    _append_duplicate_id_issues(
        issues,
        "DUPLICATE_SOURCE_MAPPING_ID",
        [mapping.mapping_id for mapping in mapping_items],
        "source key mapping",
    )

    raw_ids = {record.record_id for record in raw_items}
    raw_source_keys = defaultdict(list)
    for record in raw_items:
        raw_source_keys[
            (
                record.run_id,
                record.source_system,
                record.source_table,
                record.source_pk,
                record.entity_type,
            )
        ].append(record.record_id)
        _validate_record_times(
            issues,
            "RAW_RECORD",
            record.record_id,
            record.event_time,
            record.ingest_time,
        )
        if record.entity_type not in SUPPORTED_CANONICAL_ENTITY_TYPES:
            _issue(
                issues,
                "ERROR",
                "UNSUPPORTED_RAW_ENTITY_TYPE",
                f"Raw source record {record.record_id} uses unsupported entity_type={record.entity_type}.",
                record_id=record.record_id,
                entity_type=record.entity_type,
            )

    for source_key, record_ids in raw_source_keys.items():
        if len(record_ids) > 1:
            _issue(
                issues,
                "WARN",
                "DUPLICATE_RAW_SOURCE_KEY",
                "Multiple raw source records share the same source key.",
                source_key=_source_key_from_tuple(source_key),
                record_ids=record_ids,
            )

    mapping_key_to_canonical_ids = defaultdict(set)
    for mapping in mapping_items:
        if mapping.status != "ACTIVE":
            continue
        key = (
            mapping.run_id,
            mapping.source_system,
            mapping.source_table,
            mapping.source_pk,
            mapping.entity_type,
        )
        mapping_key_to_canonical_ids[key].add(mapping.canonical_id)
        _validate_record_times(
            issues,
            "SOURCE_KEY_MAPPING",
            mapping.mapping_id,
            mapping.event_time,
            mapping.ingest_time,
        )
        if not mapping.canonical_id:
            _issue(
                issues,
                "ERROR",
                "MISSING_MAPPING_CANONICAL_ID",
                f"Source key mapping {mapping.mapping_id} has no canonical_id.",
                mapping_id=mapping.mapping_id,
            )

    for key, canonical_ids in mapping_key_to_canonical_ids.items():
        if len(canonical_ids) > 1:
            _issue(
                issues,
                "ERROR",
                "SOURCE_KEY_CANONICAL_CONFLICT",
                "One active source key maps to multiple canonical ids.",
                source_key=_source_key_from_tuple(key),
                canonical_ids=sorted(canonical_ids),
            )

    for record in canonical_items:
        entity_type = record.entity_type.upper()
        if entity_type not in SUPPORTED_CANONICAL_ENTITY_TYPES:
            _issue(
                issues,
                "ERROR",
                "UNSUPPORTED_CANONICAL_ENTITY_TYPE",
                f"Canonical record {record.record_id} uses unsupported entity_type={record.entity_type}.",
                record_id=record.record_id,
                entity_type=record.entity_type,
            )
        if not record.canonical_id:
            _issue(
                issues,
                "ERROR",
                "MISSING_CANONICAL_ID",
                f"Canonical record {record.record_id} has no canonical_id.",
                record_id=record.record_id,
            )
        if not record.raw_record_id:
            _issue(
                issues,
                "WARN",
                "MISSING_RAW_RECORD_REFERENCE",
                f"Canonical record {record.record_id} has no raw_record_id reference.",
                record_id=record.record_id,
                canonical_id=record.canonical_id,
            )
        elif raw_ids and record.raw_record_id not in raw_ids:
            _issue(
                issues,
                "WARN",
                "RAW_RECORD_REFERENCE_NOT_FOUND",
                f"Canonical record {record.record_id} references a missing raw record.",
                record_id=record.record_id,
                raw_record_id=record.raw_record_id,
            )
        _validate_record_times(
            issues,
            "CANONICAL_RECORD",
            record.record_id,
            record.event_time,
            record.ingest_time,
        )
        if entity_type in {"UNIT", "WAFER", "ASSIGNMENT", "QUALITY"} and not record.operation_id:
            _issue(
                issues,
                "WARN",
                "MISSING_OPERATION_ID",
                f"Canonical {entity_type} record {record.record_id} has no operation_id.",
                record_id=record.record_id,
                entity_type=entity_type,
            )

    severities = {issue["severity"] for issue in issues}
    status = "ERROR" if "ERROR" in severities else "WARN" if "WARN" in severities else "OK"
    if not raw_items and not canonical_items and not mapping_items:
        status = "EMPTY"

    latest_event_time = _latest_time(
        [record.event_time for record in raw_items]
        + [record.event_time for record in canonical_items]
        + [mapping.event_time for mapping in mapping_items]
    )
    latest_ingest_time = _latest_time(
        [record.ingest_time for record in raw_items]
        + [record.ingest_time for record in canonical_items]
        + [mapping.ingest_time for mapping in mapping_items]
    )
    entity_counts = _entity_counts(canonical_items)
    operation_counts = _operation_counts(canonical_items)

    return {
        "schema_version": PRODUCTION_SCHEMA_VERSION,
        "status": status,
        "at_time": at_time,
        "counts": {
            "raw_records": len(raw_items),
            "canonical_records": len(canonical_items),
            "source_key_mappings": len(mapping_items),
            "issues": len(issues),
        },
        "coverage": {
            "entity_types": entity_counts,
            "operations": [
                {
                    "operation_id": operation_id,
                    "canonical_records": operation_counts.get(operation_id, 0),
                    "configured": operation_id in operations if operations else False,
                }
                for operation_id in sorted(set(operations) | set(operation_counts.keys()))
            ],
        },
        "freshness": {
            "latest_event_time": latest_event_time,
            "latest_ingest_time": latest_ingest_time,
            "event_lag": (
                int(latest_ingest_time) - int(latest_event_time)
                if latest_event_time is not None and latest_ingest_time is not None
                else None
            ),
        },
        "issue_count": len(issues),
        "issues": issues,
        "recommended_actions": _recommended_actions(status, issues),
    }


def canonical_record_matches_entity(
    record: CanonicalIngestionRecord,
    entity_type: str,
    canonical_id: str,
) -> bool:
    """Return whether a canonical record belongs to an entity genealogy."""
    target_type = str(entity_type).upper()
    target_id = str(canonical_id)
    if record.entity_type.upper() == target_type and record.canonical_id == target_id:
        return True
    if target_type in {"UNIT", "WAFER"}:
        return target_id in {str(record.unit_id), str(record.canonical_id)}
    if target_type == "LOT":
        return target_id in {str(record.lot_id), str(record.canonical_id)}
    if target_type == "EQUIPMENT":
        return target_id in {str(record.equipment_id), str(record.canonical_id)}
    if target_type == "RECIPE":
        return target_id in {str(record.recipe_id), str(record.canonical_id)}
    return False


def _table_contracts() -> Dict[str, Dict[str, Any]]:
    return {
        "lots": {
            "primary_key": "lot_id",
            "required_fields": ["lot_id", "product_id", "route_id", "status"],
            "time_fields": ["event_time", "ingest_time"],
            "source_link_fields": ["source_system", "source_table", "source_pk"],
            "purpose": "Tracks lot-level identity, route, and production status.",
        },
        "units": {
            "primary_key": "unit_id",
            "required_fields": ["unit_id", "lot_id", "operation_id", "status"],
            "time_fields": ["event_time", "ingest_time", "decision_time"],
            "source_link_fields": ["source_system", "source_table", "source_pk"],
            "purpose": "Tracks wafer/unit position, specs, due date, and process state.",
        },
        "equipment": {
            "primary_key": "equipment_id",
            "required_fields": ["equipment_id", "equipment_group_id", "status"],
            "time_fields": ["event_time", "ingest_time"],
            "source_link_fields": ["source_system", "source_table", "source_pk"],
            "purpose": "Tracks tool status, capabilities, batch size, and current load.",
        },
        "operations": {
            "primary_key": "operation_id",
            "required_fields": ["operation_id", "display_name", "route_edges"],
            "time_fields": [],
            "source_link_fields": [],
            "purpose": "Defines process route topology and policy keys.",
        },
        "recipes": {
            "primary_key": "recipe_id",
            "required_fields": ["recipe_id", "operation_id", "approval_status"],
            "time_fields": ["event_time", "ingest_time"],
            "source_link_fields": ["source_system", "source_table", "source_pk"],
            "purpose": "Tracks RMS/APC recipe versions and parameter sets.",
        },
        "events": {
            "primary_key": "event_id",
            "required_fields": ["event_id", "entity_type", "event_type", "event_time"],
            "time_fields": ["event_time", "ingest_time", "decision_time"],
            "source_link_fields": ["source_system", "source_table", "source_pk"],
            "purpose": "Append-only manufacturing event ledger.",
        },
        "assignments": {
            "primary_key": "assignment_id",
            "required_fields": ["assignment_id", "operation_id", "equipment_id", "unit_ids"],
            "time_fields": ["event_time", "ingest_time", "decision_time"],
            "source_link_fields": ["source_system", "source_table", "source_pk"],
            "purpose": "Links selected units to equipment, candidate, command, and outcome.",
        },
        "quality_results": {
            "primary_key": "quality_result_id",
            "required_fields": ["quality_result_id", "unit_id", "operation_id", "result"],
            "time_fields": ["event_time", "ingest_time"],
            "source_link_fields": ["source_system", "source_table", "source_pk"],
            "purpose": "FDC/inspection/APC outcome facts used for quality lineage.",
        },
        "source_key_mappings": {
            "primary_key": "mapping_id",
            "required_fields": ["source_system", "source_table", "source_pk", "entity_type", "canonical_id"],
            "time_fields": ["event_time", "ingest_time", "decision_time"],
            "source_link_fields": ["source_system", "source_table", "source_pk"],
            "purpose": "Maps legacy keys to stable AI MES canonical ids.",
        },
        "raw_source_records": {
            "primary_key": "record_id",
            "required_fields": ["source_system", "source_table", "source_pk", "entity_type"],
            "time_fields": ["event_time", "ingest_time", "decision_time"],
            "source_link_fields": ["source_system", "source_table", "source_pk"],
            "purpose": "Stores unmodified evidence from MES/RMS/FDC/APC/ERP sources.",
        },
        "canonical_ingestion_records": {
            "primary_key": "record_id",
            "required_fields": ["raw_record_id", "entity_type", "canonical_id"],
            "time_fields": ["event_time", "ingest_time", "decision_time"],
            "source_link_fields": ["raw_record_id"],
            "purpose": "Stores standardized events that rebuild the production digital twin.",
        },
        "action_proposals": {
            "primary_key": "proposal_id",
            "required_fields": ["proposal_id", "correlation_id", "proposal_type", "payload"],
            "time_fields": ["decision_time"],
            "source_link_fields": ["correlation_id", "command_id"],
            "purpose": "AI MES recommendation intent submitted to legacy MES review boundary.",
        },
        "action_proposal_reviews": {
            "primary_key": "review_id",
            "required_fields": ["review_id", "proposal_id", "review_status"],
            "time_fields": ["reviewed_at"],
            "source_link_fields": ["proposal_id", "correlation_id"],
            "purpose": "Operator or process-engineer review gate before legacy submission.",
        },
        "legacy_decisions": {
            "primary_key": "decision_id",
            "required_fields": ["decision_id", "proposal_id", "legacy_status"],
            "time_fields": ["decision_time"],
            "source_link_fields": ["proposal_id", "correlation_id"],
            "purpose": "Records how legacy MES accepted, rejected, or modified proposals.",
        },
        "outcome_records": {
            "primary_key": "outcome_id",
            "required_fields": ["outcome_id", "proposal_id", "outcome_status"],
            "time_fields": ["event_time", "ingest_time"],
            "source_link_fields": ["proposal_id", "correlation_id"],
            "purpose": "Records observed execution and quality outcomes for evaluation.",
        },
    }


def _filter_by_time(
    records: List[CanonicalIngestionRecord],
    at_time: Optional[int],
) -> List[CanonicalIngestionRecord]:
    if at_time is None:
        return records
    result = []
    for record in records:
        event_time = record.event_time if record.event_time is not None else record.ingest_time
        if event_time is None or int(event_time) <= int(at_time):
            result.append(record)
    return result


def _append_duplicate_id_issues(
    issues: List[Dict[str, Any]],
    code: str,
    ids: Sequence[str],
    label: str,
) -> None:
    seen = set()
    duplicates = set()
    for item in ids:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    duplicates = sorted(duplicates)
    if duplicates:
        _issue(
            issues,
            "ERROR",
            code,
            f"Duplicate {label} ids found.",
            record_ids=duplicates,
        )


def _validate_record_times(
    issues: List[Dict[str, Any]],
    record_type: str,
    record_id: str,
    event_time: Optional[int],
    ingest_time: Optional[int],
) -> None:
    if event_time is None and ingest_time is None:
        _issue(
            issues,
            "WARN",
            "MISSING_EVENT_AND_INGEST_TIME",
            f"{record_type} {record_id} has neither event_time nor ingest_time.",
            record_id=record_id,
            record_type=record_type,
        )
        return
    if event_time is not None and ingest_time is not None and int(event_time) > int(ingest_time):
        _issue(
            issues,
            "WARN",
            "EVENT_TIME_AFTER_INGEST_TIME",
            f"{record_type} {record_id} has event_time later than ingest_time.",
            record_id=record_id,
            record_type=record_type,
            event_time=event_time,
            ingest_time=ingest_time,
        )


def _issue(
    issues: List[Dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    **details: Any,
) -> None:
    issues.append(
        {
            "severity": severity,
            "code": code,
            "message": message,
            **details,
        }
    )


def _source_key_from_tuple(key: tuple[Any, ...]) -> str:
    _run_id, source_system, source_table, source_pk, entity_type = key
    return f"{source_system}:{source_table}:{source_pk}:{entity_type}"


def _latest_time(values: Sequence[Optional[int]]) -> Optional[int]:
    filtered = [int(value) for value in values if value is not None]
    return max(filtered) if filtered else None


def _entity_counts(records: Sequence[CanonicalIngestionRecord]) -> Dict[str, int]:
    counts: Dict[str, int] = {entity_type: 0 for entity_type in SUPPORTED_CANONICAL_ENTITY_TYPES}
    for record in records:
        entity_type = record.entity_type.upper()
        counts[entity_type] = counts.get(entity_type, 0) + 1
    return counts


def _operation_counts(records: Sequence[CanonicalIngestionRecord]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for record in records:
        operation_id = str(record.operation_id or "UNKNOWN")
        counts[operation_id] = counts.get(operation_id, 0) + 1
    return counts


def _recommended_actions(status: str, issues: Sequence[Dict[str, Any]]) -> List[str]:
    if status == "EMPTY":
        return ["Ingest raw source records before evaluating production readiness."]
    codes = {issue["code"] for issue in issues}
    actions = []
    if "SOURCE_KEY_CANONICAL_CONFLICT" in codes:
        actions.append("Resolve source key conflicts before using records for policy evaluation.")
    if "UNSUPPORTED_CANONICAL_ENTITY_TYPE" in codes or "UNSUPPORTED_RAW_ENTITY_TYPE" in codes:
        actions.append("Add adapter/schema support for unsupported entity types or remap them.")
    if "RAW_RECORD_REFERENCE_NOT_FOUND" in codes:
        actions.append("Backfill missing raw source evidence for canonical records.")
    if "MISSING_OPERATION_ID" in codes:
        actions.append("Populate operation_id so L1/L2/L3 policy routing can evaluate candidates.")
    if not actions:
        actions.append("No blocking data quality actions detected.")
    return actions
