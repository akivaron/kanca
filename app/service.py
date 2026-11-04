import json
import math
from datetime import datetime, timedelta, timezone
from app.connectors.registry import CAPABILITIES
from app.connectors.odoo import OdooClient
from app.credentials import decrypt_credentials
from app.connectors import erp_demo
from app.storage import acquire_task_source_automation, connect, event, now, release_task_source_automation, uid


class StaleSourceDataError(ValueError):
    pass


def validate_steps(steps, connected):
    if not isinstance(steps, list) or not 1 <= len(steps) <= 10:
        raise ValueError("Plan must contain 1–10 supported steps.")
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or not {"capability", "arguments"} <= set(step) or set(step) - {"capability", "arguments", "condition"}:
            raise ValueError("Format langkah invalid.")
        name, args = step["capability"], step["arguments"]
        if not isinstance(name, str) or name not in CAPABILITIES:
            raise ValueError("Unknown capability.")
        spec = CAPABILITIES[name]
        if spec["connector"] not in connected:
            raise ValueError(f"Connector for {name} is not connected.")
        schema = spec["parameters"]
        if not isinstance(args, dict) or set(args) - set(schema["properties"]) or set(schema.get("required", [])) - set(args):
            raise ValueError(f"Argument {name} invalid.")
        for key, value in args.items():
            prop = schema["properties"][key]
            if prop.get("type") == "string" and (not isinstance(value, str) or len(value) > prop.get("maxLength", 10000)):
                raise ValueError(f"Argument {key} invalid.")
            if prop.get("type") == "integer" and (type(value) is not int or value < prop.get("minimum", -math.inf) or value > prop.get("maximum", math.inf)):
                raise ValueError(f"Argument {key} invalid.")
            if prop.get("type") == "number" and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= prop.get("exclusiveMinimum", -math.inf) or value < prop.get("minimum", -math.inf)):
                raise ValueError(f"Argument {key} invalid.")
            if prop.get("type") == "array":
                item_schema = prop.get("items", {})
                if not isinstance(value, list) or not prop.get("minItems", 0) <= len(value) <= prop.get("maxItems", 10000):
                    raise ValueError(f"Argument {key} invalid.")
                for entry in value:
                    if not isinstance(entry, dict) or set(entry) - set(item_schema.get("properties", {})) or set(item_schema.get("required", [])) - set(entry):
                        raise ValueError(f"Argument {key} invalid.")
                    for field, field_value in entry.items():
                        field_schema = item_schema["properties"][field]
                        if field_schema.get("type") == "integer" and (type(field_value) is not int or field_value < field_schema.get("minimum", -math.inf)):
                            raise ValueError(f"Argument {key} invalid.")
                        if field_schema.get("type") == "number" and (isinstance(field_value, bool) or not isinstance(field_value, (int, float)) or not math.isfinite(field_value) or field_value <= field_schema.get("exclusiveMinimum", -math.inf) or field_value < field_schema.get("minimum", -math.inf)):
                            raise ValueError(f"Argument {key} invalid.")
        condition = step.get("condition")
        if condition is not None:
            if not isinstance(condition, dict) or set(condition) != {"step", "field", "operator", "value"}:
                raise ValueError("Format kondisi invalid.")
            if type(condition["step"]) is not int or not 0 <= condition["step"] < index or not isinstance(condition["field"], str) or not condition["field"] or condition["operator"] not in ("eq", "ne", "gt", "gte", "lt", "lte"):
                raise ValueError("Condition must reference a previous step and a supported operator.")
            value = condition["value"]
            if not isinstance(value, (str, int, float, bool, type(None))) or (isinstance(value, float) and not math.isfinite(value)):
                raise ValueError("Condition value must be valid text, a number, a boolean, or null.")
            if condition["operator"] in ("gt", "gte", "lt", "lte") and (value is None or isinstance(value, bool)):
                raise ValueError("Condition value does not support ordered comparisons.")
            previous = CAPABILITIES[steps[condition["step"]]["capability"]]
            known_fields = previous.get("result_fields")
            if known_fields is not None and condition["field"] not in known_fields and not (condition["field"].startswith("data.") and known_fields.get("data") == "object"):
                raise ValueError("Condition field is unavailable in the previous step result.")


