# AGENTS.md — Intelligent Supplier Selection Agent for MYPES
> This file is the single source of truth for the Cursor AI agent working on this project.
> Read it fully before writing any code, creating any file, or making any architectural decision.

---

## 1. Project Overview

An autonomous **e-procurement assistant** for Peruvian Small and Medium Enterprises (MYPES).
It ingests procurement emails, uses a **local LLM (Ollama)** to extract structured entities,
scores suppliers via a weighted algorithm, and auto-generates PDF Purchase Orders (POs) with
a human-in-the-loop approval step.

**Core principles:**
- **100% local inference.** No cloud LLM calls. Data sovereignty is non-negotiable.
- **Everything runs in Docker.** `docker compose up -d` is the only command needed to start the full system.
- The developer's machine runs **only** Cursor and Docker Desktop. No local Python, Node, or Ollama installs required.

---

## 2. Tech Stack & Official Docs

| Layer | Technology | Official Docs |
|---|---|---|
| Workflow Automation | **n8n** (self-hosted, Docker) | https://docs.n8n.io |
| Local LLM Runtime | **Ollama** (Docker, GPU optional) | https://github.com/ollama/ollama/blob/main/docs/api.md |
| LLM Model | **llama3.2:3b** (Ollama pull, cached in `ollama_data`) | https://ollama.com/library/llama3.2 |
| Database | **PostgreSQL 16** (Docker) | https://www.postgresql.org/docs/16/index.html |
| Backend API | **FastAPI** (Python 3.12, Docker) | https://fastapi.tiangolo.com |
| ORM | **SQLAlchemy 2.0** | https://docs.sqlalchemy.org/en/20/ |
| DB Migrations | **Alembic** | https://alembic.sqlalchemy.org/en/latest/ |
| PDF Generation | **WeasyPrint** | https://doc.courtbouillon.org/weasyprint/stable/ |
| Containerization | **Docker Compose v2** | https://docs.docker.com/compose/ |
| Email Protocol | IMAP / Gmail API | https://developers.google.com/gmail/api/guides |
| Validation | **Pydantic v2** | https://docs.pydantic.dev/latest/ |
| Frontend Dashboard | **React + Vite** (Docker, nginx) | https://vitejs.dev/guide/ |

---

## 3. Docker Architecture

All services communicate over a shared Docker network called `supplier-net`.
**Never use `localhost` in inter-service calls** — use the service name as the hostname.

```
┌─────────────────────────────────────────────────────┐
│                   supplier-net (Docker bridge)       │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ postgres │  │  ollama  │  │     fastapi       │  │
│  │  :5432   │  │  :11434  │  │      :8000        │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
│                                                      │
│  ┌──────────┐  ┌──────────────────────────────────┐ │
│  │   n8n    │  │           frontend               │ │
│  │  :5678   │  │    (nginx, :3000)                │ │
│  └──────────┘  └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘

Host-exposed ports (for developer access):
  localhost:5432  → postgres
  localhost:11434 → ollama
  localhost:8000  → fastapi
  localhost:5678  → n8n UI
  localhost:3000  → frontend
```

### Service hostnames (use inside containers)
| Service | Internal hostname | Port |
|---|---|---|
| PostgreSQL | `postgres` | `5432` |
| Ollama | `ollama` | `11434` |
| FastAPI | `fastapi` | `8000` |
| n8n | `n8n` | `5678` |
| Frontend | `frontend` | `80` |

---

## 4. docker-compose.yml Specification

Create this file at the project root exactly as specified.

