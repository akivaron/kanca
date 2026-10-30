"""Connector contract and explicit registry. No domain logic belongs in core."""
from typing import Any, Callable


def business_orders(_: dict[str, Any]) -> dict[str, Any]:
    return {"source": "synthetic", "orders": [
        {"id": "order-1", "packed": False, "expected": 3, "recorded": 3},
        {"id": "order-2", "packed": True, "expected": 2, "recorded": 1},
    ], "note": "Data simulasi; tidak memverifikasi pengiriman fisik."}


def business_check(_: dict[str, Any]) -> dict[str, Any]:
    orders = business_orders({})["orders"]
    return {"source": "synthetic", "checked": len(orders), "unpacked_count": sum(not order["packed"] for order in orders),
            "mismatch_count": sum(order["expected"] != order["recorded"] for order in orders),
            "unverified": ["Jadwal pickup, foto, dan pengiriman fisik tidak diverifikasi."]}


def device_temperature(_: dict[str, Any]) -> dict[str, Any]:
    return {"source": "synthetic", "temperature_c": 29, "note": "Sensor simulasi."}


def device_light(_: dict[str, Any]) -> dict[str, Any]:
    return {"source": "synthetic", "state": "on", "note": "Aksi simulasi; tidak mengontrol perangkat fisik."}


def demo_reminder(args: dict[str, Any]) -> dict[str, Any]:
    return {"source": "synthetic", "message": args["message"], "note": "Pengingat simulasi; tidak dikirim ke pihak eksternal."}


CAPABILITIES: dict[str, dict[str, Any]] = {
    "external.latest_event": {"connector": "external_events", "description": "Baca event terbaru dari sumber eksternal. Gunakan event_type bila sumber memiliki lebih dari satu jenis event; data berasal dari pengirim dan belum diverifikasi.", "result_fields": {"event_type": "string", "received_at": "string", "data": "object"}, "risk": "read", "parameters": {"type": "object", "properties": {"source_id": {"type": "string", "maxLength": 100}, "event_type": {"type": "string", "maxLength": 100}}, "required": ["source_id"], "additionalProperties": False}, "run": None},
    "external.escalate": {"connector": "external_events", "description": "Catat eskalasi untuk pemilik sebagai event; tidak mengirim pesan langsung.", "risk": "safe_action", "parameters": {"type": "object", "properties": {"message": {"type": "string", "maxLength": 500}}, "required": ["message"], "additionalProperties": False}, "run": None},
    "business.list_orders": {"connector": "business_demo", "description": "Baca pesanan sintetis dan status packing.", "risk": "read", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}, "run": business_orders},
    "business.check_orders": {"connector": "business_demo", "description": "Hitung pesanan sintetis yang belum dikemas dan yang jumlahnya berbeda; hasil memiliki unpacked_count dan mismatch_count.", "result_fields": {"checked": "integer", "unpacked_count": "integer", "mismatch_count": "integer"}, "risk": "read", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}, "run": business_check},
    "business.remind": {"connector": "business_demo", "description": "Buat pengingat simulasi.", "risk": "safe_action", "parameters": {"type": "object", "properties": {"message": {"type": "string", "maxLength": 500}}, "required": ["message"], "additionalProperties": False}, "run": demo_reminder},
    "device.read_temperature": {"connector": "device_demo", "description": "Baca suhu sensor simulasi dalam derajat Celsius.", "result_fields": {"temperature_c": "number"}, "risk": "read", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}, "run": device_temperature},
    "device.turn_on_light": {"connector": "device_demo", "description": "Nyalakan lampu simulasi.", "risk": "action", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}, "run": device_light},
}


def describe(connector: str | None = None) -> list[dict[str, Any]]:
    return [{"name": name, **{k: v for k, v in value.items() if k != "run"}} for name, value in CAPABILITIES.items() if connector is None or value["connector"] == connector]
