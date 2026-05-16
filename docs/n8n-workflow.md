# Workflow n8n

## Archivo actual
- `n8n/workflows/procurement_flow.json`

## Importacion
1. Levanta la pila: `docker compose up -d`
2. Abre http://localhost:5678
3. **Workflows -> Import from file** -> `procurement_flow.json`

## Flujo actual
El workflow contiene un solo nodo **Manual Trigger** sin conexiones. Sirve como base para ejecuciones manuales.
