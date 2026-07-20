# -*- coding: utf-8 -*-
"""RMS adapters for recipe master and equipment eligibility rows."""

from __future__ import annotations

from typing import Any, Dict

from src.mes.ingestion.adapters.base import BaseSourceAdapter, optional_int


class RMSRecipeAdapter(BaseSourceAdapter):
    adapter_id = "rms_recipe"
    source_system = "RMS"
    source_tables = ("RECIPE_MASTER", "RECIPE_VERSION")
    canonical_entity_types = ("RECIPE",)
    description = "Maps RMS recipe master/version rows into canonical recipes."

    def adapt(self, row: Dict[str, Any]) -> Dict[str, Any]:
        recipe_id = str(row["recipe_id"])
        operation_id = str(row.get("operation_id") or "")
        return {
            "source_system": self.source_system,
            "source_table": str(row.get("source_table") or "RECIPE_MASTER"),
            "source_pk": str(row.get("source_pk") or recipe_id),
            "entity_type": "RECIPE",
            "canonical_id": str(row.get("canonical_id") or recipe_id),
            "operation_id": operation_id,
            "recipe_id": recipe_id,
            "event_time": optional_int(row.get("event_time")),
            "ingest_time": optional_int(row.get("ingest_time")),
            "decision_time": optional_int(row.get("decision_time")),
            "canonical": {
                "event_type": str(row.get("event_type") or "RECIPE_AVAILABLE"),
                "attributes": {
                    "recipe_version": str(row.get("recipe_version") or "v1"),
                    "approval_status": str(row.get("approval_status") or "APPROVED"),
                    "parameter_set": dict(row.get("parameter_set") or {}),
                    "product_id": str(row.get("product_id") or ""),
                    "recipe_family": str(row.get("recipe_family") or ""),
                },
            },
            "payload": dict(row),
        }


class RMSRecipeEligibilityAdapter(BaseSourceAdapter):
    adapter_id = "rms_recipe_eligibility"
    source_system = "RMS"
    source_tables = ("RECIPE_EQUIPMENT_ELIGIBILITY", "RECIPE_TOOL_MATRIX")
    canonical_entity_types = ("RECIPE", "EVENT")
    description = "Maps RMS recipe-tool eligibility rows into recipe constraint events."

    def adapt(self, row: Dict[str, Any]) -> Dict[str, Any]:
        recipe_id = str(row["recipe_id"])
        equipment_id = str(row.get("equipment_id") or "")
        operation_id = str(row.get("operation_id") or equipment_id.split("_", 1)[0])
        eligibility_id = str(
            row.get("eligibility_id")
            or row.get("source_pk")
            or f"{recipe_id}:{equipment_id or operation_id}"
        )
        eligible = bool(row.get("eligible", True))
        return {
            "source_system": self.source_system,
            "source_table": str(row.get("source_table") or "RECIPE_EQUIPMENT_ELIGIBILITY"),
            "source_pk": eligibility_id,
            "entity_type": "RECIPE",
            "canonical_id": str(row.get("canonical_id") or eligibility_id),
            "operation_id": operation_id,
            "equipment_id": equipment_id,
            "recipe_id": recipe_id,
            "event_time": optional_int(row.get("event_time")),
            "ingest_time": optional_int(row.get("ingest_time")),
            "decision_time": optional_int(row.get("decision_time")),
            "canonical": {
                "event_type": str(row.get("event_type") or "RECIPE_ELIGIBILITY_UPDATED"),
                "attributes": {
                    "recipe_id": recipe_id,
                    "equipment_id": equipment_id,
                    "eligible": eligible,
                    "constraint_reason": str(row.get("constraint_reason") or ""),
                    "qualification_status": str(
                        row.get("qualification_status")
                        or ("QUALIFIED" if eligible else "BLOCKED")
                    ),
                },
            },
            "payload": dict(row),
        }
