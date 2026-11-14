"""Định dạng lỗi chung (SPEC 10.1): {"error": {"code", "message", "details"}}."""
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict[str, Any] | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


def not_found(message: str = "Không tìm thấy") -> AppError:
    return AppError(404, "NOT_FOUND", message)


def invalid_transition(message: str = "Chuyển trạng thái không hợp lệ", **details: Any) -> AppError:
    return AppError(409, "INVALID_TRANSITION", message, details)


def validation_error(message: str, **details: Any) -> AppError:
    return AppError(422, "VALIDATION_ERROR", message, details)


def _body(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


_HTTP_CODES = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 429: "RATE_LIMITED"}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status, content=_body(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        fields = []
        for err in exc.errors():
            fields.append({"loc": [str(p) for p in err.get("loc", [])], "msg": err.get("msg", "")})
        return JSONResponse(
            status_code=422,
            content=_body("VALIDATION_ERROR", "Dữ liệu không hợp lệ", {"fields": fields}),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        import logging

        logging.getLogger("phongtro.api").exception("Lỗi không mong đợi ở %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content=_body("INTERNAL_ERROR", "Lỗi máy chủ, vui lòng thử lại sau"))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else code
        return JSONResponse(status_code=exc.status_code, content=_body(code, message), headers=exc.headers)
