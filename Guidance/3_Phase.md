# Phase 3 — Ollama Integration & Extraction

## Objective
Implement the Ollama integration layer and entity extraction endpoint to parse procurement emails using the local Llama 3.2 3B model. This phase creates the backend service that communicates with Ollama, implements the entity extraction route, and validates the LLM output before database persistence.

## Tasks

### 1. Create Ollama Client Service

Create `backend/services/ollama_client.py` with:

- A wrapper for Ollama REST API calls
- Methods for entity extraction and supplier justification
- Retry logic for malformed JSON responses
- Integration with Pydantic validation schemas
- Error handling and logging

Key requirements:
- Use `OLLAMA_BASE_URL` and `OLLAMA_MODEL` from environment variables
- Implement the entity extraction call format as specified in AGENTS.md §12
- Add retry mechanism: on malformed JSON, retry once with stricter prompt
- After 2 failures, raise exception for handling in route layer
- Validate output against `ProcurementRequest` schema before returning

### 2. Implement POST /procurement/parse Route

Update `backend/routers/procurement.py` to:

- Accept email body in request payload
- Call Ollama client for entity extraction
- Validate response with Pydantic schema
- Return structured JSON or appropriate error codes
- Implement rate limiting (10 req/min using slowapi)
- Handle LLM failures gracefully (HTTP 422 for validation errors, 503 for Ollama unavailability)

Route specification:
```
POST /procurement/parse
Content-Type: application/json
{
  "email_body": "Necesito 10 laptops antes del lunes, presupuesto 30000 soles."
}
```

Expected successful response:
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

### 3. Create Entity Extraction Prompt

Create `prompts/entity_extraction.txt` with:

- System prompt instructing the LLM to extract procurement entities
- Clear specification of expected JSON structure
- Instructions to return ONLY valid JSON
- Examples of valid outputs
- Constraints on field types and formats

Based on AGENTS.md §12, the prompt should guide the model to extract:
- request_id (string)
- items (list of objects with product and quantity)
- constraints (max_budget, currency, delivery_before)
- priority (low/medium/high)

### 4. Add Rate Limiting

Configure slowapi on the `/procurement/parse` endpoint:
- Limit: 10 requests per minute
- Key function based on client IP
- Custom error response for rate limit exceeded

### 5. Health Check Integration

Ensure the `/health` endpoint in `backend/main.py` includes Ollama status checking:
- Verify Ollama service is reachable
- Confirm model availability
- Return appropriate health status codes

### 6. Unit Tests

Create tests for:
- Ollama client success/failure scenarios
- Route validation and error handling
- Rate limiting functionality
- Prompt template correctness

## Deliverables

By the end of this phase, the project must include:

- `backend/services/ollama_client.py` - Ollama service wrapper
- Updated `backend/routers/procurement.py` with extraction endpoint
- `prompts/entity_extraction.txt` - LLM prompt for entity extraction
- Rate limiting configuration on procurement routes
- Updated health check with Ollama verification
- Unit tests for new functionality

## Technical Expectations

### Code Quality
- Follow existing code patterns in the backend
- Proper error handling and logging
- Type hints throughout
- Separation of concerns (service layer vs route layer)
- Environment variable configuration

### Integration Points
- Uses SQLAlchemy models from Phase 2 (indirectly through validation schemas)
- Depends on Alembic migrations being applied
- Works with seeded supplier data for future phases
- Prepares for scoring algorithm implementation (Phase 4)

### Ollama Specifics
- Internal URL: `http://ollama:11434` (container-to-container)
- External URL: `http://localhost:11434` (for testing/health checks)
- Model: `llama3.2-3b` (must match environment variable)
- Format: JSON mode enabled for structured output
- Temperature: 0.1 for consistent extraction
- Context length: 4096 tokens

### Validation Requirements
- All LLM output must pass through Pydantic validation
- Never trust raw LLM output for database operations
- Defensive programming against malformed responses
- Clear error messages for debugging

## Success Criteria

1. `docker compose up -d` starts all services without errors
2. `GET http://localhost:8000/health` returns 200 with Ollama status: ok
3. `POST http://localhost:8000/procurement/parse` with sample email returns valid JSON
4. Invalid email responses trigger appropriate error handling
5. Rate limiting prevents abuse (10 req/min)
6. Ollama health check fails appropriately when service is down
7. Unit tests pass for all new functionality