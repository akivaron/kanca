# Kanca — Agent Platform Foundation

An API-first backend for cross-domain agent tasks. Business and device connector examples use **simulated** data and actions. See [PLAN.md](PLAN.md) for the project roadmap.

## Quick Start

Requires Docker and Docker Compose. Copy `.env.example` to `.env`, update `KANCA_API_KEY` and `POSTGRES_PASSWORD`, then run:

```bash
./run.sh
```

Run `./restart.sh` to rebuild the image and restart the API and worker without removing data volumes. To stop the services, run `./stop.sh`. View logs with `docker compose logs -f`.

The demo UI is available at `http://localhost:8765`. API documentation is at `http://localhost:8765/docs`, and the health check is at `http://localhost:8765/health`. The server uses `KANCA_API_KEY` from `.env` to create a local UI session; external API clients authenticate with the `X-API-Key` header. PostgreSQL is available only on the internal Compose network, and its data is stored in the `kanca-postgres` volume.

### Legacy SQLite Data

PostgreSQL is a new database; data from the old SQLite volume is **not migrated automatically**. To preserve that data before switching to the new database, stop the API and worker, make sure PostgreSQL is running, then run the migration once:

```bash
docker compose up -d db
docker compose stop api worker
docker compose build api
docker compose run --rm --no-deps api python -m app.migrate_sqlite /data/kanca.db
./run.sh
```

The migration reads SQLite without modifying it, preserves IDs and event cursors, and refuses to run if PostgreSQL already contains data. Do not allow the API, worker, or any other process to write to either database during migration. If the SQLite file is in another location, adjust the path inside the container. Check the result before removing the old volume; `./stop.sh` does not remove volumes.

`POSTGRES_PASSWORD` is used when the PostgreSQL volume is first created. Changing it in `.env` after initialization does not automatically change the stored password. Use URL-safe characters for the Compose password.

To try the UI, select a simulated connector and send an instruction. **New conversation** starts a separate topic; use the sidebar to reopen conversation history. Kanca includes the latest 12 messages from the topic as model context, and each generated plan becomes its own task. Chat plans that only read data or use registered safe actions run automatically. Other actions require approval. Safe actions are currently limited to simulated reminders and escalation events. Task status updates automatically. Tasks created directly through the API or MCP, and reruns, require approval. The UI creates a local session automatically, so anyone who can access it can use the demo data and actions. Compose binds the app to localhost; add proper user authentication before exposing it to a network. After changing code, run `./run.sh` to rebuild the Docker image.

The **Background tasks** menu shows tasks from all conversations. New tasks are created through chat; schedules for unfinished tasks can be changed and must be approved again. Removing a task from the list stops an active task and archives it; its history and events remain stored. A task is work run by the shared worker, not a separate worker process.

Use **Pause** to suspend the next check and **Resume** to reactivate it. Progress and completed actions remain stored. If a scheduled check is overdue when resumed, it may run immediately. Pausing does not cancel a check that has already started. Schedule changes made while paused still require approval again. API endpoints are available at `POST /v1/tasks/{id}/pause` and `POST /v1/tasks/{id}/resume`.

The **Notifications** menu shows up to 100 recent task updates, including approvals, completions, failures, escalations, cancellations, pauses, and resumptions. Choose which notification types to display; preferences and read status are stored per tenant. Completed, failed, or stopped tasks can be rerun from a notification, the task list, or chat. A rerun creates a new task from scratch and requires approval; the original task history remains. These notifications appear in the app and are available through the API; they are not operating-system push notifications. Worker process termination is not detected automatically.

Under **Integrations → Device Sources**, create and manage sources that send JSON events over HTTP. The **Public Sources** tab includes 100 BMKG village-level forecast feeds across 38 provinces and 400 public CCTV feeds. Public feeds are not polled on a schedule by default. **Get Data** and AI-routed chat requests fetch a single update; enable automation on a source to poll it regularly. BMKG forecasts cover three days in three-hour intervals and update twice daily. BMKG limits requests to 60 per minute per IP and requires attribution. Save the token when creating a source; the server stores only its hash. Example request from the same machine:

```bash
curl -X POST http://localhost:8765/v1/ingest/SOURCE_ID \
  -H 'Authorization: Bearer SOURCE_TOKEN' -H 'Content-Type: application/json' \
  -d '{"type":"temperature","data":{"value":29}}'
```

Events are stored, visible in the UI, and emitted as `source.event.v1` for subscribers. Each source stores `expected_interval_seconds` (default 300) to estimate its reception status: waiting for data, recent, overdue, or inactive. This status reflects only when the last event arrived; Kanca does not monitor the gateway process directly. A task considers data fresh for the greater of five minutes or twice the expected interval. The UI flags observations older than this limit and marks uncertain media results. Sources are soft-deleted so their history remains stored. Source event exports are available at `/v1/sources/{id}/events/export`; platform event exports are available at `/v1/events/export`. Both support `format=json|csv`, up to 1,000 rows per request, and an `after` cursor to continue an export. CSV exports protect text that spreadsheet software could interpret as formulas. The Compose app accepts localhost connections only; other devices require a secure gateway or deployment with HTTPS. Video streaming, QR/Bluetooth pairing, and device control are not available. Do not send video or photos through this endpoint (32 KiB limit).

