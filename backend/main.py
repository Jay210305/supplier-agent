from config import settings  # loads & validates env (POSTGRES_HOST required)

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from db.session import engine
from limiter import limiter
from routers import orders, procurement, suppliers

app = FastAPI(title="Supplier Agent API", version="0.1.0")
app.state.limiter = limiter
app.include_router(procurement.router, prefix="/procurement", tags=["procurement"])
app.include_router(suppliers.router, prefix="/suppliers", tags=["suppliers"])
app.include_router(orders.router, prefix="/orders", tags=["orders"])


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(_request: Request, _exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Maximum 10 requests per minute."},
    )


def _ollama_has_model(tags_body: dict, model_name: str) -> bool:
    for m in tags_body.get("models") or []:
        name = m.get("name") or ""
        if name == model_name or name.split(":")[0] == model_name.split(":")[0]:
            return True
    return False


@app.get("/health")
async def health() -> JSONResponse:
    postgres_status = "error"
    ollama_status = "error"
    model_ok = False

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
                data = response.json()
                model_ok = _ollama_has_model(data, settings.OLLAMA_MODEL)
                ollama_status = "ok" if model_ok else "degraded"
    except Exception:
        ollama_status = "error"

    healthy = postgres_status == "ok" and ollama_status == "ok"
    payload = {
        "postgres": postgres_status,
        "ollama": ollama_status,
        "ollama_model": settings.OLLAMA_MODEL,
        "ollama_model_ready": model_ok,
    }
    return JSONResponse(payload, status_code=200 if healthy else 503)
