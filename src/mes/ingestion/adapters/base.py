# -*- coding: utf-8 -*-
"""Source adapter interfaces for production ingestion.

Adapters are intentionally narrow: they translate one source row into the
existing raw/canonical ingestion payload shape. They do not write to storage and
they do not make policy decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Protocol, Sequence


ADAPTER_INTERFACE_VERSION = "source-adapter-v1"
OUTPUT_CONTRACT = {
    "raw_source_record": "raw-source-record-v1",
    "canonical_ingestion_record": "canonical-ingestion-record-v1",
    "source_key_mapping": "source-key-mapping-v1",
}


class SourceAdapter(Protocol):
    adapter_id: str
    source_system: str
    source_tables: Sequence[str]
    canonical_entity_types: Sequence[str]
    description: str

    def adapt(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Return an ingestion payload for one source row."""

    def metadata(self) -> Dict[str, Any]:
        """Return adapter contract metadata."""


@dataclass(frozen=True)
class AdapterMetadata:
    adapter_id: str
    source_system: str
    source_tables: Sequence[str]
    canonical_entity_types: Sequence[str]
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "interface_version": ADAPTER_INTERFACE_VERSION,
            "source_system": self.source_system,
            "source_tables": list(self.source_tables),
            "canonical_entity_types": list(self.canonical_entity_types),
            "mode": "row_to_canonical_ingestion_payload",
            "writes": [
                "raw_source_records",
                "canonical_ingestion_records",
                "source_key_mappings",
            ],
            "output_contract": dict(OUTPUT_CONTRACT),
            "description": self.description,
        }


class BaseSourceAdapter:
    adapter_id = ""
    source_system = ""
    source_tables: Sequence[str] = ()
    canonical_entity_types: Sequence[str] = ()
    description = ""

    def metadata(self) -> Dict[str, Any]:
        return AdapterMetadata(
            adapter_id=self.adapter_id,
            source_system=self.source_system,
            source_tables=self.source_tables,
            canonical_entity_types=self.canonical_entity_types,
            description=self.description,
        ).to_dict()


def optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def list_of_strings(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, Iterable):
        return [str(item) for item in value]
    return [str(value)]


def task_uid(row: Dict[str, Any], unit_id: str = "") -> int:
    value = row.get("task_uid") or row.get("uid")
    if value is not None and str(value).lstrip("-").isdigit():
        return int(value)
    suffix = str(unit_id).split("_")[-1]
    return int(suffix) if suffix.isdigit() else 0
