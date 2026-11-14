"""Đặt mật khẩu cho tài khoản demo trong seed từ SEED_DEMO_PASSWORD (SPEC 18).

Chạy: python -m app.seed_passwords        (chỉ đặt cho tài khoản có hash '!unset-...')
      python -m app.seed_passwords --all  (đặt lại cho mọi tài khoản @example.com)
Có chờ CSDL sẵn sàng tối đa ~60 giây để dùng làm bước khởi động container.
"""
import sys
import time

from sqlalchemy import text

from .config import get_settings
from .db import engine
from .security import hash_password


def wait_for_db(seconds: int = 60) -> None:
    deadline = time.monotonic() + seconds
    while True:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM users LIMIT 1"))
            return
        except Exception as exc:
            if time.monotonic() > deadline:
                raise SystemExit(f"CSDL chưa sẵn sàng: {type(exc).__name__}")
            print("Đang chờ CSDL...", flush=True)
            time.sleep(2)


def main() -> None:
    settings = get_settings()
    wait_for_db()
    pw = settings.seed_demo_password
    if not pw or pw == "CHANGE_ME" or len(pw) < 8:
        print("Bỏ qua: SEED_DEMO_PASSWORD chưa đặt hoặc ngắn hơn 8 ký tự")
        return
    where = "email LIKE '%@example.com'" if "--all" in sys.argv else "password_hash LIKE '!unset%'"
    with engine.begin() as conn:
        n = conn.execute(text(f"UPDATE users SET password_hash = :h WHERE {where}"), {"h": hash_password(pw)}).rowcount
    print(f"Đã đặt mật khẩu demo cho {n} tài khoản")


if __name__ == "__main__":
    main()
