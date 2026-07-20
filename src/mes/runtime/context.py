"""Runtime lifecycle for the simulator-backed MES API."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from src.environment.manufacturing_env import ManufacturingEnv
from src.mes import MESDevelopmentHarness
from src.mes.factory_twin import FactoryTwinService
from src.mes.operations.registry import build_default_operation_registry
from src.mes.recommendations import make_id
from src.mes.runtime.config import load_runtime_config
from src.mes.sqlite_store import SQLiteMESStore


def build_default_env() -> ManufacturingEnv:
    env = ManufacturingEnv(load_runtime_config())
    env.reset(seed=11)
    return env


def default_db_path() -> Path:
    return Path(os.environ.get("MES_DB_PATH", "data/mes_mvp.sqlite3"))


class MESAPIContext:
    """Mutable runtime state shared by API routes."""

    def __init__(self) -> None:
        self.runtime_lock = threading.RLock()
        self.env = build_default_env()
        self.operation_registry = build_default_operation_registry(self.env.config)
        self.store = SQLiteMESStore(default_db_path())
        self.store.clear_runtime_state()
        self.run_id = ""
        self._run_sequence = len(self.store.runs())
        self._start_new_run("startup")
        self.harness = MESDevelopmentHarness(config=self.env.config, store=self.store)
        self.factory_twin = FactoryTwinService(self, lock=self.runtime_lock)
        self.factory_twin.commit("SIMULATOR", force=True)
        self.autoplay_enabled = False
        self.autoplay_target_stage = "AUTO"
        self.autoplay_generate_every = 20
        self.last_generation_time: Optional[int] = None
        self.last_correlation_id: Optional[str] = None
        self.last_cycle: Optional[Dict[str, Any]] = None
        self.scenario_snapshots: Dict[str, Dict[str, Any]] = {}
        self.experiment_results: Dict[str, Dict[str, Any]] = {}

    def reset_runtime(self) -> None:
        with self.runtime_lock:
            self.env = build_default_env()
            self.operation_registry = build_default_operation_registry(self.env.config)
            self.store.clear_runtime_state()
            self._start_new_run("reset")
            self.autoplay_enabled = False
            self.autoplay_target_stage = "AUTO"
            self.last_generation_time = None
            self.last_correlation_id = None
            self.last_cycle = None
            self.scenario_snapshots.clear()
            self.experiment_results.clear()
            self.factory_twin.reset()

    def _start_new_run(self, reason: str) -> None:
        self._run_sequence += 1
        self.run_id = make_id("RUN")
        self.store.start_run(
            self.run_id,
            reason=reason,
            time=int(self.env.time),
            metadata={
                "sequence": self._run_sequence,
                "config": dict(self.env.config),
                "operation_registry": self.operation_registry.to_payload()
                if hasattr(self, "operation_registry")
                else {},
            },
        )
        self.store.record_state_snapshot(
            source=f"runtime_{reason}",
            decision_state=self.env.get_decision_state(),
            run_id=self.run_id,
        )
