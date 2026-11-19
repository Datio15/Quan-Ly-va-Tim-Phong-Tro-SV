"""Định dạng lỗi chung (SPEC 10.1): {"error": {"code", "message", "details"}}."""
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError, IntegrityError
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


_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

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

    def _db_error(request: Request, exc: Exception, message: str) -> JSONResponse:
        import logging

        log = logging.getLogger("phongtro.api")
        orig = getattr(exc, "orig", None)
        if request.method in _WRITE_METHODS:
            # Ghi dữ liệu vượt kiểu cột / vi phạm ràng buộc mà kiểm tra đầu vào bỏ sót: lỗi của yêu cầu -> 422.
            log.warning("%s ở %s %s: %s", type(exc).__name__, request.method, request.url.path,
                        type(orig).__name__ if orig else "?")
            return JSONResponse(status_code=422, content=_body("VALIDATION_ERROR", message))
        # Lệnh đọc mà gặp lỗi dữ liệu là lỗi PHÍA MÁY CHỦ (dữ liệu cũ hỏng, hàm SQL sai): trả 500 để giám sát
        # bắt được, không đổ lỗi cho người dùng (báo cáo QA 19/11, mục 8).
        log.error("%s ở %s %s", type(exc).__name__, request.method, request.url.path, exc_info=exc)
        return JSONResponse(status_code=500, content=_body("INTERNAL_ERROR", "Lỗi máy chủ, vui lòng thử lại sau"))

    @app.exception_handler(DataError)
    async def _db_data(request: Request, exc: DataError):
        return _db_error(request, exc, "Giá trị vượt giới hạn cho phép")

    @app.exception_handler(IntegrityError)
    async def _db_integrity(request: Request, exc: IntegrityError):
        return _db_error(request, exc, "Dữ liệu không thỏa ràng buộc của hệ thống")

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
