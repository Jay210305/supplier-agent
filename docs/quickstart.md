# Quickstart

## Prerequisites
- Docker Desktop or Docker Engine

## Run the stack
```
docker compose up -d
```

## Health check
```
curl http://localhost:8000/health
```

A healthy response returns HTTP 200 with status for Postgres and Ollama.

## Optional .env overrides
FastAPI loads a `.env` file if present. Docker Compose already provides default values, but you can override them with:

```
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=supplier_agent_db
POSTGRES_USER=mypes_user
POSTGRES_PASSWORD=changeme

OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:3b

GENERATED_POS_DIR=/app/generated_pos
```

## Ports (host)
- 8000: FastAPI API
- 11434: Ollama
- 5678: n8n
- 3000: Frontend (nginx)
- 5432: Postgres

## GPU setup (Linux only)
Run the helper script to configure NVIDIA Container Toolkit:

```
bash setup.sh
```

Then start with GPU override:

```
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```
