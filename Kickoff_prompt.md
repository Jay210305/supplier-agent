# KICKOFF PROMPT — Paste this into Cursor Agent (Cmd/Ctrl+L → Agent mode)

---

Read `AGENTS.md` in full before doing anything else. That is your specification.

This project is empty. Your job is to implement **Phase 1 — Infrastructure** from scratch.
Deliver every file needed to run `docker compose up -d` successfully.

## Step 0 — Fix MCP configuration (do this first, before any file creation)

Open `.cursor/mcp.json`. It contains a placeholder path for the `filesystem` MCP server:
```
"/absolute/path/to/your/project"
```

Replace it with the **actual absolute path of this project** — detect it by running:
```bash
pwd
```
from the project root using your terminal tool, then update `mcp.json` with the real path.

Also confirm the `postgres` connection string matches the credentials in `.env` (section 6 of AGENTS.md):
```
postgresql://mypes_user:changeme@localhost:5432/supplier_agent_db
```
If any value differs, sync it.

Save `mcp.json`, then verify the `filesystem` MCP can list the project root before proceeding.

---

## What to build in this session

1. `docker-compose.yml` — as specified below (NOT the version in AGENTS.md §4 — see corrections).
2. `docker-compose.gpu.yml` — Compose override that enables NVIDIA GPU for Ollama (Linux only).
3. `setup.sh` — OS/GPU detection script; installs NVIDIA Container Toolkit on Linux if needed.
4. `.env` — with all variables from AGENTS.md section 6. Use placeholder values where noted.
5. `.gitignore` — ignore `.env`, `__pycache__`, `*.pyc`, `node_modules`, `dist`, `.DS_Store`, `generated_pos/`.
6. `backend/Dockerfile` — from AGENTS.md section 8.
7. `backend/requirements.txt` — from AGENTS.md section 8.
8. `backend/main.py` — minimal FastAPI app with:
   - `GET /health` → checks Postgres connection and Ollama reachability (`GET http://ollama:11434/api/tags`), returns `{"postgres": "ok"|"error", "ollama": "ok"|"error"}` with HTTP 200 or 503.
   - Router includes for `procurement`, `suppliers`, `orders` (empty routers with a placeholder `GET /ping` each are fine for now).
   - **OLLAMA_MODEL** env var (default `llama3.2:3b`) used in all Ollama API payloads.
9. `backend/db/session.py` — SQLAlchemy async engine reading all connection params from env via pydantic-settings.
10. `backend/alembic.ini` + `backend/alembic/env.py` — configured to point at the project's models package.
11. `frontend/Dockerfile` — from AGENTS.md section 9.
12. `frontend/nginx.conf` — from AGENTS.md section 9.
13. `frontend/package.json` — React 18 + Vite + TypeScript + TailwindCSS.
14. `frontend/src/main.tsx` + `frontend/index.html` — minimal React entry point rendering "Supplier Agent — Sistema de Abastecimiento Inteligente" with a centered placeholder UI.

---

## Corrections to AGENTS.md §4 — apply these, do NOT follow the original

The following conflicts between AGENTS.md and this Kickoff have been resolved.
The Kickoff takes precedence.

### ❌ Remove from Ollama service volumes (AGENTS.md §4 is wrong here):
```yaml
# DELETE these three lines — they reference a now-removed LM Studio approach:
- ${LM_STUDIO_MODELS_PATH}:/root/.ollama/gguf-import:ro
- ./ollama/Modelfile:/tmp/Modelfile:ro
- ./ollama/entrypoint.sh:/entrypoint.sh:ro
```

### ✅ Ollama service volumes must be ONLY:
```yaml
volumes:
  - ollama_data:/root/.ollama
```

### ✅ Ollama entrypoint — inline native pull (no shell script file):
```yaml
entrypoint: >
  /bin/sh -c "
    ollama serve &
    OLLAMA_PID=$$!;
    until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do sleep 2; done;
    ollama pull llama3.2:3b || true;
    wait $$OLLAMA_PID
  "
```

### ✅ Model name is `llama3.2:3b` everywhere (colon, not dash):
All Ollama API payloads, the `OLLAMA_MODEL` env var, test commands, and
`ollama list` expected output must use `llama3.2:3b`.

### ✅ GPU section stays commented in docker-compose.yml:
The GPU block from AGENTS.md §4 is moved to `docker-compose.gpu.yml`.
Users run `setup.sh` first, then:
```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

### ✅ No `ollama/` directory:
Do not create `ollama/Modelfile`, `ollama/entrypoint.sh`, or any file under `ollama/`.

### ✅ `LM_STUDIO_MODELS_PATH` is NOT required:
Keep it in `.env` as a comment for documentation only.

---

## Constraints

- **No `ollama/` directory** — the model is pulled natively via the inline entrypoint.
- All inter-service URLs inside containers must use Docker service names (`http://ollama:11434`, `http://postgres:5432`), never `localhost`.
- `backend/main.py` must fail loudly at startup if `POSTGRES_HOST` is not set (use pydantic-settings Settings class).
- `OLLAMA_MODEL` env var (default `llama3.2:3b`) must be read by all Ollama API calls — never hardcode the model string.
- Do not create any database tables yet — that is Phase 2.

---

## After creating all files

1. Use the `filesystem` MCP to verify the project tree matches AGENTS.md section 7 (minus the `ollama/` folder).
2. Use the `fetch` MCP to verify Ollama is reachable at `http://localhost:11434/api/tags` (only if Docker is already running).
3. Save a `memory` entry:
   ```
   Phase 1 complete: Docker infra, FastAPI skeleton, frontend scaffold.
   Postgres credentials: mypes_user/changeme.
   Ollama model: llama3.2:3b (native pull, no LM Studio).
   GPU: setup.sh + docker-compose.gpu.yml for Linux NVIDIA.
   Next: Phase 2 — SQLAlchemy models, Alembic migrations, seed 10 suppliers.
   ```
4. Print a clear checklist of what the user must do manually before running the stack:

   **Pre-flight checklist:**
   - [ ] Docker Desktop (macOS/Windows) or Docker Engine (Linux) is running.
   - [ ] **Linux with NVIDIA GPU:** run `bash setup.sh` first; if GPU-ready use the `-f docker-compose.gpu.yml` flag.
   - [ ] **macOS Apple Silicon:** no extra steps — Metal is auto-detected by the Ollama image.
   - [ ] First `docker compose up -d` downloads `llama3.2:3b` (~2 GB). This only happens once (model is cached in the `ollama_data` volume).
   - [ ] Fill in real IMAP credentials in `.env` before enabling the n8n email trigger.
   - [ ] Change `N8N_ENCRYPTION_KEY` in `docker-compose.yml` to a random 32-character string before production use.