```yaml
# docker-compose.yml
name: supplier-agent

services:

  postgres:
    image: postgres:16-alpine
    container_name: postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: supplier_agent_db
      POSTGRES_USER: mypes_user
      POSTGRES_PASSWORD: changeme
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    networks:
      - supplier-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mypes_user -d supplier_agent_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: unless-stopped
    volumes:
      - ollama_data:/root/.ollama   # persists pulled model weights
    ports:
      - "11434:11434"
    networks:
      - supplier-net
    # GPU (Linux): run ./setup.sh, then docker compose -f docker-compose.gpu.yml up -d
    entrypoint:
      - /bin/sh
      - -c
      - |
          ollama serve &
          OLLAMA_PID=$$!
          until ollama list >/dev/null 2>&1; do sleep 2; done
          ollama pull llama3.2:3b || true
          wait "$$OLLAMA_PID"
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 30s
      timeout: 10s
      retries: 10
      start_period: 120s

  fastapi:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: fastapi
    restart: unless-stopped
    env_file: .env
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      OLLAMA_BASE_URL: http://ollama:11434
    volumes:
      - ./backend:/app
      - po_pdfs:/app/generated_pos
    ports:
      - "8000:8000"
    networks:
      - supplier-net
    depends_on:
      postgres:
        condition: service_healthy
      ollama:
        condition: service_healthy
    command: >
      sh -c "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped
    environment:
      N8N_HOST: n8n
      N8N_PORT: 5678
      N8N_PROTOCOL: http
      WEBHOOK_URL: http://localhost:5678
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: postgres
      DB_POSTGRESDB_PORT: 5432
      DB_POSTGRESDB_DATABASE: supplier_agent_db
      DB_POSTGRESDB_USER: mypes_user
      DB_POSTGRESDB_PASSWORD: changeme
      N8N_ENCRYPTION_KEY: change_this_to_a_random_32char_string
    volumes:
      - n8n_data:/home/node/.n8n
      - ./n8n/workflows:/home/node/.n8n/workflows
    ports:
      - "5678:5678"
    networks:
      - supplier-net
    depends_on:
      postgres:
        condition: service_healthy

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: frontend
    restart: unless-stopped
    ports:
      - "3000:80"
    networks:
      - supplier-net
    depends_on:
      - fastapi

volumes:
  postgres_data:
  ollama_data:
  n8n_data:
  po_pdfs:

networks:
  supplier-net:
    driver: bridge
```

---

## 5. Ollama Bootstrap (native pull)

On first start the `ollama` container runs `ollama pull llama3.2:3b` (~2 GB, cached in
volume `ollama_data`). No LM Studio mount, no `ollama/Modelfile`, no host GGUF path.

- Model tag in `.env` / Compose: `llama3.2:3b` (must match the pulled tag).
- GPU (Linux): `bash setup.sh` then `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d`.
- macOS Apple Silicon: Metal is automatic; use `docker compose up -d` only.

---

## 6. Environment Variables (`.env`)

Create `.env` at the project root. **Never commit this file.**
Add `.env` to `.gitignore` immediately.

```dotenv
# ── Database ──────────────────────────────────────
POSTGRES_DB=supplier_agent_db
POSTGRES_USER=mypes_user
POSTGRES_PASSWORD=changeme

# ── Ollama ────────────────────────────────────────
# Internal URL (used by FastAPI container → ollama container)
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:3b

# PDF output inside FastAPI container (volume po_pdfs → /app/generated_pos)
GENERATED_POS_DIR=/app/generated_pos

# ── Email (IMAP) ──────────────────────────────────
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=compras@mype.com.pe
IMAP_PASSWORD=your_gmail_app_password

# ── FastAPI ───────────────────────────────────────
SECRET_KEY=generate_a_long_random_string_here
ENV=development
API_PORT=8000
```

---

## 7. Project Structure (Target)

```
supplier-agent/
├── .cursor/
│   └── mcp.json
├── .env                           # secrets — never commit
├── .gitignore
├── docker-compose.yml
├── AGENTS.md                      # this file
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                    # FastAPI app entry point
│   ├── routers/
│   │   ├── procurement.py         # POST /procurement/parse
│   │   ├── suppliers.py           # CRUD for supplier records
│   │   └── orders.py              # PO generation & approval
│   ├── services/
│   │   ├── ollama_client.py       # Ollama REST wrapper
│   │   ├── scoring.py             # WLC scoring algorithm
│   │   └── pdf_generator.py       # WeasyPrint PO generation
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── base.py
│   │   ├── supplier.py
│   │   ├── product.py
│   │   ├── purchase_order.py
│   │   └── procurement_log.py
│   ├── schemas/                   # Pydantic v2 schemas
│   │   ├── procurement_request.py
│   │   └── purchase_order.py
│   ├── db/
│   │   ├── session.py
│   │   └── seed.py                # 10 dummy suppliers for dev
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   └── tests/
│       └── test_scoring.py
│
├── prompts/
│   ├── entity_extraction.txt      # system prompt for extraction
│   └── justification.txt          # prompt for LLM recommendation
│
├── n8n/
│   └── workflows/
│       └── procurement_flow.json
│
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    └── src/
        ├── main.tsx
        └── pages/
            ├── Dashboard.tsx
            └── OrderDetail.tsx
```

