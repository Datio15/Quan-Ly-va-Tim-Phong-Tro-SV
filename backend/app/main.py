"""Tạo FastAPI, gắn router, middleware đo thời gian (SPEC mục 6)."""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .errors import install_error_handlers
from .routers import admin, auth, bookings, health, landlord, landlord_ops, public, rooms
from .services import storage
from .services.metrics import setup_telemetry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("phongtro.api")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    storage.ensure_buckets()
    yield


app = FastAPI(title="EasyRent API", version="0.3.0", lifespan=lifespan, docs_url="/api/docs",
              openapi_url="/api/openapi.json", redoc_url=None)
install_error_handlers(app)
setup_telemetry(app)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"],
        expose_headers=["X-Search-Source"],
    )


@app.middleware("http")
async def timing(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
    if elapsed_ms > 2000:
        # Chỉ ghi đường dẫn mẫu (route), không ghi query string vì có thể chứa dữ liệu người dùng.
        route = request.scope.get("route")
        log.warning("Chậm %.0f ms: %s %s", elapsed_ms, request.method, getattr(route, "path", "?"))
    return response


API = "/api/v1"
for r in (health.router, auth.router, public.router, rooms.router, bookings.router, landlord.router,
          landlord_ops.router, admin.router):
    app.include_router(r, prefix=API)
