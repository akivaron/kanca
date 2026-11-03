---
name: kanca-project
description: Work on the Kanca AI-agent platform, including its API, chat, monitoring worker, notifications, MCP interface, and IoT or camera gateway. Use for implementation, debugging, testing, or architecture questions in this repository.
---

# Kanca project

Kanca is an API-first agent platform intended for multiple domains. Business oversight is the initial use case; smart home, education, and other domains must not be hardcoded into the core. The user prefers Indonesian and a natural, nontechnical tone in product-facing chat. `PLAN.md` is a roadmap, not proof that a feature is implemented.

## Start here

- Read the root `AGENTS.md` and follow its linked command instructions. Use this skill as a navigation map; inspect relevant code before making changes because implementation and model APIs can evolve.
- Do not print, commit, or copy secrets from `.env`, source tokens, camera URLs, or gateway `config.json` into outputs. Prefer `.env.example` and documented variable names; inspect secret-bearing files only when necessary and avoid exposing their contents.
- Keep Kanca server APIs and the Baseten key server-side. Mini PC gateways receive only a per-source token; they do not receive the Baseten key.
- Preserve user-visible evidence and truthful limitations. Do not claim physical-device compatibility, live Baseten success, video verification, or production readiness without actual verification.

## Architecture and file map

| Concern | Entry points |
| --- | --- |
| REST API, auth, chat, sources, tasks, notifications | `app/main.py` |
| PostgreSQL/SQLite storage, transactional events, webhook outbox, legacy migration | `app/storage.py`, `app/migrate_sqlite.py` |
| Task validation, conditions, monitoring and execution | `app/service.py`, `app/worker.py` |
| Baseten text planner | `app/planner.py`; `BASETEN_MODEL`, `BASETEN_API_KEY` |
| Connector metadata and simulated capabilities | `app/connectors/registry.py` |
| Baseten vision/audio and media validation | `app/media.py`; `BASETEN_MEDIA_MODEL` |
| Webhook signing, retries, address validation | `app/webhooks.py` |
| Local stdio MCP wrapper over REST | `app/mcp_server.py`, `app/mcp_client.py`; `ask_source` answers from stored observations |
| React/Vite chat and task UI | `frontend/src/App.jsx`, `frontend/src/style.css` |
| Standalone mini PC gateway and setup | `mini-pc-gateway/gateway.py`, `setup.py`, `detect.py`, `README.md` |
| Earlier standalone integrations | `gateways/` |
| Tests | `tests/test_platform.py`, `tests/test_media_gateway.py`, `tests/test_mcp_client.py` |

## Behavior that changes implementation decisions

- Agent-generated plans are validated server-side; do not execute model-generated shell, SQL, or unrestricted tools. The registry classifies tools as `read`, `safe_action`, or `action`.
- Chat plans containing only `read`/`safe_action` run automatically. Other chat actions require owner approval. API/MCP task proposals and reruns currently require approval. Schedule edits require renewed approval. Re-check the implementation when changing this policy.
- Compose uses PostgreSQL; SQLite remains available for tests and legacy migration. Existing SQLite data is not imported automatically: follow the offline migration procedure in `README.md`. One worker performs scheduled checks; a task is not a separate OS process. Pause/resume, rerun, and event history must preserve this distinction. Actions are deduplicated per task step.
- Events drive notifications and signed webhooks; webhook delivery is at-least-once and consumers deduplicate by event ID. Source ingestion uses per-source tokens. Treat external data and model output as untrusted.
- Source health is inferred from `last_seen` against each source's `expected_interval_seconds`; it does not prove the gateway process is running. Source and platform event exports are JSON/CSV and capped at 10,000 rows per request. Numeric threshold rules are task plans and require approval; external escalations are emitted at most once per task step.
- Notification event types are configurable per tenant. Webhook subscriptions filter event types at enqueue time; legacy subscriptions default to all event types. Update these behaviors alongside their API and UI.
- Vision/audio are opt-in per source except the explicitly requested DKI public CCTV pack, whose two sources enable vision analysis and send periodic snapshots through Kanca to Baseten. Raw media is not stored in the database. Counts are estimates, not verified inventory; uncertain results must not become fabricated facts. RTSP/HLS capture, BLE, MQTT, and other gateways require real-device validation.
- Mini PC gateway currently includes RTSP and the allowlisted DKI public HLS feeds, MQTT, HTTP JSON, Home Assistant, custom event input, and limited direct BLE. Direct Zigbee, Z-Wave and Matter controllers, automatic universal pairing, physical control, and offline queues are not implemented. Hardware detection returns hints, not compatibility guarantees.
- Public Sources includes 100 curated Indonesian BMKG weather feeds at village/urban-village (`adm4`) level, 400 public CCTV HLS feeds (200 in DI Yogyakarta and 200 additional feeds across 11 Indonesian regions), BMKG earthquake/weather presets, and Open-Meteo/USGS feeds. The additional CCTV playlists were checked for a valid HLS response and cataloged from the public PantauCCTV index; streams can still change or go offline. New public source records and automation are disabled by default; camera audio remains opt-in. Public camera and JSON feeds in the mini PC gateway are marked `on_demand`: Get Data and AI-routed chat source requests request one fresh read, then public polling stops. Per-source automation can be explicitly enabled at 5, 10, 30, or 60 second intervals; RTSP/local and unmarked integrations retain their configured polling behavior. The gateway accepts up to 512 configured sources, allows public HLS only from its explicit government/provider host allowlist, verifies source state and one-shot requests with each source's token, and serializes BMKG HTTP JSON polls with a 1.1-second minimum gap to stay below BMKG's documented 60 requests/minute/IP limit. Display BMKG attribution when using the forecast data.
- Chat uses the language model to infer whether a message requests fresh source data and to choose among registered sources. The server validates model-selected source IDs against the tenant's camera/IoT inventory before queueing reads; the model cannot create a source URL or call the gateway directly. Ambiguous requests are clarified instead of guessed.
- Source questions generally use stored events, but matching camera questions in chat request one new analyzed frame and wait up to 60 seconds for the gateway. Raw camera frames are not retained. Physical device control requires explicit protocol-specific adapters and approval policies; current gateway ingestion paths do not expose universal control.
- The local web UI automatically obtains a session and Docker binds it to localhost. Do not expose the whole UI publicly without proper authentication; gateway ingress must expose only the intended ingest endpoints over HTTPS.

## Run and verify

- Local Compose: `./run.sh`; stop with `./stop.sh`. UI `http://localhost:8765`, API docs `/docs`, health `/health`.
- Frontend development: `cd frontend`, `npm install`, `npm run dev` with API on port 8765; production assets use `npm run build` and are served by FastAPI.
- Backend tests: `python -m pytest -q`. PostgreSQL-specific tests require `KANCA_TEST_DATABASE_URL` pointing to a disposable database. Add focused tests for policy, persistence, retries, and race conditions when relevant.
- Gateway setup and prerequisites: `mini-pc-gateway/README.md`; `python3 mini-pc-gateway/detect.py` performs local read-only hardware inventory. Do not assume access to Docker, npm/PyPI, Baseten, radios, or physical devices; report what was and was not exercised.
- For local MCP client configuration, see the MCP section in `README.md`. The existing MCP server is stdio-only and proposes tasks without bypassing approval.

## Maintenance

When a change materially alters architecture, commands, safety boundaries, or supported protocols, update this skill alongside the relevant implementation and documentation. Keep secrets and machine-specific credentials out of it. Prefer updating the affected section rather than appending a chronological log.
