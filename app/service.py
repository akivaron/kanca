import json
import math
from datetime import datetime, timedelta, timezone
from app.connectors.registry import CAPABILITIES
from app.storage import connect, event, now, uid


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


def run_one() -> bool:
    """Claim and finish one short, local simulation atomically. No network calls here."""
    db = connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        task_query = "SELECT t.*,s.runs,s.max_runs,s.interval_seconds FROM tasks t JOIN schedules s ON t.id=s.task_id WHERE t.status='scheduled' AND s.next_run<=? ORDER BY s.next_run LIMIT 1"
        if getattr(db, 'is_postgres', False): task_query += " FOR UPDATE OF t SKIP LOCKED"
        task = db.execute(task_query, (now(),)).fetchone()
        if task is None:
            db.commit()
            return False
        tid, tenant = task["id"], task["tenant"]
        plan = json.loads(task["plan"])
        connected = {r[0] for r in db.execute("SELECT type FROM connections WHERE tenant=? AND status='connected'", (tenant,))}
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
                        raise ValueError("Source data is stale; the check cannot be verified.")
                    result = {"event_type": latest["event_type"], "received_at": latest["received_at"], "data": json.loads(latest["payload"])}
                elif step["capability"] == "external.escalate":
                    result = {"message": step["arguments"]["message"], "delivery": "event"}
                    event(db, tenant, tid, "task.escalated.v1", result)
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
            db.execute("UPDATE schedules SET runs=?, next_run=? WHERE task_id=?", (run_number, next_run, tid))
            db.execute("UPDATE tasks SET status=?, result=?, updated_at=? WHERE id=?", ("completed" if finished else "scheduled", json.dumps(output, ensure_ascii=False), now(), tid))
            event(db, tenant, tid, "task.completed.v1" if finished else "task.checked.v1", {"status": "completed" if finished else "scheduled", "run": run_number, "result_url": f"/v1/tasks/{tid}"})
        except Exception as exc:
            # No external side effects exist in the demo connector. Roll back partial steps.
            db.rollback()
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT status FROM tasks WHERE id=?", (tid,)).fetchone()
            if current and current[0] == "scheduled":
                db.execute("UPDATE tasks SET status='failed', result=?, updated_at=? WHERE id=?", (json.dumps({"error": str(exc)}), now(), tid))
                event(db, tenant, tid, "task.failed.v1", {"status": "failed"})
        db.commit()
        return True
    finally:
        db.close()
