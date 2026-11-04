# Kanca

<img width="3340" height="1666" alt="image" src="https://github.com/user-attachments/assets/61376d0a-d2bd-4795-9a9d-b1e358eb22de" />

Kanca is an API-first platform for AI-assisted monitoring and task automation across business systems and connected devices. It uses Baseten for natural-language planning, validates every generated plan on the server, and records task activity and escalations in a shared event stream.

The project includes simulated business, device, ERP, and warehouse-gateway integrations for demos, plus a built-in Odoo connector for inventory and purchase orders.

## Quick start

Requirements: Docker and Docker Compose.

1. Copy `.env.example` to `.env`.
2. Set `KANCA_API_KEY` and `POSTGRES_PASSWORD`.
3. Start Kanca:

   ```bash
   ./run.sh
   ```

Open the demo at [http://localhost:8765](http://localhost:8765). The API reference is at [http://localhost:8765/docs](http://localhost:8765/docs), and the health endpoint is `/health`.

Use `./restart.sh` to rebuild and restart the API and worker while keeping database volumes. Use `./stop.sh` to stop the services. View service logs with `docker compose logs -f`.

The web UI creates a local session automatically. External API clients authenticate with the `X-API-Key` header. Compose binds Kanca to localhost by default.

## Demo workflow

Create a conversation and send an instruction in natural language. Baseten turns monitoring requests into scheduled tasks using only capabilities available to the tenant. The server validates the plan before execution. Read-only plans and registered safe actions can start automatically; other actions require approval. Tasks created through the API or MCP require approval.

The **Background tasks** view shows tasks from all conversations. You can pause, resume, update a schedule, rerun a finished task, or archive it. Schedule changes require renewed approval. The shared worker executes scheduled tasks and updates their results and event history.

The **Notifications** view displays recent task events, including approvals, completions, failures, and escalations. Notification preferences and read status are stored per tenant. Events are also available through the API and webhooks.

## ERP demo

Kanca provides a stateful simulated ERP for demos. It contains sample stock and open purchase orders:

| SKU | Item | Stock | Minimum | Open purchase order |
| --- | --- | ---: | ---: | --- |
| `KRT-001` | Demo Carton | 1 carton | 3 cartons | `PO-DEMO-1001`: 4 cartons |
| `KRT-002` | Reserve Demo Carton | 0 cartons | 6 cartons | `PO-DEMO-1003`: 5 cartons |
| `BRG-014` | Shelf Component | 24 pcs | 10 pcs | `PO-DEMO-1002`: 12 pcs |

When no ERP is connected, Kanca provisions the demo ERP during planning. You can also create one directly with `POST /v1/erp-connections/demo`. Use `GET /v1/connections/{id}/resources` to view its capabilities and `POST /v1/erp-connections/{id}/reset-demo` to restore the sample data.

The demo gateway, **Gateway Penerimaan Gudang Demo**, is provisioned with the demo ERP when no warehouse IoT source is registered. Its worker-generated heartbeat keeps the simulated sensor online, and it produces a sample goods receipt every 15 minutes. The sample receipt is two cartons of `KRT-002` against `PO-DEMO-1003`, whose ordered quantity is five cartons. This scenario demonstrates both a quantity discrepancy and a post-receipt stock shortage.

Pause or resume the simulated gateway with `POST /v1/sources/{id}/demo-gateway` and either `{"enabled":false}` or `{"enabled":true}`. A paused gateway allows a monitoring task to demonstrate stale-source escalation.

### Connect a real gateway

Send receipts to the source ingest endpoint using event type `goods_receipt`. The event data must include a SKU and an integer quantity; the purchase order number and shipment reference are optional.

```bash
curl -X POST http://localhost:8765/v1/ingest/SOURCE_ID \
  -H 'Authorization: Bearer SOURCE_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"type":"goods_receipt","data":{"sku":"KRT-002","quantity":2,"po_number":"PO-DEMO-1003","reference":"GR-DEMO-01"}}'
```

The recurring reconciliation task checks each new receipt against open demo purchase orders and calculates stock after receipt. It records a `task.escalated.v1` event with the source and receipt details when the receipt quantity differs from its purchase order, the data is incomplete or ambiguous, or stock is at least three cartons below the item's minimum. If the source stops sending data, Kanca retries and then records an escalation with the latest available observation. CCTV sources are not used for quantity reconciliation.

The simulated reconciliation capabilities are `erp.demo.inventory`, `erp.demo.purchase_orders`, and `erp.demo.reconcile_source_receipt`. The `erp.demo.receive_shipment` action updates demo inventory and requires task approval. Escalations are stored in Kanca; a configured webhook consumer can forward them to other systems or staff.

## Odoo connector

Connect Odoo with `POST /v1/erp-connections/odoo`, supplying a connection name, HTTPS base URL, optional database name, and API key. The API key is encrypted in the Kanca database and is never returned by the API. New connections remain pending until verified with `POST /v1/erp-connections/{id}/test`.

Set a persistent Fernet key in `KANCA_CREDENTIALS_KEY` before creating an Odoo connection. Generate a key with:

```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

The Odoo connector reads inventory and open purchase orders. Approved write actions can create a draft purchase order or update a note on a draft order. It does not confirm or send purchase orders. Odoo JSON-2 API access requires an Odoo Custom plan; grant the API key only the model access needed by the integration.

Available Odoo capabilities: `erp.odoo.stock_levels`, `erp.odoo.purchase_orders`, `erp.odoo.create_draft_purchase_order`, and `erp.odoo.update_draft_purchase_order_note`. Each step requires the connection's `connection_id`.

## Device sources and gateways

Under **Integrations → Device Sources**, create sources that send JSON events to Kanca. The server stores a hash of each source token; save the token when it is created. Events appear in the UI and are emitted as `source.event.v1` for subscribers.

The **Public Sources** catalog includes 100 BMKG village-level forecast feeds and 400 public CCTV feeds. Public feeds are read on demand by default. Use **Get Data** or an AI-routed chat request for a one-time update, or enable source automation for regular polling. BMKG forecasts cover three days in three-hour intervals and update twice daily. Attribute BMKG when presenting its forecast data.

Source health is estimated from the time of the latest event and the configured `expected_interval_seconds`. A monitoring task treats data as fresh for the greater of five minutes or twice the expected interval. Source events can be exported from `/v1/sources/{id}/events/export` and platform events from `/v1/events/export`; both endpoints support JSON or CSV and cursor-based pagination.

Example gateways are in `gateways/`. Install their optional dependencies with `pip install -r gateways/requirements.txt`. Create a source in Kanca, then set `KANCA_URL`, `KANCA_SOURCE_ID`, and `KANCA_SOURCE_TOKEN` in the gateway environment.

- **Home Assistant:** configure `HA_URL`, `HA_TOKEN`, and `HA_ENTITIES`, then run `python gateways/home_assistant.py`. The gateway forwards entity state every 30 seconds.
- **MQTT:** configure `MQTT_HOST`, `MQTT_TOPIC`, and optional credentials, then run `python gateways/mqtt.py`. The broker should provide TLS on port `8883`.
- **Camera motion:** set `CAMERA_SOURCE` to an OpenCV-compatible camera index or stream URL, then run `python gateways/camera_motion.py`. It forwards motion metadata; camera counts remain visual estimates.
- **ESP32:** `examples/esp32/kanca_sensor.ino` demonstrates sending HTTPS readings. Configure Wi-Fi, the source URL and token, and the CA certificate before use.

For Docker-based gateways, copy the appropriate `gateways/*.env.example` file to the matching ignored environment file, configure the source ID and token, then start a profile. For example:

```bash
docker compose -f compose.yaml -f compose.gateways.yaml --profile home-assistant up -d --build
```

Use `mqtt` or `camera` as the profile name for those gateways. Gateway examples send data to Kanca; device control is provided only by explicitly implemented, protocol-specific capabilities.

## API usage

Create a simulated device connection:

```bash
curl -X POST http://localhost:8765/v1/connections \
  -H "X-API-Key: $KANCA_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"type":"device_demo"}'
```

Create and approve a task:

```bash
curl -X POST http://localhost:8765/v1/tasks \
  -H "X-API-Key: $KANCA_API_KEY" \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: temperature-check-1' \
  -d '{"instruction":"Check the temperature","explicit_steps":[{"capability":"device.read_temperature","arguments":{}}]}'

curl -X POST http://localhost:8765/v1/tasks/TASK_ID/approve \
  -H "X-API-Key: $KANCA_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"version":1}'
```

Set `BASETEN_API_KEY` to enable natural-language planning through Baseten and set `BASETEN_MODEL` to select the model. Without a Baseten key, create tasks with `explicit_steps`.

Recurring schedules use an `interval_seconds` value and a `max_runs` count, for example `{"interval_seconds":60,"max_runs":5}`. Conditions can compare fields from earlier steps with `eq`, `ne`, `gt`, `gte`, `lt`, or `lte`. Each action runs once per step per task; check results are available at `/v1/tasks/{id}/runs`.

## MCP integration

Kanca provides a local MCP server over stdio. It can list sources and connections, read events and task results, answer questions about recent source observations, create task proposals, and propose reruns. Task and rerun proposals require approval.

After `./run.sh`, start the MCP server from the project directory:

```bash
docker compose exec -T -e KANCA_URL=http://api:8000 api python -m app.mcp_server
```

Configure the MCP client to run `docker compose exec -T -e KANCA_URL=http://api:8000 api python -m app.mcp_server`. The API key is read from the container environment.

## Webhooks

Create a subscription with `POST /v1/webhook-subscriptions`, for example:

```json
{"url":"https://example.com/webhook","event_types":["task.escalated.v1"]}
```

Kanca returns the signing secret once when the subscription is created. Store it securely. Webhook requests include `X-Kanca-Timestamp` and `X-Kanca-Signature`; verify the HMAC-SHA256 signature, enforce a timestamp age limit, and deduplicate deliveries by event ID. Delivery is at least once with up to five attempts. Subscriptions accept HTTPS endpoints on port 443 and do not follow redirects.

## Database migration

Compose uses PostgreSQL. SQLite remains available for local development and existing SQLite data is not imported automatically. To migrate a legacy SQLite database, stop the API and worker, ensure PostgreSQL is running, then run:

```bash
docker compose up -d db
docker compose stop api worker
docker compose build api
docker compose run --rm --no-deps api python -m app.migrate_sqlite /data/kanca.db
./run.sh
```

The migration preserves IDs and event cursors, reads SQLite without modifying it, and refuses to run if PostgreSQL already contains data. Do not allow processes to write to either database during migration. `POSTGRES_PASSWORD` is applied when the PostgreSQL volume is first created; changing it in `.env` does not change the stored database password.

## Development

The frontend uses React and Vite. Start the API on port `8765`, then run `npm install` and `npm run dev` from `frontend/`. Vite proxies `/v1` requests to the API. Build the frontend with `npm run build` to serve it through FastAPI.

To run without Docker, install `requirements.txt`, configure `KANCA_API_KEY` and `DATABASE_URL`, then start the API and worker in separate terminals:

```bash
uvicorn app.main:app --reload --port 8765
python -m app.worker
```

Without `DATABASE_URL`, Kanca uses SQLite at `KANCA_DB_PATH`. Keep API keys, webhook secrets, ERP credentials, and source tokens out of source control. Use TLS and an appropriate authentication layer before exposing Kanca beyond localhost.
