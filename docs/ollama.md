# Integracion con Ollama

## Runtime
- Service: ollama (Docker)
- Base URL (red interna): http://ollama:11434
- Base URL (host): http://localhost:11434
- Model tag: llama3.2:3b

## Prompts
- prompts/entity_extraction.txt
- prompts/justification.txt

FastAPI carga prompts desde el repo o desde `/prompts` (montado en Docker).

## Request format
FastAPI usa `POST /api/generate` con JSON:

```
{
  "model": "llama3.2:3b",
  "prompt": "<prompt text>\n\nEMAIL:\n...",
  "stream": false,
  "format": "json",
  "options": {
    "temperature": 0.1,
    "num_ctx": 4096
  }
}
```

## Reintento
- Si la respuesta no es JSON valido o falla validacion Pydantic, FastAPI reintenta una vez con un sufijo mas estricto.
- Si el segundo intento falla, el API devuelve error (422 en /procurement/parse o /orders/generate).

## Salidas esperadas
Extraccion de entidades (validada por Pydantic):
```
{
  "request_id": "REQ-2026-001",
  "items": [{"product":"Laptop","quantity":10}],
  "constraints": {
    "max_budget": 30000.0,
    "currency": "PEN",
    "delivery_before": "2026-05-19"
  },
  "priority": "high"
}
```

Salida de justificacion:
```
{
  "recommended_supplier_id": 12,
  "justification": "Cumple plazo y presupuesto.",
  "runner_up_supplier_id": 7
}
```
