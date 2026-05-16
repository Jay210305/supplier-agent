# Testing

## Run tests (inside Docker)
```
docker compose exec fastapi pytest
```

## Coverage
- Procurement router tests (LLM extraction + budget estimate)
- Orders router tests (PO generation response)
- Ollama client tests (retry and validation logic)
- WLC scoring tests
- PDF generation tests