def matches(condition, results):
    if condition is None:
        return True
    item = results[condition["step"]].get("result")
    for part in condition["field"].split("."):
        if not isinstance(item, dict) or part not in item:
            raise ValueError("Data required to evaluate the condition is unavailable.")
        item = item[part]
    value = condition["value"]
    op = condition["operator"]
    same_type = type(item) is type(value) or (type(item) in (int, float) and type(value) in (int, float))
    if not same_type:
        raise ValueError("Type data kondisi cannot dibandingkan.")
    try:
        return {"eq": lambda: item == value, "ne": lambda: item != value, "gt": lambda: item > value, "gte": lambda: item >= value, "lt": lambda: item < value, "lte": lambda: item <= value}[op]()
    except TypeError as exc:
        raise ValueError("Type data kondisi cannot dibandingkan.") from exc


def run_odoo_capability(db, tenant, capability, arguments, reference=None):
    connection_id = arguments["connection_id"]
    row = db.execute("SELECT config,credentials_enc FROM connections WHERE id=? AND tenant=? AND type='erp_odoo' AND status='connected'", (connection_id, tenant)).fetchone()
    if row is None:
        raise ValueError("Active Odoo connection not found for this tenant.")
    config = json.loads(row["config"] or '{}')
    credentials = decrypt_credentials(row["credentials_enc"] or '')
    client = OdooClient(config["base_url"], credentials["api_key"], config.get("database"))
    args = {key: value for key, value in arguments.items() if key != "connection_id"}
    if capability == "erp.odoo.create_draft_purchase_order":
        args["reference"] = reference
    operations = {
        "erp.odoo.stock_levels": client.stock_levels,
        "erp.odoo.purchase_orders": client.purchase_orders,
        "erp.odoo.create_draft_purchase_order": client.create_draft_purchase_order,
        "erp.odoo.update_draft_purchase_order_note": client.update_draft_purchase_order_note,
    }
    operation = operations.get(capability)
    if operation is None:
        raise ValueError("Unsupported Odoo operation.")
    return operation(**args)


def run_demo_erp_capability(db, tenant, capability, arguments, task_id=None, task_created_at=None):
    connection_id = arguments["connection_id"]
    row = db.execute("SELECT config FROM connections WHERE id=? AND tenant=? AND type='erp_demo' AND status='connected'", (connection_id, tenant)).fetchone()
    if row is None:
        raise ValueError("Active demo ERP connection not found for this tenant.")
    state = json.loads(row["config"] or '{}')
    if capability == "erp.demo.inventory":
        return erp_demo.inventory(state)
    if capability == "erp.demo.purchase_orders":
        return erp_demo.purchase_orders(state)
    if capability == "erp.demo.reconcile_source_receipt":
        source_id = arguments["source_id"]
        source = db.execute("SELECT id,name,kind,status,last_seen,expected_interval_seconds FROM sources WHERE id=? AND tenant=?", (source_id, tenant)).fetchone()
        if source is None or source["kind"] != "iot":
            raise ValueError("ERP receipt reconciliation requires an active structured IoT/gateway source; a camera cannot verify receipt quantities.")
        if source["status"] != "active":
            raise StaleSourceDataError("The selected IoT source is not transmitting because it is paused or inactive.")
        if not source["last_seen"]:
            raise StaleSourceDataError("The selected sensor has not sent data yet.")
        received = datetime.fromisoformat(source["last_seen"])
        if datetime.now(timezone.utc) - received > timedelta(seconds=max(300, source["expected_interval_seconds"] * 2)):
            raise StaleSourceDataError("The selected sensor has not sent fresh data.")
        previous = db.execute("SELECT created_at FROM task_runs WHERE task_id=? ORDER BY number DESC LIMIT 1", (task_id,)).fetchone() if task_id else None
        since = previous["created_at"] if previous else task_created_at
        rows = db.execute("SELECT id,event_type,payload,received_at FROM source_events WHERE source_id=? AND event_type=? AND received_at>? ORDER BY rowid LIMIT 500", (source_id, arguments["event_type"], since)).fetchall()
        reconciliations = []
        for latest in rows:
            result = erp_demo.reconcile_receipt(state, dict(source), {"id": latest["id"], "event_type": latest["event_type"], "received_at": latest["received_at"], "data": json.loads(latest["payload"])})
            reconciliations.append(result)
            if result["needs_escalation"]:
                event(db, tenant, task_id or "", "task.escalated.v1", {
                    "reason": result["escalation_reasons"], "source": result["source"],
                    "source_event_id": result["source_event_id"], "observed_at": result["received_at"],
                    "event_type": result["event_type"], "event_data": result["event_data"], "sku": result["sku"],
                    "receipt_quantity": result["receipt_quantity"], "expected_quantity": result["expected_quantity"],
                    "purchase_order": result["purchase_order"], "stock_after_receipt": result["stock_after_receipt"],
                    "shortage_cartons": result["shortage_cartons"],
                })
        return {"source": {"id": source["id"], "name": source["name"], "kind": source["kind"]},
                "sensor_status": "recent", "processed_receipts": reconciliations,
                "count": len(reconciliations), "no_new_receipt": not reconciliations, "simulated": True}
    if capability == "erp.demo.receive_shipment":
        result = erp_demo.receive_shipment(state, arguments["sku"], arguments["cartons"], arguments["reference"])
        db.execute("UPDATE connections SET config=? WHERE id=? AND tenant=?", (json.dumps(state, ensure_ascii=False), connection_id, tenant))
        return result
    raise ValueError("Unsupported demo ERP operation.")