Approved tasks can read the latest event from one active source through `external.latest_event` and trigger `external.escalate` as a `task.escalated.v1` event when a condition is met. The Integrations UI provides a threshold-rule builder for numeric fields already received; created tasks still require approval and emit at most one escalation per step. Data older than the freshness limit cannot be verified. Assign one Kanca source to each sensor or entity to prevent readings from different devices from overwriting one another. Events do not automatically wake tasks: tasks check data according to their approved schedule. An escalation is an event for a consumer, not a message sent directly.

### Device Gateways

Examples in `gateways/` run separately from the API and worker; install optional dependencies with `pip install -r gateways/requirements.txt`. For each gateway, first create a source in the UI and set `KANCA_URL`, `KANCA_SOURCE_ID`, and `KANCA_SOURCE_TOKEN` in the gateway environment. Run the gateway on a machine that can access both Kanca and the device; do not commit tokens. For cross-machine connections, use HTTPS and a secure network gateway. The default Compose configuration does not expose ports to other devices.

- **Home Assistant:** set `HA_URL`, `HA_TOKEN`, and `HA_ENTITIES` (for example, `sensor.temperature`), then run `python gateways/home_assistant.py`. The gateway reads entity state every 30 seconds; `GATEWAY_INTERVAL` can be changed. Matter devices already added to and supported by Home Assistant can be used through their available entities; Kanca does not pair Matter devices itself. State is forwarded as a string in `data.state`.
- **MQTT:** set `MQTT_HOST`, `MQTT_TOPIC`, and, if needed, `MQTT_USERNAME` and `MQTT_PASSWORD`, then run `python gateways/mqtt.py`. The broker must provide trusted TLS; the default port is `8883`. Messages must be JSON objects and are placed in `data.payload`. Gateway delivery is best effort, with no local queue or guarantee against message loss.
- **Camera:** set `CAMERA_SOURCE` to a camera index or stream URL supported by OpenCV, then run `python gateways/camera_motion.py`. The gateway sends only estimated motion metadata; it does not send frames, recognize objects, or verify packages. Motion can be caused by lighting changes, so treat it as a signal that needs review.
- **ESP32:** `examples/esp32/kanca_sensor.ino` demonstrates sending dummy readings over HTTPS. Fill in the Wi-Fi, URL, token, and CA certificate configuration, then replace the dummy value with a sensor reading. The example has not been tested on physical hardware.

These gateways have not been tested with hubs, brokers, cameras, or physical devices, do not have comprehensive recovery mechanisms, and do not provide device control. Use them for local experiments before building a production deployment. For the mini PC package that sends image or audio snapshots to the Kanca server for Baseten analysis, see [mini-pc-gateway/README.md](mini-pc-gateway/README.md).

#### Run a Gateway with Docker

To run a gateway with Docker on the same machine as Kanca:

1. Create a source on the **External Sources** page and save the ID and token, which are shown only once.
2. Copy one of `gateways/home-assistant.env.example`, `gateways/mqtt.env.example`, or `gateways/camera.env.example` to `gateways/.env.home-assistant`, `gateways/.env.mqtt`, or `gateways/.env.camera`. Fill in the ID, token, and relevant device or service configuration. These files are ignored by Git and are not copied into the image.
3. Start the selected profile, for example:

   ```bash
   docker compose -f compose.yaml -f compose.gateways.yaml --profile home-assistant up -d --build
   ```

   Use the `mqtt` or `camera` profile for other gateways. For a network camera, `CAMERA_SOURCE` can be an RTSP URL supported by OpenCV; USB devices require appropriate host device access configuration, which is not provided automatically. `./stop.sh` stops all gateway profiles along with Kanca.

Each Home Assistant gateway is configured for one entity and one Kanca source. Numeric values are provided as `data.value`, while the original value is available as `data.state`; `unknown` and `unavailable` are not forwarded as readings. MQTT skips retained messages because their measurement time cannot be confirmed. Kanca recognizes data structure only after data has been received; send an initial reading before requesting monitoring. Marking data as new based on its receipt time does not prove the device or hub took a new measurement at that time.

### Frontend Development

The frontend uses React and Vite in `frontend/`. For development, start the API on port 8765, then run `npm install` and `npm run dev` from that directory. Vite proxies `/v1` requests to the API. To serve the built frontend through FastAPI without Docker, run `npm run build` first.

### Run Without Docker

