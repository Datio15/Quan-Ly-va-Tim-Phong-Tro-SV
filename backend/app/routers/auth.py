import logging
import secrets
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..errors import AppError
from ..models import User
from ..schemas import LoginIn, MePatch, RegisterIn
from ..security import create_access_token, get_current_user, hash_password, login_rate_limit, verify_password
from .common import user_out

log = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(tags=["auth"])


@router.post("/auth/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where(func.lower(User.email) == body.email)):
        raise AppError(409, "EMAIL_TAKEN", "Email này đã được đăng ký")
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        phone=body.phone,
        role=body.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "EMAIL_TAKEN", "Email này đã được đăng ký")
    log.info("Đăng ký tài khoản mới role=%s", user.role)
    return {"id": str(user.id), "email": user.email, "role": user.role}


@router.post("/auth/login", dependencies=[Depends(login_rate_limit)])
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(func.lower(User.email) == body.email)).first()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise AppError(401, "UNAUTHORIZED", "Email hoặc mật khẩu không đúng")
    token, expires_in = create_access_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": {"id": str(user.id), "role": user.role, "full_name": user.full_name},
    }


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.patch("/me")
def update_me(body: MePatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    if "full_name" in data and data["full_name"]:
        user.full_name = data["full_name"]
    if "phone" in data:
        user.phone = data["phone"]
    db.commit()
    return user_out(user)


_ALPHABET = string.ascii_letters + string.digits


@router.post("/me/telegram-link")
def telegram_link(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """SPEC 3F: mã ngẫu nhiên 16 ký tự, hạn 15 phút; worker khớp mã qua getUpdates."""
    if not settings.telegram_bot_name:
        raise AppError(503, "UPSTREAM_UNAVAILABLE", "Chưa cấu hình bot Telegram")
    code = "".join(secrets.choice(_ALPHABET) for _ in range(16))
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    user.telegram_link_code = code
    user.telegram_link_expires = expires
    db.commit()
    return {
        "url": f"https://t.me/{settings.telegram_bot_name}?start={code}",
        "expires_at": expires.isoformat(),
        "linked": bool(user.telegram_chat_id),
    }