def tick_demo_gateway() -> bool:
    """Generate recurring sample receipts and health updates for the built-in demo gateway."""
    worked = False
    timestamp = datetime.now(timezone.utc)
    with connect() as db:
        sources = db.execute("SELECT id,tenant,created_at,last_seen FROM sources WHERE name='Gateway Penerimaan Gudang Demo' AND status='active'").fetchall()
        for source in sources:
            last_seen = datetime.fromisoformat(source["last_seen"]) if source["last_seen"] else None
            if last_seen is None or timestamp - last_seen >= timedelta(seconds=30):
                db.execute("UPDATE sources SET last_seen=? WHERE id=?", (timestamp.isoformat(), source["id"]))
                worked = True
            latest_receipt = db.execute("SELECT received_at FROM source_events WHERE source_id=? AND event_type='goods_receipt' ORDER BY rowid DESC LIMIT 1", (source["id"],)).fetchone()
            last_receipt = datetime.fromisoformat(latest_receipt["received_at"]) if latest_receipt else datetime.fromisoformat(source["created_at"])
            if timestamp - last_receipt >= timedelta(seconds=30) and (latest_receipt is None or timestamp - last_receipt >= timedelta(seconds=900)):
                source_event_id = uid("sevt")
                payload = {"sku": "KRT-002", "quantity": 2, "po_number": "PO-DEMO-1003", "reference": f"GR-DEMO-{timestamp.strftime('%Y%m%d%H%M%S')}"}
                db.execute("INSERT INTO source_events (id,source_id,event_type,payload,received_at) VALUES (?,?,?,?,?)", (source_event_id, source["id"], "goods_receipt", json.dumps(payload, ensure_ascii=False), timestamp.isoformat()))
                db.execute("UPDATE sources SET last_seen=? WHERE id=?", (timestamp.isoformat(), source["id"]))
                event(db, source["tenant"], "", "source.event.v1", {"source_id": source["id"], "source_event_id": source_event_id, "type": "goods_receipt", "simulated": True})
                worked = True
    return worked


