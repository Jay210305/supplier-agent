# Architecture

## Services
| Service | Purpose | Internal Hostname | Internal Port | Host Port |
| --- | --- | --- | --- | --- |
| postgres | Relational database | postgres | 5432 | 5432 |
| ollama | Local LLM runtime | ollama | 11434 | 11434 |
| fastapi | Backend API | fastapi | 8000 | 8000 |
| n8n | Workflow automation | n8n | 5678 | 5678 |
| frontend | React app via nginx | frontend | 80 | 3000 |

All services share the `supplier-net` Docker network. Inter-service calls use service hostnames (not localhost).

## Data flow (current)
1. Client calls `/procurement/parse` with email text.
2. FastAPI calls Ollama to extract structured data, validates it, and estimates a minimum total from catalog data.
3. Client calls `/orders/generate` with the extracted request.
4. FastAPI builds supplier quotes, scores them with WLC, asks Ollama for a justification, and generates a PDF.
5. A procurement log entry is created for the PO generation event.

## Volumes
- postgres_data: Postgres data
- ollama_data: Ollama model cache
- n8n_data: n8n state
- po_pdfs: generated PDF storage
