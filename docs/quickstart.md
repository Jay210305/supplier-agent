# Inicio rapido

## Requisitos
- Docker Desktop o Docker Engine

## Levantar la pila
```
docker compose up -d
```

## Chequeo de salud
```
curl http://localhost:8000/health
```

Una respuesta sana devuelve HTTP 200 con estado para Postgres y Ollama.

## Migraciones
El contenedor `fastapi` ejecuta `alembic upgrade head` al iniciar. Si necesitas correrlo manualmente:

```
docker compose exec fastapi alembic upgrade head
```

## Datos de ejemplo
Carga proveedores y productos demo. Esto borra proveedores, productos y logs existentes.

```
docker compose exec fastapi python db/seed.py
```

## Variables .env (opcional)
FastAPI carga un archivo `.env` si existe. Docker Compose ya define defaults, pero puedes sobrescribirlos:

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

## Puertos (host)
- 8000: API FastAPI
- 11434: Ollama
- 5678: n8n
- 3000: Frontend (nginx)
- 5432: Postgres

## GPU (solo Linux)
Ejecuta el script de apoyo para NVIDIA Container Toolkit:

```
bash setup.sh
```

Luego levanta con override de GPU:

```
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```
