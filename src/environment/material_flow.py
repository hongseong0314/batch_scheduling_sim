# -*- coding: utf-8 -*-
"""Deterministic material transfer state for the manufacturing environment."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from src.objects import Task


@dataclass
class TransferJob:
    """One carrier movement between two operations."""

    transfer_id: str
    carrier_id: str
    task_uids: List[int]
    from_operation_id: str
    to_operation_id: str
    dispatch_time: int
    arrival_time: int
    status: str = "IN_TRANSIT"

    def to_dict(self, current_time: int | None = None) -> Dict[str, Any]:
        payload = asdict(self)
        payload["route_id"] = (
            f"ROUTE_{self.from_operation_id}_{self.to_operation_id}"
        )
        if current_time is None:
            progress = 1.0 if self.status == "ARRIVED" else 0.0
        elif self.arrival_time <= self.dispatch_time:
            progress = 1.0
        else:
            progress = (int(current_time) - self.dispatch_time) / (
                self.arrival_time - self.dispatch_time
            )
        payload["progress"] = round(max(0.0, min(1.0, progress)), 4)
        return payload


class MaterialFlowController:
    """Own movement state without making scheduling or recipe decisions."""

    VALID_MODES = {"immediate", "timed_oht"}

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        resolved = dict(config or {})
        mode = str(resolved.get("mode", "immediate")).lower()
        self.mode = mode if mode in self.VALID_MODES else "immediate"

        raw_oht_time = resolved.get("oht_time")
        if isinstance(raw_oht_time, Mapping):
            default_time = resolved.get("default_travel_time", 2)
            configured_oht_routes = dict(raw_oht_time)
        else:
            default_time = (
                raw_oht_time
                if raw_oht_time is not None
                else resolved.get("default_travel_time", 2)
            )
            configured_oht_routes = {}

        self.default_travel_time = _nonnegative_duration(default_time, default=2)
        raw_route_times = dict(resolved.get("route_travel_time", {}) or {})
        raw_route_times.update(configured_oht_routes)
        self.route_travel_time = {
            str(key).replace("->", ">"): _nonnegative_duration(value)
            for key, value in raw_route_times.items()
        }
        self._sequence = 0
        self._active: Dict[str, tuple[TransferJob, List[Task]]] = {}
        self._completed: List[TransferJob] = []
        self._task_owners: Dict[int, str] = {}

    def reset(self) -> None:
        self._sequence = 0
        self._active.clear()
        self._completed.clear()
        self._task_owners.clear()

    def dispatch(
        self,
        tasks: Sequence[Task],
        from_operation_id: str,
        to_operation_id: str,
        current_time: int,
    ) -> List[Task]:
        """Dispatch tasks and return same-step arrivals in immediate mode."""
        batch = list(tasks)
        if not batch:
            return []
        duplicate = [task.uid for task in batch if task.uid in self._task_owners]
        if duplicate:
            raise ValueError(f"tasks already in transit: {sorted(duplicate)}")

        self._sequence += 1
        travel_time = self._travel_time(from_operation_id, to_operation_id)
        arrival_time = int(current_time) + travel_time
        job = TransferJob(
            transfer_id=f"TRANSFER_{self._sequence:06d}",
            carrier_id=f"CARRIER_{self._sequence:06d}",
            task_uids=[int(task.uid) for task in batch],
            from_operation_id=str(from_operation_id),
            to_operation_id=str(to_operation_id),
            dispatch_time=int(current_time),
            arrival_time=arrival_time,
            status="ARRIVED" if travel_time == 0 else "IN_TRANSIT",
        )
        for task in batch:
            task.location = f"IN_TRANSIT_{from_operation_id}_{to_operation_id}"

        if travel_time == 0:
            self._completed.append(job)
            return batch

        self._active[job.transfer_id] = (job, batch)
        for task in batch:
            self._task_owners[int(task.uid)] = job.transfer_id
        return []

    def release_arrivals(self, current_time: int) -> Dict[str, List[Task]]:
        """Release jobs whose authoritative arrival time has been reached."""
        arrivals: Dict[str, List[Task]] = {}
        due_ids = [
            transfer_id
            for transfer_id, (job, _) in self._active.items()
            if job.arrival_time <= int(current_time)
        ]
        for transfer_id in sorted(due_ids):
            job, tasks = self._active.pop(transfer_id)
            job.status = "ARRIVED"
            self._completed.append(job)
            arrivals.setdefault(job.to_operation_id, []).extend(tasks)
            for task in tasks:
                self._task_owners.pop(int(task.uid), None)
        return arrivals

    def in_transit_tasks(self) -> Iterable[Task]:
        for _, tasks in self._active.values():
            yield from tasks

    def task_transfer(self, task_uid: int) -> TransferJob | None:
        transfer_id = self._task_owners.get(int(task_uid))
        if transfer_id is None:
            return None
        entry = self._active.get(transfer_id)
        return entry[0] if entry else None

    def active_jobs(self, current_time: int | None = None) -> List[Dict[str, Any]]:
        return [
            job.to_dict(current_time)
            for job, _ in sorted(
                self._active.values(), key=lambda entry: entry[0].transfer_id
            )
        ]

    def recent_jobs(
        self,
        current_time: int | None = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        jobs = self._completed[-max(0, int(limit)) :] if limit else []
        return [job.to_dict(current_time) for job in jobs]

    def state(self, current_time: int) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "active": self.active_jobs(current_time),
            "recent_completed": self.recent_jobs(current_time),
            "active_count": len(self._active),
            "completed_count": len(self._completed),
        }

    def _travel_time(self, source: str, target: str) -> int:
        if self.mode == "immediate":
            return 0
        key = f"{source}>{target}"
        return self.route_travel_time.get(key, self.default_travel_time)


def _nonnegative_duration(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return max(0, int(default))


__all__ = ["MaterialFlowController", "TransferJob"]
