# -*- coding: utf-8 -*-
"""ERP adapters for order, product, and due-date context."""

from __future__ import annotations

from typing import Any, Dict

from src.mes.ingestion.adapters.base import BaseSourceAdapter, optional_int


class ERPOrderLotAdapter(BaseSourceAdapter):
    adapter_id = "erp_order_lot"
    source_system = "ERP"
    source_tables = ("ORDER_LINE", "LOT_ORDER", "CUSTOMER_ORDER")
    canonical_entity_types = ("LOT",)
    description = "Maps ERP order/lot demand rows into canonical lot context events."

    def adapt(self, row: Dict[str, Any]) -> Dict[str, Any]:
        lot_id = str(row.get("lot_id") or row.get("job_id") or row["order_id"])
        order_id = str(row.get("order_id") or row.get("source_pk") or lot_id)
        route_id = str(row.get("route_id") or "A_B_C")
        return {
            "source_system": self.source_system,
            "source_table": str(row.get("source_table") or "ORDER_LINE"),
            "source_pk": str(row.get("source_pk") or order_id),
            "entity_type": "LOT",
            "canonical_id": str(row.get("canonical_id") or lot_id),
            "operation_id": str(row.get("operation_id") or ""),
            "lot_id": lot_id,
            "event_time": optional_int(row.get("event_time")),
            "ingest_time": optional_int(row.get("ingest_time")),
            "decision_time": optional_int(row.get("decision_time")),
            "canonical": {
                "event_type": str(row.get("event_type") or "LOT_DEMAND_UPDATED"),
                "attributes": {
                    "order_id": order_id,
                    "lot_id": lot_id,
                    "product_id": str(row.get("product_id") or ""),
                    "customer_id": str(row.get("customer_id") or "UNKNOWN"),
                    "route_id": route_id,
                    "due_date": int(row.get("due_date", 0) or 0),
                    "priority": str(row.get("priority") or ""),
                    "quantity": int(row.get("quantity", 0) or 0),
                },
            },
            "payload": dict(row),
        }
