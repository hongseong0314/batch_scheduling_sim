"""REST and WebSocket delivery for the spatial factory twin."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from src.mes.factory_twin.contracts import SCHEMA_VERSION


def build_factory_twin_router(context: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v2/factory-twin", tags=["factory-twin"])

    @router.get("/layout")
    def layout() -> dict[str, Any]:
        return context.factory_twin.layout().model_dump(mode="json")

    @router.get("/snapshot")
    def snapshot(
        source: str = Query("SIMULATOR"),
        run_id: Optional[str] = Query(None),
        at_time: Optional[int] = Query(None),
    ) -> dict[str, Any]:
        try:
            with context.runtime_lock:
                result = context.factory_twin.commit(
                    source, run_id=run_id, at_time=at_time
                )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return result.model_dump(mode="json")

    @router.get("/entity/{entity_type}/{entity_id}")
    def entity(
        entity_type: str,
        entity_id: str,
        source: str = Query("SIMULATOR"),
        run_id: Optional[str] = Query(None),
        at_time: Optional[int] = Query(None),
    ) -> dict[str, Any]:
        try:
            result = context.factory_twin.entity(
                entity_type,
                entity_id,
                source=source,
                run_id=run_id,
                at_time=at_time,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if result is None:
            raise HTTPException(status_code=404, detail="factory twin entity not found")
        return result

    @router.get("/replay-range")
    def replay_range(run_id: Optional[str] = Query(None)) -> dict[str, Any]:
        return context.factory_twin.replay_range(run_id=run_id)

    @router.websocket("/stream")
    async def stream(websocket: WebSocket) -> None:
        source = websocket.query_params.get("source", "SIMULATOR")
        requested_schema = websocket.query_params.get("schema", SCHEMA_VERSION)
        if requested_schema != SCHEMA_VERSION:
            await websocket.close(code=1003, reason="unsupported schema")
            return
        try:
            initial = context.factory_twin.commit(source)
        except ValueError:
            await websocket.close(code=1008, reason="unsupported source")
            return

        await websocket.accept()
        await websocket.send_json(
            {
                "type": "hello",
                "schema_version": SCHEMA_VERSION,
                "run_id": initial.run_id,
                "sequence": initial.sequence,
                "state_source": initial.state_source,
                "server_time": time.time(),
            }
        )
        await websocket.send_json(
            {"type": "snapshot", "payload": initial.model_dump(mode="json")}
        )
        sequence = initial.sequence
        last_heartbeat = time.monotonic()
        try:
            while True:
                await asyncio.sleep(0.25)
                current = context.factory_twin.commit(source)
                if current.run_id != initial.run_id:
                    initial = current
                    sequence = current.sequence
                    await websocket.send_json(
                        {
                            "type": "snapshot",
                            "reason": "run_changed",
                            "payload": current.model_dump(mode="json"),
                        }
                    )
                    continue
                if current.sequence != sequence:
                    kind, payload = context.factory_twin.snapshot_after(
                        source, current.run_id, sequence
                    )
                    if kind == "delta":
                        await websocket.send_json(
                            {"type": "delta", "payload": payload.model_dump(mode="json")}
                        )
                    else:
                        await websocket.send_json(
                            {
                                "type": "resync_required",
                                "sequence": current.sequence,
                            }
                        )
                        await websocket.send_json(
                            {"type": "snapshot", "payload": current.model_dump(mode="json")}
                        )
                    sequence = current.sequence
                if time.monotonic() - last_heartbeat >= 5.0:
                    await websocket.send_json(
                        {
                            "type": "heartbeat",
                            "sequence": sequence,
                            "time": current.time,
                            "server_time": time.time(),
                        }
                    )
                    last_heartbeat = time.monotonic()
        except (WebSocketDisconnect, RuntimeError):
            return

    return router


__all__ = ["build_factory_twin_router"]
