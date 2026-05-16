# Arquitectura

## Servicios
| Servicio | Proposito | Hostname interno | Puerto interno | Puerto host |
| --- | --- | --- | --- | --- |
| postgres | Base de datos relacional | postgres | 5432 | 5432 |
| ollama | Runtime LLM local | ollama | 11434 | 11434 |
| fastapi | API backend | fastapi | 8000 | 8000 |
| n8n | Automatizacion de workflows | n8n | 5678 | 5678 |
| frontend | React servido por nginx | frontend | 80 | 3000 |

Todos los servicios comparten la red Docker `supplier-net`. Las llamadas entre servicios usan hostnames de servicio (no localhost).

## Flujo actual
1. El cliente llama a `/procurement/parse` con el texto del correo.
2. FastAPI llama a Ollama para extraer datos estructurados, valida y estima un total minimo desde el catalogo.
3. El cliente llama a `/orders/generate` con la solicitud extraida.
4. FastAPI arma cotizaciones, aplica WLC, pide justificacion a Ollama y genera el PDF.
5. Se registra un log de procurement para la generacion de la orden.

## Volumenes
- postgres_data: datos de Postgres
- ollama_data: cache de modelos Ollama
- n8n_data: estado de n8n
- po_pdfs: almacenamiento de PDFs
