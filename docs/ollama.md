# Ollama Integration

## Runtime
- Service: ollama (Docker)
- Base URL (inside network): http://ollama:11434
- Base URL (host): http://localhost:11434
- Model tag: llama3.2:3b

## Prompts
- prompts/entity_extraction.txt
- prompts/justification.txt

FastAPI loads prompts from the repo or from `/prompts` (mounted in Docker).

## Request format
FastAPI uses `POST /api/generate` with JSON format:

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

## Retry behavior
- If the response is not valid JSON or fails Pydantic validation, FastAPI retries once with a stricter prompt suffix.
- If the second attempt fails, the API returns an error (422 for /procurement/parse or /orders/generate).

## Output shapes
Entity extraction (validated by Pydantic):
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

Justification output:
```
{
  "recommended_supplier_id": 12,
  "justification": "Meets deadline and budget.",
  "runner_up_supplier_id": 7
}
```
