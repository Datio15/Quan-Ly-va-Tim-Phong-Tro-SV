"""Băm mật khẩu (argon2), JWT, phụ thuộc kiểm tra vai trò (SPEC mục 7, 19)."""
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .errors import AppError
from .models import User

_hasher = PasswordHasher()
_bearer = HTTPBearer(auto_error=False)
settings = get_settings()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _secret() -> str:
    if not settings.jwt_secret or settings.jwt_secret == "CHANGE_ME":
        raise RuntimeError("JWT_SECRET chưa được cấu hình")
    return settings.jwt_secret


def create_access_token(user: User) -> tuple[str, int]:
    expires_in = settings.jwt_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user.id), "role": user.role, "iat": now, "exp": now + timedelta(seconds=expires_in)}
    return jwt.encode(payload, _secret(), algorithm="HS256"), expires_in


def create_signed_token(purpose: str, data: dict, minutes: int = 5) -> str:
    """Token ngắn hạn cho URL ký trước (file trong bucket private, SPEC 19)."""
    now = datetime.now(timezone.utc)
    payload = {"purpose": purpose, **data, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, _secret(), algorithm="HS256")


def decode_signed_token(token: str, purpose: str) -> dict:
    try:
        payload = jwt.decode(token, _secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise AppError(401, "UNAUTHORIZED", "Liên kết không hợp lệ hoặc đã hết hạn")
    if payload.get("purpose") != purpose:
        raise AppError(401, "UNAUTHORIZED", "Liên kết không hợp lệ")
    return payload


def _user_from_token(token: str, db: Session) -> User:
    try:
        payload = jwt.decode(token, _secret(), algorithms=["HS256"])
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise AppError(401, "UNAUTHORIZED", "Token không hợp lệ hoặc đã hết hạn")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AppError(401, "UNAUTHORIZED", "Tài khoản không tồn tại hoặc đã bị khóa")
    return user


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise AppError(401, "UNAUTHORIZED", "Cần đăng nhập")
    return _user_from_token(creds.credentials, db)


def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User | None:
    if creds is None:
        return None
    try:
        return _user_from_token(creds.credentials, db)
    except AppError:
        return None


def require_role(*roles: str):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AppError(403, "FORBIDDEN", "Bạn không có quyền thực hiện thao tác này")
        return user

    return _dep


require_student = require_role("student")
require_landlord = require_role("landlord")
require_admin = require_role("admin")


class RateLimiter:
    """Giới hạn tần suất đơn giản trong bộ nhớ (mỗi tiến trình api): N lần / cửa sổ / IP."""

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def __call__(self, request: Request) -> None:
        # request.client đã được uvicorn --proxy-headers thay bằng IP thật từ nginx (X-Forwarded-For),
        # chỉ khi yêu cầu đến từ mạng tin cậy (FORWARDED_ALLOW_IPS). Không đọc header trực tiếp để tránh giả mạo.
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        hits = self._hits[ip]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            raise AppError(429, "RATE_LIMITED", "Thử quá nhiều lần, vui lòng đợi một phút")
        hits.append(now)


login_rate_limit = RateLimiter(limit=10, window_seconds=60)
