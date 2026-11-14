from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from ..db import engine
from ..services import storage

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    body = {"status": "ok" if db_ok else "degraded", "db": db_ok, "minio": storage.healthy()}
    return JSONResponse(status_code=200 if db_ok else 503, content=body)