Create a virtual environment, install dependencies with `pip install -r requirements.txt`, and set `KANCA_API_KEY` and `DATABASE_URL` for PostgreSQL. Run `uvicorn app.main:app --reload --port 8765` and `python -m app.worker` in separate terminals. If `DATABASE_URL` is not set, SQLite through `KANCA_DB_PATH` remains available for testing and legacy migrations.

## API Examples

```bash
export KANCA_API_KEY='change-me'
curl -X POST http://localhost:8765/v1/connections \
  -H "X-API-Key: $KANCA_API_KEY" -H 'Content-Type: application/json' \
  -d '{"type":"device_demo"}'

curl -X POST http://localhost:8765/v1/tasks \
  -H "X-API-Key: $KANCA_API_KEY" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: example-1' \
  -d '{"instruction":"Check the temperature","explicit_steps":[{"capability":"device.read_temperature","arguments":{}}]}'
```

Get the `id` from the response, review the `plan`, then approve its version:

```bash
curl -X POST "http://localhost:8765/v1/tasks/TASK_ID/approve" \
  -H "X-API-Key: $KANCA_API_KEY" -H 'Content-Type: application/json' \
  -d '{"version":1}'
curl "http://localhost:8765/v1/tasks/TASK_ID" -H "X-API-Key: $KANCA_API_KEY"
curl "http://localhost:8765/v1/events" -H "X-API-Key: $KANCA_API_KEY"
```

For model mode, set `BASETEN_API_KEY` and submit a task without `explicit_steps`. Muse Spark Open on Baseten proposes capabilities and a schedule; the backend validates them and still requires approval. Configure the model with `BASETEN_MODEL`. Without a key, use `explicit_steps`; this is demo mode, not AI. `examples/poll_events.py` shows an external consumer reading events with a cursor; production consumers should store the cursor and IDs of processed events.

## MCP Integration

Kanca provides a local MCP server over stdio. Available tools include listing sources and connections, reading events and task results, asking natural-language questions about recent source observations (`ask_source`), creating task proposals, and proposing reruns. Questions and the latest events needed to answer them are sent to Baseten. Source answers use only received events and stored camera analysis; MCP cannot request a new camera frame. Task and rerun proposals still require owner approval in Kanca. Direct physical device control is not available; each control adapter must define its own specific actions and approval policy.

After `./run.sh`, an MCP client that supports stdio can run the following command from the project directory:

```bash
docker compose exec -T -e KANCA_URL=http://api:8000 api python -m app.mcp_server
```

This command starts the MCP process; it is not an interactive command to type and use as a chat. Configure the MCP client with command `docker` and arguments `compose`, `exec`, `-T`, `-e`, `KANCA_URL=http://api:8000`, `api`, `python`, `-m`, `app.mcp_server`. Run it from the project directory so Compose can find its configuration. The API key is read from the container environment and is not sent through the model. Access to this process and API key gives the agent access to this demo account data; share access carefully. Use from another host requires separate transport and authentication; a public HTTP MCP endpoint is not available.

### Recurring Monitoring

Add a `schedule` to a task, for example: `{"interval_seconds":60,"max_runs":5}`. For explicit steps, an optional condition such as `{"step":0,"field":"temperature_c","operator":"gt","value":28}` checks the result of a previous step. Available operators are `eq`, `ne`, `gt`, `gte`, `lt`, and `lte`. Each action runs only once per step per task; each check result is available at `/v1/tasks/{id}/runs`. All connectors are currently simulated.

### Webhooks

Create a subscription with `POST /v1/webhook-subscriptions` using the body `{"url":"https://example.com/webhook"}`. The secret is returned only when the subscription is created; store it on the receiving side. Filter events with `event_types` when creating the subscription or with `PUT /v1/webhook-subscriptions/{id}/event-types`; the default `["*"]` means all events. New events and deliveries are created in the same transaction. The worker sends them with the `X-Kanca-Timestamp` and `X-Kanca-Signature: sha256=<hex>` headers, using HMAC-SHA256 over `timestamp + "." + raw_body`. Receivers must verify the signature, limit the timestamp age, and deduplicate by event ID. Delivery is at least once, with up to five attempts; see `/v1/webhook-deliveries`. Webhooks accept only HTTPS on port 443 and public IP addresses; redirects are not followed. A subscription receives only events created after it becomes active and matching its filter.

## Current Status and Limitations

This is a local MVP, not a complete implementation of PLAN.md. Compose uses PostgreSQL; one API key still maps to one tenant. Webhook secrets are stored in the database; secure the volume and use TLS in front of the API. LangGraph, Celery, universal pairing, SAM, and real-world actions are not included. Device integrations and Baseten require direct testing. Do not use this for production data or actions until multi-tenant authentication, secret storage, policies, and recovery are strengthened.

## Verification

```bash
python -m pytest -q
```

Additional PostgreSQL tests run with `KANCA_TEST_DATABASE_URL` pointing to a test database that can create and drop schemas. Do not use a production database.
