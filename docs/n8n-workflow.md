# n8n Workflow

## Current workflow file
`n8n/workflows/procurement_flow.json`

## Import
1. Open n8n at http://localhost:5678
2. Import the workflow JSON from the file above

## Current behavior
The workflow contains a single Manual Trigger node with no connections. It is ready for manual execution and can be expanded with HTTP Request nodes targeting FastAPI.

## FastAPI endpoints (inside Docker network)
- http://fastapi:8000/procurement/parse
- http://fastapi:8000/orders/generate

## n8n database
n8n stores state in Postgres using the connection configured in docker-compose.yml.
