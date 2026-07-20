"""Adapters from authoritative MES state sources into a common decision state."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from src.mes.digital_twin import build_canonical_decision_state, build_digital_twin_state
from src.mes.ingestion import CanonicalIngestionRecord


def simulator_source_state(env: Any) -> Dict[str, Any]:
    state = dict(env.get_decision_state())
    state["state_source"] = "SIMULATOR"
    return state


def canonical_source_state(
    records: Iterable[CanonicalIngestionRecord],
    at_time: Optional[int] = None,
) -> Dict[str, Any]:
    twin_state = build_digital_twin_state(records, at_time=at_time)
    state = build_canonical_decision_state(twin_state)
    state["canonical_twin"] = twin_state
    state["state_source"] = "CANONICAL_TWIN"
    return state


__all__ = ["canonical_source_state", "simulator_source_state"]
