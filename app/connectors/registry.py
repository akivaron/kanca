"""Connector contract and explicit registry. No domain logic belongs in core."""
from typing import Any, Callable


def business_orders(_: dict[str, Any]) -> dict[str, Any]:
    return {"source": "synthetic", "orders": [
        {"id": "order-1", "packed": False, "expected": 3, "recorded": 3},
        {"id": "order-2", "packed": True, "expected": 2, "recorded": 1},
    ], "note": "Simulated data; physical delivery is not verified."}


def business_check(_: dict[str, Any]) -> dict[str, Any]:
    orders = business_orders({})["orders"]
    return {"source": "synthetic", "checked": len(orders), "unpacked_count": sum(not order["packed"] for order in orders),
            "mismatch_count": sum(order["expected"] != order["recorded"] for order in orders),
            "unverified": ["Pickup schedules, photos, and physical delivery are not verified."]}


def device_temperature(_: dict[str, Any]) -> dict[str, Any]:
    return {"source": "synthetic", "temperature_c": 29, "note": "Simulated sensor."}


def device_light(_: dict[str, Any]) -> dict[str, Any]:
    return {"source": "synthetic", "state": "on", "note": "Simulated action; does not control a physical device."}


def demo_reminder(args: dict[str, Any]) -> dict[str, Any]:
    return {"source": "synthetic", "message": args["message"], "note": "Simulated reminder; not sent to external parties."}


