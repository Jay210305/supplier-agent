# Supplier Agent

Supplier Agent is an intelligent e-procurement assistant for MYPES. It runs fully in Docker and uses a local LLM (Ollama) to parse procurement requests, score suppliers, and generate purchase orders (PDF).

## Quick start
1. Ensure Docker Desktop/Engine is running.
2. Start the stack:

```
docker compose up -d
```

3. Check health:

```
curl http://localhost:8000/health
```

GPU (Linux only): run `./setup.sh`, then:

```
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

## Documentation
- docs/quickstart.md
- docs/architecture.md
- docs/backend-api.md
- docs/data-model.md
- docs/ollama.md
- docs/scoring.md
- docs/pdf-generation.md
- docs/n8n-workflow.md
- docs/frontend.md
- docs/testing.md
