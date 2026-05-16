# Frontend

## Stack
- React 18 + Vite
- Served by nginx in Docker

## Current UI
The UI is a placeholder page that confirms the API is available at `/api` via nginx.

## API proxy
nginx proxies `/api/` to the FastAPI service at `http://fastapi:8000/`.