def run_one() -> bool:
    """Claim and execute one scheduled task, including configured external ERP adapters."""
    db = connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        task_query = "SELECT t.*,s.runs,s.max_runs,s.interval_seconds,s.source_retry_count FROM tasks t JOIN schedules s ON t.id=s.task_id WHERE t.status='scheduled' AND s.next_run<=? ORDER BY s.next_run LIMIT 1"
        if getattr(db, 'is_postgres', False): task_query += " FOR UPDATE OF t SKIP LOCKED"
        task = db.execute(task_query, (now(),)).fetchone()
        if task is None:
            db.commit()
            return False
        tid, tenant = task["id"], task["tenant"]
        plan = json.loads(task["plan"])
        connected = {r[0] for r in db.execute("SELECT type FROM connections WHERE tenant=? AND status='connected'", (tenant,))}
        if "erp_odoo" in connected:
            connected.add("erp")
        if db.execute("SELECT 1 FROM sources WHERE tenant=? AND status='active'", (tenant,)).fetchone():
            connected.add("external_events")
        try:
            validate_steps(plan["steps"], connected)
            db.execute("UPDATE tasks SET status='running', updated_at=? WHERE id=?", (now(), tid))
            event(db, tenant, tid, "task.started.v1", {"run": task["runs"] + 1})
            results = []
            for index, step in enumerate(plan["steps"]):
                capability = CAPABILITIES[step["capability"]]
                if not matches(step.get("condition"), results):
                    results.append({"capability": step["capability"], "status": "condition_not_met"})
                    continue
                if capability["risk"] in ("action", "safe_action") and db.execute("SELECT 1 FROM steps WHERE task_id=? AND position=?", (tid, index)).fetchone():
                    results.append({"capability": step["capability"], "status": "already_executed"})
                    continue
                if step["capability"] == "external.latest_event":
                    source = db.execute("SELECT id,expected_interval_seconds FROM sources WHERE id=? AND tenant=? AND status='active'", (step["arguments"]["source_id"], tenant)).fetchone()
                    if source is None:
                        raise ValueError("Source inactive atau unavailable.")
                    requested_type = step["arguments"].get("event_type")
                    if not requested_type and db.execute("SELECT COUNT(DISTINCT event_type) FROM source_events WHERE source_id=?", (source['id'],)).fetchone()[0] > 1:
                        raise ValueError('Source has multiple data types; specify which event type to check.')
                    if requested_type:
                        latest = db.execute("SELECT event_type,payload,received_at FROM source_events WHERE source_id=? AND event_type=? ORDER BY rowid DESC LIMIT 1", (source["id"], requested_type)).fetchone()
                    else:
                        latest = db.execute("SELECT event_type,payload,received_at FROM source_events WHERE source_id=? ORDER BY rowid DESC LIMIT 1", (source["id"],)).fetchone()
                    if latest is None:
                        raise ValueError("Source has not sent data; the check cannot be verified.")
                    received = datetime.fromisoformat(latest["received_at"])
                    freshness_window = max(300, source['expected_interval_seconds'] * 2)
                    if datetime.now(timezone.utc) - received > timedelta(seconds=freshness_window):
                        raise StaleSourceDataError("The source has not sent a fresh update.")
                    result = {"event_type": latest["event_type"], "received_at": latest["received_at"], "data": json.loads(latest["payload"])}
                elif step["capability"] == "external.escalate":
                    result = {"message": step["arguments"]["message"], "delivery": "event"}
                    event(db, tenant, tid, "task.escalated.v1", result)
                elif step["capability"].startswith("erp.demo."):
                    result = run_demo_erp_capability(db, tenant, step["capability"], step["arguments"], tid, task["created_at"])
                    if result.get("notification"):
                        event(db, tenant, tid, "erp.demo.stock_threshold_alert.v1", result["notification"] | {"sku": result["sku"], "stock_after": result["stock_after"], "minimum_stock": result["minimum_stock"]})
                elif step["capability"].startswith("erp.odoo."):
                    result = run_odoo_capability(db, tenant, step["capability"], step["arguments"], f"kanca:{tid}:{index}")
                else:
                    result = capability["run"](step["arguments"])
                record = {"capability": step["capability"], "status": "completed", "result": result}
                if capability["risk"] in ("action", "safe_action"):
                    db.execute("INSERT INTO steps VALUES (?,?,?)", (tid, index, json.dumps(record, ensure_ascii=False)))
                results.append(record)
                if capability["risk"] in ("action", "safe_action"):
                    event(db, tenant, tid, "task.action_taken.v1", {"capability": step["capability"], "simulated": step["capability"] != "external.escalate"})
            run_number = task["runs"] + 1
            db.execute("INSERT INTO task_runs VALUES (?,?,?,?,?)", (uid("run"), tid, run_number, json.dumps(results, ensure_ascii=False), now()))
            output = {"steps": results, "runs_completed": run_number, "limitations": ["External data comes from the sending source and is not independently verified.", "Demo actions do not control physical devices."]}
            finished = run_number >= task["max_runs"]
            next_run = (datetime.now(timezone.utc) + timedelta(seconds=task["interval_seconds"])).isoformat()
            db.execute("UPDATE schedules SET runs=?, next_run=?, source_retry_count=0 WHERE task_id=?", (run_number, next_run, tid))
            db.execute("UPDATE tasks SET status=?, result=?, updated_at=? WHERE id=?", ("completed" if finished else "scheduled", json.dumps(output, ensure_ascii=False), now(), tid))
            if finished:
                release_task_source_automation(db, tid)
            event(db, tenant, tid, "task.completed.v1" if finished else "task.checked.v1", {"status": "completed" if finished else "scheduled", "run": run_number, "result_url": f"/v1/tasks/{tid}"})
        except StaleSourceDataError:
            db.rollback()
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT t.status,s.source_retry_count FROM tasks t JOIN schedules s ON t.id=s.task_id WHERE t.id=?", (tid,)).fetchone()
            leased = db.execute('SELECT 1 FROM task_source_automation_leases WHERE task_id=? LIMIT 1', (tid,)).fetchone()
            newly_leased = False
            if current and current['status'] == 'scheduled' and not leased:
                acquire_task_source_automation(db, tid, tenant, plan)
                leased = db.execute('SELECT 1 FROM task_source_automation_leases WHERE task_id=? LIMIT 1', (tid,)).fetchone()
                newly_leased = bool(leased)
            if current and current['status'] == 'scheduled' and leased and current['source_retry_count'] < 10:
                retry_number = current['source_retry_count'] + 1
                retry_delay = 180 if newly_leased else 30
                retry_at = (datetime.now(timezone.utc) + timedelta(seconds=retry_delay)).isoformat()
                waiting = {"steps": [], "runs_completed": task["runs"], "limitations": ["Waiting for fresh data from the selected source. Kanca will retry automatically; check that the gateway is running and sending to this source."]}
                db.execute("UPDATE schedules SET source_retry_count=?,next_run=? WHERE task_id=?", (retry_number, retry_at, tid))
                db.execute("UPDATE tasks SET status='scheduled',result=?,updated_at=? WHERE id=?", (json.dumps(waiting, ensure_ascii=False), now(), tid))
                event(db, tenant, tid, "task.checked.v1", {"status": "waiting_for_source", "retry": retry_number})
            elif current and current['status'] == 'scheduled':
                message = "Fresh sensor data was not received after automatic retries; the last available source observation was logged for review."
                stale_source_id = next((step.get("arguments", {}).get("source_id") for step in plan.get("steps", []) if step.get("capability") == "erp.demo.reconcile_source_receipt"), None)
                stale_details = {"source_id": stale_source_id, "sensor_status": "stale_or_no_data"}
                if stale_source_id:
                    source_row = db.execute("SELECT id,name,kind,last_seen FROM sources WHERE id=? AND tenant=?", (stale_source_id, tenant)).fetchone()
                    latest_row = db.execute("SELECT event_type,payload,received_at FROM source_events WHERE source_id=? ORDER BY rowid DESC LIMIT 1", (stale_source_id,)).fetchone()
                    if source_row:
                        stale_details["source"] = {key: source_row[key] for key in ("id", "name", "kind", "last_seen")}
                    if latest_row:
                        stale_details["latest_event"] = {"event_type": latest_row["event_type"], "received_at": latest_row["received_at"], "data": json.loads(latest_row["payload"])}
                event(db, tenant, tid, "task.escalated.v1", {"reason": "sensor_failed_to_send_fresh_data", **stale_details})
                db.execute("UPDATE tasks SET status='failed',result=?,updated_at=? WHERE id=?", (json.dumps({"error": message, "escalation": stale_details}), now(), tid))
                release_task_source_automation(db, tid)
                event(db, tenant, tid, "task.failed.v1", {"status": "failed", "error": message})
            db.commit()
            return True
        except Exception as exc:
            # Roll back local records. A completed ERP request cannot be undone by the database transaction.
            db.rollback()
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT status FROM tasks WHERE id=?", (tid,)).fetchone()
            if current and current[0] == "scheduled":
                db.execute("UPDATE tasks SET status='failed', result=?, updated_at=? WHERE id=?", (json.dumps({"error": str(exc)}), now(), tid))
                release_task_source_automation(db, tid)
                event(db, tenant, tid, "task.failed.v1", {"status": "failed"})
        db.commit()
        return True
    finally:
        db.close()
