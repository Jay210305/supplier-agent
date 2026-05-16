# Backend API

Base URL: `http://localhost:8000`

## Health
**GET /health**

Returns 200 when Postgres and Ollama are OK, otherwise 503.

Response body:
```
{
  "postgres": "ok" | "error",
  "ollama": "ok" | "degraded" | "error",
  "ollama_model": "llama3.2:3b",
  "ollama_model_ready": true | false
}
```

## Procurement
**GET /procurement/ping**

Response:
```
{"status":"ok","router":"procurement"}
```

**POST /procurement/parse** (rate limit: 10/min)

Request:
```
{
  "email_body": "Necesito 10 laptops antes del lunes, presupuesto 30000 soles."
}
```

Response (LLM output + budget estimate):
```
{
  "request_id": "REQ-2026-001",
  "items": [{"product":"Laptop","quantity":10}],
  "constraints": {
    "max_budget": 30000.0,
    "currency": "PEN",
    "delivery_before": "2026-05-19"
  },
  "priority": "high",
  "budget_exceeded": false,
  "estimated_minimum_total": 25000.0
}
```

Errors:
- 422: invalid LLM output
- 503: Ollama unavailable
- 500: internal error
- 429: rate limit exceeded

## Orders
**GET /orders/ping**

Response:
```
{"status":"ok","router":"orders"}
```

**POST /orders/generate**

Request (validated extraction):
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

Response:
```
{
  "purchase_order_id": 12,
  "request_id": "REQ-2026-001",
  "supplier_id": 3,
  "supplier_name": "TechMype Peru SAC",
  "pdf_path": "generated_pos/PO_REQ-2026-001_20260101_120000.pdf",
  "total_amount_pen": 3539.88,
  "justification": "Meets deadline and budget.",
  "runner_up_supplier_id": 1,
  "scoring_snapshot": [{"id":3,"wlc_score":0.91}]
}
```

Errors:
- 409: duplicate request_id
- 422: no eligible suppliers or invalid LLM justification
- 503: Ollama unavailable

## Suppliers
**GET /suppliers/ping**

Response:
```
{"status":"ok","router":"suppliers"}
```
