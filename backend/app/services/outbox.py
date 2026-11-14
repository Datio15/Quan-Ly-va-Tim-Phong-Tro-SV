"""Ghi `sync_outbox` CÙNG transaction với thay đổi phòng (SPEC 3A, 9.2).

Quy tắc: mỗi lần sửa phòng thì tăng `rooms.version`; nếu phòng đang (hoặc vừa thôi) `published`
thì chèn một dòng outbox. `op = upsert` nếu phòng đang published, ngược lại `delete`.
Worker luôn dựng lại tài liệu từ `v_rooms_public`, `payload` chỉ để gỡ lỗi (không chứa dữ liệu cá nhân).
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import House, Room, SyncOutbox


def room_changed(db: Session, room: Room, *, was_published: bool, reason: str) -> bool:
    """Tăng version và ghi outbox nếu cần. Trả True nếu đã ghi outbox."""
    room.version = (room.version or 1) + 1
    if room.status == "published" or was_published:
        db.add(
            SyncOutbox(
                entity_type="room",
                entity_id=room.id,
                entity_version=room.version,
                op="upsert" if room.status == "published" else "delete",
                payload={"reason": reason},
            )
        )
        return True
    return False


def published_room_changed(db: Session, room: Room, reason: str) -> bool:
    """Thay đổi gián tiếp (đánh giá, ảnh được duyệt, xác minh chủ trọ): chỉ ghi khi phòng đang công khai."""
    if room.status != "published":
        return False
    return room_changed(db, room, was_published=True, reason=reason)


def landlord_rooms_changed(db: Session, landlord_id: uuid.UUID, reason: str) -> int:
    rooms = db.scalars(
        select(Room).join(House, House.id == Room.house_id).where(House.landlord_id == landlord_id, Room.status == "published")
    ).all()
    for room in rooms:
        room_changed(db, room, was_published=True, reason=reason)
    return len(rooms)


def house_rooms_changed(db: Session, house_id: uuid.UUID, reason: str) -> int:
    rooms = db.scalars(select(Room).where(Room.house_id == house_id, Room.status == "published")).all()
    for room in rooms:
        room_changed(db, room, was_published=True, reason=reason)
    return len(rooms)
