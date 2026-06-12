# -*- coding: utf-8 -*-
"""Production-readiness diagnostics for deployment-boundary review."""

from __future__ import annotations

from typing import Any, Dict

from src.mes.persistence.sqlite_schema import SCHEMA_VERSION, TABLES


def production_readiness_payload(context: Any) -> Dict[str, Any]:
    store = context.harness.store
    db_path = str(getattr(store, "db_path", ""))
    return {
        "status": "READY_FOR_V1_INTEGRATION",
        "scope": "production_transition_contracts_not_direct_equipment_control",
        "storage": {
            "backend": "sqlite" if db_path else "in_memory",
            "db_path": db_path,
            "schema_version": SCHEMA_VERSION,
            "tables": sorted(TABLES.keys()),
            "normalized_indexes": list(getattr(store, "INDEX_TABLES", ())),
            "idempotent_surfaces": [
                "source_key_mappings",
                "raw_source_records",
                "canonical_ingestion_records",
                "commands",
            ],
        },
        "boundaries": {
            "direct_equipment_control": False,
            "action_submission": "ACTION_PROPOSAL_TO_LEGACY_MES_REVIEW",
            "canonical_state_source": "CANONICAL_TWIN",
            "simulator_state_source": "SIMULATOR",
        },
        "security": {
            "llm_write_tools_default": "DISABLED",
            "process_chat_default": "READ_ONLY",
            "operator_approval_required_for_writes": True,
        },
        "integration_points": {
            "production_schema": "/api/v2/production/schema",
            "data_quality": "/api/v2/production/data-quality",
            "legacy_ingestion": "/api/v2/ingestion/source-records",
            "source_adapters": "/api/v2/legacy-adapters/{adapter_id}/ingest",
            "canonical_runner": "/api/v2/digital-twin/recommendation-run",
            "action_proposals": "/api/v2/action-proposals",
            "action_proposal_approval_queue": "/api/v2/action-proposals/approval-queue",
            "decision_dataset": "/api/v2/ai-dev/decision-dataset",
            "policy_evaluation_summary": "/api/v2/ai-dev/policy-evaluation-summary",
            "feedback_summary": "/api/v2/action-proposals/{proposal_id}/feedback-summary",
        },
    }
