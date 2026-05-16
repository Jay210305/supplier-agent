# API Backend

Base URL: `http://localhost:8000`

## Health
**GET /health**

Devuelve 200 cuando Postgres y Ollama estan OK, si no 503.

Respuesta:
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

Respuesta:
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

Respuesta (salida LLM + estimacion):
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

Notas:
- `budget_exceeded` es true si no se pudo estimar el minimo o si supera `max_budget`.

Errores:
- 422: salida LLM invalida
- 503: Ollama no disponible
- 500: error interno
- 429: rate limit excedido

## Orders
**GET /orders/ping**

Respuesta:
```
{"status":"ok","router":"orders"}
```

**POST /orders/generate**

Request (extraccion validada):
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

Respuesta:
```
{
  "purchase_order_id": 12,
  "request_id": "REQ-2026-001",
  "supplier_id": 3,
  "supplier_name": "TechMype Peru SAC",
  "pdf_path": "generated_pos/PO_REQ-2026-001_20260101_120000.pdf",
  "total_amount_pen": 3539.88,
  "justification": "Cumple plazo y presupuesto.",
  "runner_up_supplier_id": 1,
  "scoring_snapshot": [{"id":3,"wlc_score":0.91}]
}
```

Errores:
- 409: request_id duplicado
- 422: no hay proveedores elegibles o justificacion LLM invalida
- 503: Ollama no disponible

## Suppliers
**GET /suppliers/ping**

Respuesta:
```
{"status":"ok","router":"suppliers"}
```
