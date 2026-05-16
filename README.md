# Supplier Agent

Supplier Agent es un asistente de compras para MYPES. Todo corre en Docker y usa un LLM local (Ollama) para extraer solicitudes, evaluar proveedores y generar ordenes de compra (PDF).

## Inicio rapido
1. Asegura que Docker Desktop/Engine este en ejecucion.
2. Levanta la pila:

```
docker compose up -d
```

3. Verifica salud:

```
curl http://localhost:8000/health
```

GPU (solo Linux): ejecuta `./setup.sh`, luego:

```
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

## Documentacion
- [docs/quickstart.md](docs/quickstart.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/backend-api.md](docs/backend-api.md)
- [docs/data-model.md](docs/data-model.md)
- [docs/ollama.md](docs/ollama.md)
- [docs/scoring.md](docs/scoring.md)
- [docs/pdf-generation.md](docs/pdf-generation.md)
- [docs/n8n-workflow.md](docs/n8n-workflow.md)
- [docs/frontend.md](docs/frontend.md)
- [docs/testing.md](docs/testing.md)