CAPABILITIES: dict[str, dict[str, Any]] = {
    "external.latest_event": {"connector": "external_events", "description": "Read the latest event from an external source. Specify event_type when the source has multiple event types; data comes from the sender and is unverified.", "result_fields": {"event_type": "string", "received_at": "string", "data": "object"}, "risk": "read", "parameters": {"type": "object", "properties": {"source_id": {"type": "string", "maxLength": 100}, "event_type": {"type": "string", "maxLength": 100}}, "required": ["source_id"], "additionalProperties": False}, "run": None},
    "external.escalate": {"connector": "external_events", "description": "Record an escalation event for the owner; this does not send a message directly.", "risk": "safe_action", "parameters": {"type": "object", "properties": {"message": {"type": "string", "maxLength": 500}}, "required": ["message"], "additionalProperties": False}, "run": None},
    "business.list_orders": {"connector": "business_demo", "description": "Read synthetic orders and their packing status.", "risk": "read", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}, "run": business_orders},
    "business.check_orders": {"connector": "business_demo", "description": "Count synthetic orders that are unpacked or have quantity mismatches; results include unpacked_count and mismatch_count.", "result_fields": {"checked": "integer", "unpacked_count": "integer", "mismatch_count": "integer"}, "risk": "read", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}, "run": business_check},
    "business.remind": {"connector": "business_demo", "description": "Create a simulated reminder.", "risk": "safe_action", "parameters": {"type": "object", "properties": {"message": {"type": "string", "maxLength": 500}}, "required": ["message"], "additionalProperties": False}, "run": demo_reminder},
    "device.read_temperature": {"connector": "device_demo", "description": "Read the simulated sensor temperature in degrees Celsius.", "result_fields": {"temperature_c": "number"}, "risk": "read", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}, "run": device_temperature},
    "device.turn_on_light": {"connector": "device_demo", "description": "Turn on the simulated light.", "risk": "action", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}, "run": device_light},
    "erp.demo.inventory": {"connector": "erp_demo", "description": "Read current stock levels and minimum thresholds from the stateful simulated ERP. All values are demo data.", "result_fields": {"count": "integer", "items": "array"}, "risk": "read", "parameters": {"type": "object", "properties": {"connection_id": {"type": "string", "maxLength": 100}}, "required": ["connection_id"], "additionalProperties": False}, "run": None},
    "erp.demo.purchase_orders": {"connector": "erp_demo", "description": "Read simulated ERP purchase orders and their shipment status.", "result_fields": {"count": "integer", "purchase_orders": "array"}, "risk": "read", "parameters": {"type": "object", "properties": {"connection_id": {"type": "string", "maxLength": 100}}, "required": ["connection_id"], "additionalProperties": False}, "run": None},
    "erp.demo.reconcile_source_receipt": {"connector": "erp_demo", "description": "Read new fresh incoming-shipment events from a selected structured IoT/gateway source and compare each event's sku and quantity (and optional po_number) with an open demo ERP purchase order. Event payload keys: sku, quantity, optional po_number and reference. Kanca logs an escalation with source and event details when the receipt data is incomplete/ambiguous, the quantity differs, or post-receipt stock is short by at least 3 cartons. Repeated checks do not process old events twice.", "result_fields": {"sensor_status": "string", "processed_receipts": "array", "count": "integer", "no_new_receipt": "boolean"}, "risk": "read", "parameters": {"type": "object", "properties": {"connection_id": {"type": "string", "maxLength": 100}, "source_id": {"type": "string", "maxLength": 100}, "event_type": {"type": "string", "maxLength": 100}}, "required": ["connection_id", "source_id", "event_type"], "additionalProperties": False}, "run": None},
    "erp.demo.receive_shipment": {"connector": "erp_demo", "description": "Simulate recording an incoming shipment, update demo stock, and produce a simulated threshold notification for admin and warehouse staff when stock remains below its minimum.", "result_fields": {"sku": "string", "stock_after": "integer", "minimum_stock": "integer", "below_minimum": "boolean"}, "risk": "action", "parameters": {"type": "object", "properties": {"connection_id": {"type": "string", "maxLength": 100}, "sku": {"type": "string", "maxLength": 30}, "cartons": {"type": "integer", "minimum": 1, "maximum": 10000}, "reference": {"type": "string", "maxLength": 100}}, "required": ["connection_id", "sku", "cartons", "reference"], "additionalProperties": False}, "run": None},
    "erp.odoo.stock_levels": {"connector": "erp", "description": "Read current on-hand and available quantity from Odoo inventory by optional product code. Quantities are ERP records, not physical verification.", "result_fields": {"count": "integer", "quantity_available": "number", "records": "array"}, "risk": "read", "parameters": {"type": "object", "properties": {"connection_id": {"type": "string", "maxLength": 100}, "product_code": {"type": "string", "maxLength": 100}, "limit": {"type": "integer", "minimum": 1, "maximum": 100}}, "required": ["connection_id"], "additionalProperties": False}, "run": None},
    "erp.odoo.purchase_orders": {"connector": "erp", "description": "Read open draft, sent, approval-pending, and confirmed purchase orders from Odoo.", "result_fields": {"count": "integer", "records": "array"}, "risk": "read", "parameters": {"type": "object", "properties": {"connection_id": {"type": "string", "maxLength": 100}, "limit": {"type": "integer", "minimum": 1, "maximum": 50}}, "required": ["connection_id"], "additionalProperties": False}, "run": None},
    "erp.odoo.create_draft_purchase_order": {"connector": "erp", "description": "Create a draft purchase order in Odoo. It is not confirmed or sent to the supplier.", "risk": "action", "parameters": {"type": "object", "properties": {"connection_id": {"type": "string", "maxLength": 100}, "vendor_id": {"type": "integer", "minimum": 1}, "lines": {"type": "array", "minItems": 1, "maxItems": 50, "items": {"type": "object", "properties": {"product_id": {"type": "integer", "minimum": 1}, "quantity": {"type": "number", "exclusiveMinimum": 0}, "price_unit": {"type": "number", "minimum": 0}}, "required": ["product_id", "quantity"], "additionalProperties": False}}}, "required": ["connection_id", "vendor_id", "lines"], "additionalProperties": False}, "run": None},
    "erp.odoo.update_draft_purchase_order_note": {"connector": "erp", "description": "Update the note on an Odoo purchase order only while it is still a draft.", "risk": "action", "parameters": {"type": "object", "properties": {"connection_id": {"type": "string", "maxLength": 100}, "order_id": {"type": "integer", "minimum": 1}, "note": {"type": "string", "maxLength": 2000}}, "required": ["connection_id", "order_id", "note"], "additionalProperties": False}, "run": None},
}


def describe(connector: str | None = None) -> list[dict[str, Any]]:
    return [{"name": name, **{k: v for k, v in value.items() if k != "run"}} for name, value in CAPABILITIES.items() if connector is None or value["connector"] == connector]
