"""Stateful, tenant-scoped ERP data for demonstrations. No external ERP calls."""
from __future__ import annotations


def default_state() -> dict:
    return {
        "items": [
            {"sku": "KRT-001", "name": "Karton Demo", "unit": "carton", "on_hand": 1, "minimum": 3},
            {"sku": "KRT-002", "name": "Karton Cadangan Demo", "unit": "carton", "on_hand": 0, "minimum": 6},
            {"sku": "BRG-014", "name": "Komponen Rak", "unit": "pcs", "on_hand": 24, "minimum": 10},
        ],
        "purchase_orders": [
            {"number": "PO-DEMO-1001", "vendor": "PT Pasokan Demo", "sku": "KRT-001", "quantity": 4, "status": "in_transit"},
            {"number": "PO-DEMO-1003", "vendor": "PT Pasokan Demo", "sku": "KRT-002", "quantity": 5, "status": "in_transit"},
            {"number": "PO-DEMO-1002", "vendor": "CV Logistik Contoh", "sku": "BRG-014", "quantity": 12, "status": "approved"},
        ],
    }


def inventory(state: dict) -> dict:
    items = state.get("items", [])
    return {"source": "erp_demo", "simulated": True, "items": items, "count": len(items)}


def purchase_orders(state: dict) -> dict:
    orders = state.get("purchase_orders", [])
    return {"source": "erp_demo", "simulated": True, "purchase_orders": orders, "count": len(orders)}


def receive_shipment(state: dict, sku: str, cartons: int, reference: str) -> dict:
    item = next((entry for entry in state.get("items", []) if entry["sku"] == sku), None)
    if item is None:
        raise ValueError("SKU is not present in this demo ERP.")
    before = item["on_hand"]
    item["on_hand"] += cartons
    below_minimum = item["on_hand"] < item["minimum"]
    return {
        "source": "erp_demo", "simulated": True, "sku": sku, "shipment_reference": reference,
        "cartons_received": cartons, "stock_before": before, "stock_after": item["on_hand"],
        "minimum_stock": item["minimum"], "below_minimum": below_minimum,
        "notification": {
            "status": "simulated", "recipients": ["admin", "warehouse_staff"],
            "message": f"Stok {sku} setelah penerimaan {reference}: {item['on_hand']} {item['unit']}; batas minimum {item['minimum']}.",
        } if below_minimum else None,
        "note": "Simulasi ERP; tidak mengubah sistem eksternal dan tidak mengirim pesan langsung.",
    }


def reconcile_receipt(state: dict, source: dict, event: dict) -> dict:
    """Compare a canonical gateway receipt event with open demo POs and stock minimums."""
    payload = event["data"]
    sku = payload.get("sku") if isinstance(payload, dict) else None
    quantity = payload.get("quantity") if isinstance(payload, dict) else None
    reference = payload.get("reference") if isinstance(payload, dict) else None
    po_number = payload.get("po_number") if isinstance(payload, dict) else None
    valid_quantity = type(quantity) is int and quantity >= 0
    open_orders = [order for order in state.get("purchase_orders", [])
                   if order.get("sku") == sku and order.get("status") in {"in_transit", "approved"}]
    if po_number:
        matching = [order for order in open_orders if order.get("number") == po_number]
    else:
        matching = open_orders
    item = next((entry for entry in state.get("items", []) if entry.get("sku") == sku), None)
    complete = isinstance(sku, str) and valid_quantity and item is not None and len(matching) == 1
    expected = matching[0]["quantity"] if complete else None
    stock_after = item["on_hand"] + quantity if complete else None
    shortage = max(0, item["minimum"] - stock_after) if complete else None
    quantity_discrepancy = quantity != expected if complete else None
    reasons = []
    if not complete:
        reasons.append("receipt_data_incomplete_or_po_ambiguous")
    elif quantity_discrepancy:
        reasons.append("receipt_quantity_differs_from_open_po")
    if complete and shortage >= 3:
        reasons.append("post_receipt_stock_short_by_at_least_three_cartons")
    return {
        "source": {"id": source["id"], "name": source["name"], "kind": source["kind"]},
        "source_event_id": event["id"],
        "event_type": event["event_type"], "received_at": event["received_at"], "event_data": payload, "shipment_reference": reference,
        "sku": sku, "receipt_quantity": quantity, "purchase_order": matching[0] if len(matching) == 1 else None,
        "expected_quantity": expected, "quantity_discrepancy": quantity_discrepancy,
        "stock_after_receipt": stock_after, "minimum_stock": item["minimum"] if item else None,
        "shortage_cartons": shortage, "sensor_status": "recent", "needs_escalation": bool(reasons),
        "escalation_reasons": reasons, "simulated": True,
    }
