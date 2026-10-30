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
| Local stdio MCP wrapper over REST | `app/mcp_server.py`, `app/mcp_client.py` |
| React/Vite chat and task UI | `frontend/src/App.jsx`, `frontend/src/style.css` |
| Standalone mini PC gateway and setup | `mini-pc-gateway/gateway.py`, `setup.py`, `detect.py`, `README.md` |
| Earlier standalone integrations | `gateways/` |
| Tests | `tests/test_platform.py`, `tests/test_media_gateway.py`, `tests/test_mcp_client.py` |

## Behavior that changes implementation decisions

- Agent-generated plans are validated server-side; do not execute model-generated shell, SQL, or unrestricted tools. The registry classifies tools as `read`, `safe_action`, or `action`.
- Chat plans containing only `read`/`safe_action` run automatically. Other chat actions require owner approval. API/MCP task proposals and reruns currently require approval. Schedule edits require renewed approval. Re-check the implementation when changing this policy.
- Compose uses PostgreSQL; SQLite remains available for tests and legacy migration. Existing SQLite data is not imported automatically: follow the offline migration procedure in `README.md`. One worker performs scheduled checks; a task is not a separate OS process. Pause/resume, rerun, and event history must preserve this distinction. Actions are deduplicated per task step.
- Events drive notifications and signed webhooks; webhook delivery is at-least-once and consumers deduplicate by event ID. Source ingestion uses per-source tokens. Treat external data and model output as untrusted.
- Vision/audio are opt-in per source, passed through Kanca to Baseten, and do not store raw media in the database. Counts are estimates, not verified inventory; uncertain results must not become fabricated facts. RTSP capture, BLE, MQTT, and other gateways require real-device validation.
- Mini PC gateway currently includes RTSP, MQTT, HTTP JSON, Home Assistant, custom event input, and limited direct BLE. Direct Zigbee, Z-Wave and Matter controllers, automatic universal pairing, physical control, and offline queues are not implemented. Hardware detection returns hints, not compatibility guarantees.
- The local web UI automatically obtains a session and Docker binds it to localhost. Do not expose the whole UI publicly without proper authentication; gateway ingress must expose only the intended ingest endpoints over HTTPS.

## Run and verify

- Local Compose: `./run.sh`; stop with `./stop.sh`. UI `http://localhost:8765`, API docs `/docs`, health `/health`.
- Frontend development: `cd frontend`, `npm install`, `npm run dev` with API on port 8765; production assets use `npm run build` and are served by FastAPI.
- Backend tests: `python -m pytest -q`. PostgreSQL-specific tests require `KANCA_TEST_DATABASE_URL` pointing to a disposable database. Add focused tests for policy, persistence, retries, and race conditions when relevant.
- Gateway setup and prerequisites: `mini-pc-gateway/README.md`; `python3 mini-pc-gateway/detect.py` performs local read-only hardware inventory. Do not assume access to Docker, npm/PyPI, Baseten, radios, or physical devices; report what was and was not exercised.
- For local MCP client configuration, see the MCP section in `README.md`. The existing MCP server is stdio-only and proposes tasks without bypassing approval.

## Maintenance

When a change materially alters architecture, commands, safety boundaries, or supported protocols, update this skill alongside the relevant implementation and documentation. Keep secrets and machine-specific credentials out of it. Prefer updating the affected section rather than appending a chronological log.
