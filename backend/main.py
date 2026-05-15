from config import settings  # loads & validates env (POSTGRES_HOST required)

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from db.session import engine
from routers import orders, procurement, suppliers

app = FastAPI(title="Supplier Agent API", version="0.1.0")

app.include_router(procurement.router, prefix="/procurement", tags=["procurement"])
app.include_router(suppliers.router, prefix="/suppliers", tags=["suppliers"])
app.include_router(orders.router, prefix="/orders", tags=["orders"])


@app.get("/health")
async def health() -> JSONResponse:
    postgres_status = "error"
    ollama_status = "error"

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        postgres_status = "ok"
    except Exception:
        postgres_status = "error"

    try:
        base = settings.OLLAMA_BASE_URL.rstrip("/")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base}/api/tags")
            if response.is_success:
                ollama_status = "ok"
    except Exception:
        ollama_status = "error"

    healthy = postgres_status == "ok" and ollama_status == "ok"
    payload = {"postgres": postgres_status, "ollama": ollama_status}
    return JSONResponse(payload, status_code=200 if healthy else 503)
