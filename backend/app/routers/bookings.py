"""Lịch xem phòng (F08, SPEC 9.3)."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import AppError, invalid_transition, not_found
from ..models import Booking, House, Room, User
from ..schemas import BookingAction, BookingIn
from ..security import get_current_user, require_role, require_student
from .common import Page, iso, paginate

router = APIRouter(prefix="/bookings", tags=["bookings"])

MIN_LEAD = timedelta(hours=2)
MAX_AHEAD = timedelta(days=14)
MAX_REQUESTED = 3


def booking_out(b: Booking, viewer: User) -> dict:
    room = b.room
    house = room.house
    out = {
        "id": str(b.id),
        "status": b.status,
        "slot_start": iso(b.slot_start),
        "student_note": b.student_note,
        "landlord_note": b.landlord_note,
        "reminded_at": iso(b.reminded_at),
        "created_at": iso(b.created_at),
        "room": {
            "id": str(room.id),
            "title": room.title,
            "street": house.street,
            "ward": house.ward,
            "area": house.area,
        },
    }
    if viewer.role == "landlord":
        # Chủ trọ cần liên hệ sinh viên đã đặt lịch (dữ liệu chỉ nằm trong OpenStack).
        out["student"] = {"full_name": b.student.full_name, "phone": b.student.phone}
        out["house_name"] = house.name
    elif viewer.role == "student" and b.status == "confirmed":
        # Đề xuất bổ sung SPEC: lịch đã xác nhận thì sinh viên thấy địa chỉ chi tiết để đến xem.
        out["room"]["address"] = house.address_private
        out["landlord"] = {"full_name": house.landlord.full_name, "phone": house.landlord.phone}
    return out


@router.post("", status_code=201)
def create_booking(body: BookingIn, user: User = Depends(require_student), db: Session = Depends(get_db)):
    room = db.get(Room, body.room_id)
    if room is None:
        raise not_found("Không tìm thấy phòng")
    if room.status != "published":
        raise AppError(409, "ROOM_NOT_PUBLISHED", "Phòng không còn công khai")
    now = datetime.now(timezone.utc)
    slot = body.slot_start.astimezone(timezone.utc)
    if slot < now + MIN_LEAD:
        raise AppError(422, "VALIDATION_ERROR", "Giờ hẹn phải cách hiện tại ít nhất 2 giờ", {"field": "slot_start"})
    if slot > now + MAX_AHEAD:
        raise AppError(422, "VALIDATION_ERROR", "Chỉ đặt lịch trong vòng 14 ngày tới", {"field": "slot_start"})
    # Khóa theo sinh viên để đếm số lịch đang chờ chính xác khi gửi đồng thời.
    db.execute(select(User.id).where(User.id == user.id).with_for_update())
    pending = db.scalar(select(func.count()).where(Booking.student_id == user.id, Booking.status == "requested"))
    if pending >= MAX_REQUESTED:
        raise AppError(409, "BOOKING_LIMIT", "Bạn đã có 3 lịch đang chờ xác nhận")
    booking = Booking(room_id=room.id, student_id=user.id, slot_start=slot, student_note=body.student_note)
    db.add(booking)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "BOOKING_CONFLICT", "Khung giờ này đã có người đặt")
    db.refresh(booking)
    return booking_out(booking, user)


@router.get("")
def list_bookings(
    status: str | None = Query(None, pattern="^(requested|confirmed|declined|cancelled|done)$"),
    page: Page = Depends(),
    user: User = Depends(require_role("student", "landlord")),
    db: Session = Depends(get_db),
):
    stmt = select(Booking)
    if user.role == "student":
        stmt = stmt.where(Booking.student_id == user.id)
    else:
        stmt = stmt.join(Room, Room.id == Booking.room_id).join(House, House.id == Room.house_id).where(House.landlord_id == user.id)
    if status:
        stmt = stmt.where(Booking.status == status)
    stmt = stmt.order_by(Booking.slot_start.desc())
    rows, total = paginate(db, stmt, page)
    return page.wrap([booking_out(b, user) for b in rows], total)


def _load(db: Session, booking_id: uuid.UUID, user: User) -> Booking:
    b = db.scalars(select(Booking).where(Booking.id == booking_id).with_for_update(of=Booking)).first()
    if b is None:
        raise not_found("Không tìm thấy lịch")
    if user.role == "student" and b.student_id == user.id:
        return b
    if user.role == "landlord" and b.room.house.landlord_id == user.id:
        return b
    raise not_found("Không tìm thấy lịch")


def _transition(db: Session, b: Booking, user: User, to: str, note: str | None) -> dict:
    if note and user.role == "landlord":
        b.landlord_note = note
    b.status = to
    db.commit()
    db.refresh(b)
    return booking_out(b, user)


@router.post("/{booking_id}/confirm")
def confirm(booking_id: uuid.UUID, body: BookingAction | None = Body(None), user: User = Depends(require_role("landlord")), db: Session = Depends(get_db)):
    b = _load(db, booking_id, user)
    if b.status != "requested":
        raise invalid_transition(f"Không thể xác nhận lịch đang ở trạng thái {b.status}")
    return _transition(db, b, user, "confirmed", body.note if body else None)


@router.post("/{booking_id}/decline")
def decline(booking_id: uuid.UUID, body: BookingAction | None = Body(None), user: User = Depends(require_role("landlord")), db: Session = Depends(get_db)):
    b = _load(db, booking_id, user)
    if b.status != "requested":
        raise invalid_transition(f"Không thể từ chối lịch đang ở trạng thái {b.status}")
    return _transition(db, b, user, "declined", body.note if body else None)


@router.post("/{booking_id}/cancel")
def cancel(booking_id: uuid.UUID, body: BookingAction | None = Body(None), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in ("student", "landlord"):
        raise AppError(403, "FORBIDDEN", "Bạn không có quyền thực hiện thao tác này")
    b = _load(db, booking_id, user)
    if b.status not in ("requested", "confirmed"):
        raise invalid_transition(f"Không thể hủy lịch đang ở trạng thái {b.status}")
    return _transition(db, b, user, "cancelled", body.note if body else None)


@router.post("/{booking_id}/done")
def done(booking_id: uuid.UUID, user: User = Depends(require_role("landlord")), db: Session = Depends(get_db)):
    b = _load(db, booking_id, user)
    if b.status != "confirmed":
        raise invalid_transition("Chỉ lịch đã xác nhận mới đánh dấu hoàn thành được")
    if b.slot_start > datetime.now(timezone.utc):
        raise invalid_transition("Chưa đến giờ hẹn")
    return _transition(db, b, user, "done", None)
