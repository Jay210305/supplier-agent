# Frontend

## Stack
- React 18 + Vite
- Servido por nginx en Docker

## UI actual
La UI es un placeholder que confirma que la API esta disponible en `/api` via nginx.

## Proxy API
nginx proxya `/api/` hacia el servicio FastAPI en `http://fastapi:8000/`.