---

## 8. Backend Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

# WeasyPrint system dependencies
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
    libcairo2 libgdk-pixbuf2.0-0 libffi-dev \
    curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
```

### `backend/requirements.txt`
```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.36
alembic==1.13.3
psycopg2-binary==2.9.9
pydantic[email]==2.9.2
pydantic-settings==2.5.2
httpx==0.27.2
weasyprint==62.3
slowapi==0.1.9
python-multipart==0.0.12
pytest==8.3.3
pytest-asyncio==0.24.0
```

---

## 9. Frontend Dockerfile

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### `frontend/nginx.conf`
```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # React SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API calls to FastAPI
    location /api/ {
        proxy_pass http://fastapi:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 10. Database Schema (3NF)

Always verify current schema via the `postgres` MCP before writing migrations.

```sql
CREATE TABLE suppliers (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(255) NOT NULL,
    ruc           VARCHAR(11) UNIQUE NOT NULL,  -- Peruvian tax ID, always 11 digits
    contact_email VARCHAR(255),
    phone         VARCHAR(20),
    rating        NUMERIC(3,2) DEFAULT 5.0,     -- 0.00–10.00
    category      VARCHAR(100),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE products (
    id             SERIAL PRIMARY KEY,
    supplier_id    INT REFERENCES suppliers(id) ON DELETE CASCADE,
    name           VARCHAR(255) NOT NULL,
    unit_price     NUMERIC(10,2) NOT NULL,
    lead_time_days INT NOT NULL,
    stock          INT DEFAULT 0,
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE purchase_orders (
    id          SERIAL PRIMARY KEY,
    request_id  VARCHAR(50) UNIQUE NOT NULL,     -- e.g. REQ-2026-001
    supplier_id INT REFERENCES suppliers(id),
    total_amount NUMERIC(10,2),
    currency    VARCHAR(3) DEFAULT 'PEN',
    status      VARCHAR(20) DEFAULT 'Pending',  -- Pending|Approved|Sent|NeedsReview
    payload     JSONB,
    pdf_path    VARCHAR(512),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    approved_at TIMESTAMPTZ
);

CREATE TABLE procurement_logs (
    id         SERIAL PRIMARY KEY,
    event_type VARCHAR(50),  -- EMAIL_RECEIVED|LLM_PARSED|PO_GENERATED|APPROVED|LLM_FAILED
    payload    JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 11. Supplier Scoring Algorithm

**Weighted Linear Combination (WLC):**

```
Score = (0.4 × Price_Score) + (0.4 × Delivery_Score) + (0.2 × Reliability_Score)

Price_Score       = 1 - (supplier_price / max_price_in_pool)
Delivery_Score    = 1 - (lead_time_days / max_lead_time_in_pool)
Reliability_Score = supplier.rating / 10.0
```

After WLC, send the **top 3 suppliers** to Ollama with `prompts/justification.txt`.
The LLM must return:

```json
{
  "recommended_supplier_id": 12,
  "justification": "OfficeSupply meets the Monday deadline (1-day lead time)...",
  "runner_up_supplier_id": 7
}
```

---

## 12. Ollama Integration

**Internal URL (from FastAPI container):** `http://ollama:11434`
**External URL (from host/MCP fetch):** `http://localhost:11434`

**Entity Extraction Call:**
```python
POST /api/generate
{
  "model": "llama3.2-3b",
  "prompt": "<contents of prompts/entity_extraction.txt>\n\nEMAIL:\n{email_body}",
  "stream": false,
  "format": "json"
}
```

**Expected output (Pydantic-validated before any DB write):**
```json
{
  "request_id": "REQ-2026-001",
  "items": [{"product": "Laptop", "quantity": 10}],
  "constraints": {
    "max_budget": 30000.00,
    "currency": "PEN",
    "delivery_before": "2026-05-19"
  },
  "priority": "high"
}
```

**⚠️ Retry logic:** On malformed JSON, retry once with a stricter prompt + concrete example.
After 2 failures → set status to `NeedsReview`, log `LLM_FAILED`, send alert.

Docs: https://github.com/ollama/ollama/blob/main/docs/api.md

---

## 13. n8n Workflow (inside Docker)

n8n runs at `http://localhost:5678`. It connects to FastAPI via `http://fastapi:8000`.

> Import workflow: n8n UI → Settings → Workflows → Import from file
> n8n API docs: https://docs.n8n.io/api/

Nodes in order:
1. **IMAP Trigger** → polls `compras@mype.com.pe` every 1 min
2. **HTML-to-Text** → strip HTML from email body
3. **HTTP Request** → `POST http://fastapi:8000/procurement/parse`
4. **IF Node** → `response.budget_exceeded == true`
   - `true` → Send budget alert email (include: items, estimated cost, budget limit)
   - `false` → continue
5. **HTTP Request** → `POST http://fastapi:8000/orders/generate`
6. **Webhook** → wait for manager approval (one-click link in email/Slack)
7. **HTTP Request** → `PATCH http://fastapi:8000/orders/{id}/approve`
8. **Send Email + Slack** → dispatch approved PO PDF

---

## 14. MCP Servers — How to Use Them

| Server | When to use | Key note |
|---|---|---|
| `postgres` | Inspect schema, debug data, verify migrations | Never DROP/TRUNCATE without confirmation |
| `filesystem` | Read existing files before writing | Always check before overwriting |
| `fetch` | Test Ollama (`http://localhost:11434`), FastAPI (`http://localhost:8000`), n8n (`http://localhost:5678`) | Use host ports, not internal |
| `memory` | Save progress across long task chains | Write an entry at end of each phase |
| `sequential-thinking` | Any task with 3+ interdependent steps | Use before designing new services |

Docs:
- postgres: https://github.com/modelcontextprotocol/servers/tree/main/src/postgres
- filesystem: https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem
- fetch: https://github.com/modelcontextprotocol/servers/tree/main/src/fetch
- memory: https://github.com/modelcontextprotocol/servers/tree/main/src/memory
- sequential-thinking: https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking

---

## 15. Key Constraints & Non-Negotiables

- **No cloud LLM** — Ollama only. Never import `openai`, `anthropic`, or `google.generativeai`.
- **No local installs** — all services run in Docker. Never instruct the user to `pip install` or `npm install` on their machine.
- **Inter-service calls use Docker hostnames** — `http://ollama:11434`, `http://postgres:5432`, `http://fastapi:8000`. Never `localhost` inside a container.
- **PEN is the default currency** — `NUMERIC(10,2)` for all monetary values.
- **RUC = 11 digits** — validate with `^\d{11}$`.
- **No PO reaches `Sent` without an approval log entry.**
- **All secrets in `.env`** — never hardcode.
- **Alembic for all schema changes** — never raw DDL in app code.

---

## 16. Improvements Beyond the Original Proposal

| # | What | Why |
|---|---|---|
| 1 | `procurement_logs` table | Original had no audit trail; needed for debugging and compliance |
| 2 | Pydantic validation gate | LLM output went straight to DB; must be validated first |
| 3 | Ollama Docker healthcheck | FastAPI must not start before Ollama is ready |
| 4 | LLM retry + `NeedsReview` fallback | Silent failures would corrupt data |
| 5 | `/health` endpoint | Required for Docker orchestration and n8n startup |
| 6 | Rate limiting on `/procurement/parse` (`slowapi`, 10 req/min) | Ollama is slow; thundering herd on n8n reconnect is a real risk |
| 7 | WhatsApp stub `POST /procurement/whatsapp` → 501 | Future-proofs Twilio integration at zero cost now |
| 8 | n8n stores state in Postgres | Original used SQLite (default); Postgres is already running, more robust |
| 9 | Frontend served via nginx with API proxy | Avoids CORS issues between React and FastAPI |
| 10 | `db/seed.py` with 10 dummy suppliers | Needed to test scoring from day one |

---

## 17. Testing Checklist

Before marking any phase complete:

- [ ] `docker compose up -d` starts all 5 services with no errors
- [ ] `docker compose ps` shows all containers as `healthy`
- [ ] `ollama list` (inside container) shows `llama3.2-3b`
- [ ] `GET http://localhost:8000/health` returns `200` with DB + Ollama status
- [ ] Alembic migrations apply cleanly on a fresh volume (`docker compose down -v && docker compose up -d`)
- [ ] Entity extraction returns valid JSON for the demo email (10 Laptops, 30k PEN, Monday)
- [ ] Scoring selects the supplier with 1-day delivery when deadline is the binding constraint
- [ ] Generated PDF contains: request_id, supplier name/RUC, item table, total in PEN, date
- [ ] Approval webhook flips status to `Approved` and inserts a log row
- [ ] Budget-exceeded flow sends alert email and does NOT generate a PO
- [ ] `GET http://localhost:8000/health` returns `503` when Ollama container is stopped

---

## 18. Quick Reference Commands

```bash
# ── Start everything ──────────────────────────────
docker compose up -d

# ── Check all containers are healthy ─────────────
docker compose ps

# ── Tail logs ─────────────────────────────────────
docker compose logs -f fastapi
docker compose logs -f ollama

# ── Verify model is registered ────────────────────
docker exec ollama ollama list

# ── Re-pull model manually (if needed) ────────────
docker exec ollama ollama pull llama3.2:3b

# ── Test Ollama from host ──────────────────────────
curl http://localhost:11434/api/tags

# ── Test FastAPI health ───────────────────────────
curl http://localhost:8000/health

# ── Test entity extraction ────────────────────────
curl -X POST http://localhost:8000/procurement/parse \
  -H "Content-Type: application/json" \
  -d '{"email_body": "Necesito 10 laptops antes del lunes, presupuesto 30000 soles."}'

# ── Reset all data (wipe volumes) ─────────────────
docker compose down -v

# ── Seed local suppliers (hard-coded demo data) ───
docker exec fastapi python -m db.seed

# ── Seed external catalog sources (MercadoLibre, Amazon, eBay, ...) ─
docker exec fastapi python -m db.seed_catalog_sources

# ── List external sources ─────────────────────────
curl http://localhost:8000/catalog-sources

# ── Test an external source end-to-end ────────────
curl -X POST http://localhost:8000/catalog-sources/1/test \
 -H "Content-Type: application/json" \
 -d '{"query": "laptop", "limit": 5}'

# ── Open n8n UI ───────────────────────────────────
open http://localhost:5678

# ── Open frontend ─────────────────────────────────
open http://localhost:3000
```

---

## 19. External Catalog Sources (Phase 4 extension)

Beyond the hard-coded local supplier pool seeded by `backend/db/seed.py`, the
agent can fan out to a **configurable pool of external providers** at procure
time. Sources are user-managed via the frontend (`/sources`) or the REST API.

### Architecture
- `catalog_sources` table: one row per external provider (website or email),
  with `adapter_key`, `endpoint`, `is_enabled`, `auth`, `config`, rate-limit
  and timeout.
- `catalog_search_cache` table: short-TTL JSONB cache (default 6h) keyed by
  `(source_id, sha256(query))`.
- `services/catalog_adapters/`: one adapter per integration. Built-ins:
  - `mercadolibre` — public search API (default-enabled, no auth).
  - `amazon` — PA-API 5 (requires AWS SigV4 credentials).
  - `ebay` — Browse API (requires OAuth bearer token).
  - `alibaba` — Open Platform (requires app_key/app_secret).
  - `generic_http` — HTML scraping driven by CSS selectors in `config`.
  - `email_rfq` — outbound RFQ (async; never blocks scoring).
- `services/catalog_search.py`: per-source semaphore + per-source httpx timeout
  + global timeout wrapping `asyncio.gather`. Each adapter coroutine uses its
  own `AsyncSession` for concurrency safety.
- `services/candidate_aggregator.py`: merges local DB suppliers and external
  results into a single `list[SupplierQuote]` consumed by the existing WLC
  scoring pipeline. External results use a **virtual** `supplier_id = -<source_id>`
  so they never collide with real supplier IDs.
- External hits are **never** persisted to `products` / `suppliers`. They live
  only in the JSONB cache + in-memory `SupplierQuote` objects.

### Endpoints
- `GET    /catalog-sources` — list all sources
- `GET    /catalog-sources/adapters` — list available adapter keys + metadata
- `POST   /catalog-sources` — create
- `GET    /catalog-sources/{id}` — read
- `PATCH  /catalog-sources/{id}` — update / toggle `is_enabled`
- `DELETE /catalog-sources/{id}` — delete
- `POST   /catalog-sources/{id}/test` — run adapter once, do NOT touch cache
- `POST   /catalog-sources/search` — cached fan-out for a single query

### `/procurement/parse` integration
The body accepts two new fields (both optional):
- `include_external: bool = true` — toggle the external fan-out per request.
- `source_ids: list[int] | None` — restrict to a subset of source IDs.

The response gains `sources_used: list[str]` and `external_candidate_count: int`.
`budget_exceeded` and `estimated_minimum_total` now take the minimum of local
and external lower-bound estimates.