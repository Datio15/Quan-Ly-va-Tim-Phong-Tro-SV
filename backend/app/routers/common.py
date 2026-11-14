"""Tiện ích dùng chung cho router: phân trang, tìm tài nguyên theo quyền sở hữu, nhật ký."""
import uuid
from datetime import datetime

from fastapi import Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..errors import not_found
from ..models import AuditLog, House, Room, User


class Page:
    def __init__(self, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50)):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    def wrap(self, items: list, total: int) -> dict:
        return {"items": items, "page": self.page, "page_size": self.page_size, "total": total}


def paginate(db: Session, stmt, page: Page):
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.scalars(stmt.limit(page.page_size).offset(page.offset)).unique().all()
    return rows, total or 0


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def owned_house(db: Session, house_id: uuid.UUID, landlord: User) -> House:
    house = db.get(House, house_id)
    if house is None or house.landlord_id != landlord.id:
        raise not_found("Không tìm thấy nhà")
    return house


def owned_room(db: Session, room_id: uuid.UUID, landlord: User, *, lock: bool = False) -> Room:
    stmt = select(Room).join(House, House.id == Room.house_id).where(Room.id == room_id, House.landlord_id == landlord.id)
    if lock:
        stmt = stmt.with_for_update(of=Room)
    room = db.scalars(stmt).first()
    if room is None:
        raise not_found("Không tìm thấy phòng")
    return room


def audit(db: Session, user: User | None, action: str, entity: str, entity_id: uuid.UUID | None, **meta) -> None:
    """Nhật ký thao tác. Không ghi dữ liệu cá nhân vào meta."""
    db.add(AuditLog(user_id=user.id if user else None, action=action, entity=entity, entity_id=entity_id, meta=meta))


def user_out(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "role": user.role,
        "verified": user.verified,
        "telegram_linked": bool(user.telegram_chat_id),
        "created_at": iso(user.created_at),
    }


def short_name(full_name: str) -> str:
    """Hiển thị tên ngắn gọn cho người lạ (vd đánh giá công khai): chỉ tên gọi."""
    parts = full_name.split()
    return parts[-1] if parts else ""
