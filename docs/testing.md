# Pruebas

## Ejecutar tests (dentro de Docker)
```
docker compose exec fastapi pytest
```

## Cobertura
- Tests del router de procurement (extraccion LLM + estimacion)
- Tests del router de orders (respuesta de generacion de PO)
- Tests del cliente Ollama (reintentos y validacion)
- Tests de scoring WLC
- Tests de generacion PDF
