"""Chủ trọ: nhà, phòng, ảnh, bảng giá, tiện nghi (F02, F03). Mọi API kiểm tra QUYỀN SỞ HỮU (SPEC 7)."""
import logging
import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import delete, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..errors import AppError, invalid_transition, not_found
from ..models import Amenity, CostRate, House, Room, RoomAmenity, RoomImage, Tenant, User
from ..schemas import HouseIn, HousePatch, RoomIn, RoomPatch
from ..security import require_landlord
from ..services import storage
from ..services.outbox import house_rooms_changed, published_room_changed, room_changed
from ..services.rooms_public import image_url
from .common import Page, audit, iso, owned_house, owned_room, paginate

log = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/landlord", tags=["landlord"])

MAX_IMAGES = 10
PUBLIC_HOUSE_FIELDS = {"street", "ward", "area", "city", "lat", "lng"}


# ---------- Nhà ----------
def house_out(h: House, room_count: int | None = None) -> dict:
    out = {
        "id": str(h.id), "name": h.name, "address_private": h.address_private, "street": h.street, "ward": h.ward,
        "area": h.area, "city": h.city, "lat": h.lat, "lng": h.lng, "created_at": iso(h.created_at),
    }
    if room_count is not None:
        out["room_count"] = room_count
    return out


@router.get("/houses")
def list_houses(user: User = Depends(require_landlord), db: Session = Depends(get_db)):
    rows = db.execute(
        select(House, func.count(Room.id))
        .outerjoin(Room, Room.house_id == House.id)
        .where(House.landlord_id == user.id)
        .group_by(House.id)
        .order_by(House.created_at)
    ).unique().all()
    return [house_out(h, n) for h, n in rows]


@router.post("/houses", status_code=201)
def create_house(body: HouseIn, user: User = Depends(require_landlord), db: Session = Depends(get_db)):
    house = House(landlord_id=user.id, **body.model_dump())
    db.add(house)
    db.commit()
    return house_out(house, 0)


@router.get("/houses/{house_id}")
def get_house(house_id: uuid.UUID, user: User = Depends(require_landlord), db: Session = Depends(get_db)):
    house = owned_house(db, house_id, user)
    n = db.scalar(select(func.count()).where(Room.house_id == house.id))
    return house_out(house, n)


@router.patch("/houses/{house_id}")
def update_house(house_id: uuid.UUID, body: HousePatch, user: User = Depends(require_landlord), db: Session = Depends(get_db)):
    house = owned_house(db, house_id, user)
    data = body.model_dump(exclude_unset=True)
    changed_public = False
    for key, value in data.items():
        if value is None and key not in ("lat", "lng"):
            continue
        if getattr(house, key) != value:
            setattr(house, key, value)
            changed_public |= key in PUBLIC_HOUSE_FIELDS
    if changed_public:
        house_rooms_changed(db, house.id, "house_update")
    db.commit()
    return get_house(house_id, user, db)


@router.delete("/houses/{house_id}")
def delete_house(house_id: uuid.UUID, user: User = Depends(require_landlord), db: Session = Depends(get_db)):
    house = owned_house(db, house_id, user)
    has_tenant = db.scalar(
        select(exists().where(Tenant.room_id == Room.id, Room.house_id == house.id))
    )
    if has_tenant:
        raise invalid_transition("Không xóa được nhà còn phòng có khách thuê (hoặc lịch sử khách thuê/hóa đơn)")
    rooms = db.scalars(select(Room).where(Room.house_id == house.id)).all()
    keys = []
    for room in rooms:
        was_published = room.status == "published"
        room.status = "hidden"
        room_changed(db, room, was_published=was_published, reason="house_delete")
        keys += db.scalars(select(RoomImage.object_key).where(RoomImage.room_id == room.id)).all()
    db.flush()
    db.delete(house)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise invalid_transition("Không xóa được nhà vì còn dữ liệu liên quan")
    for key in keys:
        storage.remove(settings.minio_bucket_public_src, key)
    return {"id": str(house_id), "deleted": True}


# ---------- Phòng ----------
def _amenities(db: Session, room_id: uuid.UUID) -> list[str]:
    return list(db.scalars(select(RoomAmenity.amenity_code).where(RoomAmenity.room_id == room_id).order_by(RoomAmenity.amenity_code)))


def _cost_rates_out(cr: CostRate | None) -> dict:
    if cr is None:
        return {"electricity_per_kwh": 0, "water_mode": "per_m3", "water_per_m3": 0, "water_per_person": 0,
                "internet_per_month": 0, "parking_per_vehicle": 0, "service_per_month": 0}
    return {
        "electricity_per_kwh": cr.electricity_per_kwh, "water_mode": cr.water_mode, "water_per_m3": cr.water_per_m3,
        "water_per_person": cr.water_per_person, "internet_per_month": cr.internet_per_month,
        "parking_per_vehicle": cr.parking_per_vehicle, "service_per_month": cr.service_per_month,
    }


def image_out(i: RoomImage) -> dict:
    return {
        "id": str(i.id), "url": image_url(i.id, i.public_url), "position": i.position, "moderation": i.moderation,
        "moderation_note": i.moderation_note, "synced": bool(i.public_url),
    }


def room_summary(r: Room) -> dict:
    return {
        "id": str(r.id), "house_id": str(r.house_id), "house_name": r.house.name, "title": r.title,
        "price_month": r.price_month, "area_m2": float(r.area_m2), "max_people": r.max_people, "floor": r.floor,
        "status": r.status, "reject_reason": r.reject_reason, "version": r.version,
        "published_at": iso(r.published_at), "updated_at": iso(r.updated_at),
    }


def room_full(db: Session, r: Room) -> dict:
    images = db.scalars(select(RoomImage).where(RoomImage.room_id == r.id).order_by(RoomImage.position, RoomImage.created_at)).all()
    return room_summary(r) | {
        "description": r.description,
        "deposit_amount": r.deposit_amount,
        "curfew_time": r.curfew_time.strftime("%H:%M") if r.curfew_time else None,
        "available_from": r.available_from.isoformat() if r.available_from else None,
        "amenities": _amenities(db, r.id),
        "cost_rates": _cost_rates_out(db.get(CostRate, r.id)),
        "images": [image_out(i) for i in images],
        "house": {"id": str(r.house.id), "name": r.house.name, "street": r.house.street, "ward": r.house.ward,
                  "area": r.house.area, "city": r.house.city, "lat": r.house.lat, "lng": r.house.lng},
    }


def _set_amenities(db: Session, room_id: uuid.UUID, codes: list[str]) -> None:
    codes = sorted(set(codes))
    if codes:
        known = set(db.scalars(select(Amenity.code).where(Amenity.code.in_(codes))))
        unknown = [c for c in codes if c not in known]
        if unknown:
            raise AppError(422, "VALIDATION_ERROR", "Mã tiện nghi không hợp lệ", {"unknown": unknown})
    db.execute(delete(RoomAmenity).where(RoomAmenity.room_id == room_id))
    for code in codes:
        db.add(RoomAmenity(room_id=room_id, amenity_code=code))


def _set_cost_rates(db: Session, room_id: uuid.UUID, data: dict) -> None:
    cr = db.get(CostRate, room_id)
    if cr is None:
        db.add(CostRate(room_id=room_id, **data))
    else:
        for k, v in data.items():
            setattr(cr, k, v)


@router.get("/rooms")
def list_rooms(
    house_id: uuid.UUID | None = None,
    status: str | None = Query(None, pattern="^(draft|pending|published|hidden|rejected)$"),
    page: Page = Depends(),
    user: User = Depends(require_landlord),
    db: Session = Depends(get_db),
):
    stmt = select(Room).join(House, House.id == Room.house_id).where(House.landlord_id == user.id)
    if house_id:
        stmt = stmt.where(Room.house_id == house_id)
    if status:
        stmt = stmt.where(Room.status == status)
    rows, total = paginate(db, stmt.order_by(Room.created_at.desc(), Room.id), page)
    items = []
    for r in rows:
        thumb = db.scalars(select(RoomImage).where(RoomImage.room_id == r.id).order_by(RoomImage.position).limit(1)).first()
        items.append(room_summary(r) | {"thumbnail_url": image_url(thumb.id, thumb.public_url) if thumb else None})
    return page.wrap(items, total)


@router.post("/rooms", status_code=201)
def create_room(body: RoomIn, user: User = Depends(require_landlord), db: Session = Depends(get_db)):
    owned_house(db, body.house_id, user)
    data = body.model_dump(exclude={"amenities", "cost_rates"})
    room = Room(**data, status="draft", version=1)
    db.add(room)
    db.flush()
    _set_amenities(db, room.id, body.amenities)
    _set_cost_rates(db, room.id, body.cost_rates.model_dump())
    audit(db, user, "room.create", "room", room.id)
    db.commit()
    db.refresh(room)
    return room_full(db, room)


@router.get("/rooms/{room_id}")
def get_room(room_id: uuid.UUID, user: User = Depends(require_landlord), db: Session = Depends(get_db)):
    return room_full(db, owned_room(db, room_id, user))


@router.patch("/rooms/{room_id}")
def update_room(room_id: uuid.UUID, body: RoomPatch, user: User = Depends(require_landlord), db: Session = Depends(get_db)):
    room = owned_room(db, room_id, user, lock=True)
    data = body.model_dump(exclude_unset=True)
    if not data:
        return room_full(db, room)
    if "house_id" in data and data["house_id"] is not None:
        owned_house(db, data["house_id"], user)
    was_published = room.status == "published"
    amenities = data.pop("amenities", None)
    cost_rates = data.pop("cost_rates", None)
    nullable = {"floor", "curfew_time", "available_from"}
    for key, value in data.items():
        if value is None and key not in nullable:
            continue
        setattr(room, key, value)
    if amenities is not None:
        _set_amenities(db, room.id, amenities)
    if cost_rates is not None:
        _set_cost_rates(db, room.id, cost_rates)
    if room.status == "rejected":
        room.status = "draft"  # sửa lại sau khi bị từ chối (SPEC 9.1)
        room.reject_reason = None
    room_changed(db, room, was_published=was_published, reason="room_update")
    db.commit()
    db.refresh(room)
    return room_full(db, room)


@router.post("/rooms/{room_id}/submit")
def submit_room(room_id: uuid.UUID, user: User = Depends(require_landlord), db: Session = Depends(get_db)):
    room = owned_room(db, room_id, user, lock=True)
    if room.status not in ("draft", "rejected"):
        raise invalid_transition(f"Không thể gửi duyệt phòng đang ở trạng thái {room.status}")
    if room.house.lat is None or room.house.lng is None:
        raise AppError(422, "VALIDATION_ERROR", "Nhà chưa có tọa độ; hãy đặt ghim trên bản đồ trước khi gửi duyệt")
    room.status = "pending"
    room.reject_reason = None
    room_changed(db, room, was_published=False, reason="submit")
    audit(db, user, "room.submit", "room", room.id)
    db.commit()
    return room_full(db, room)


@router.post("/rooms/{room_id}/hide")
def hide_room(room_id: uuid.UUID, user: User = Depends(require_landlord), db: Session = Depends(get_db)):
    room = owned_room(db, room_id, user, lock=True)
    if room.status != "published":
        raise invalid_transition("Chỉ ẩn được phòng đang công khai")
    room.status = "hidden"
    room_changed(db, room, was_published=True, reason="hide")
    audit(db, user, "room.hide", "room", room.id)
    db.commit()
    return room_full(db, room)


@router.post("/rooms/{room_id}/unhide")
def unhide_room(room_id: uuid.UUID, user: User = Depends(require_landlord), db: Session = Depends(get_db)):
    room = owned_room(db, room_id, user, lock=True)
    if room.status != "hidden":
        raise invalid_transition("Chỉ hiện lại được phòng đang ẩn")
    if room.published_at is None:
        raise invalid_transition("Phòng chưa từng được duyệt; hãy gửi duyệt")
    room.status = "published"
    room_changed(db, room, was_published=False, reason="unhide")
    audit(db, user, "room.unhide", "room", room.id)
    db.commit()
    return room_full(db, room)


# ---------- Ảnh ----------
@router.post("/rooms/{room_id}/images", status_code=201)
async def upload_image(
    room_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(require_landlord),
    db: Session = Depends(get_db),
):
    room = owned_room(db, room_id, user, lock=True)
    count = db.scalar(select(func.count()).where(RoomImage.room_id == room.id))
    if count >= MAX_IMAGES:
        raise AppError(422, "VALIDATION_ERROR", f"Mỗi phòng tối đa {MAX_IMAGES} ảnh")
    data = await file.read(storage.MAX_IMAGE_BYTES + 1)
    if len(data) > storage.MAX_IMAGE_BYTES:
        raise AppError(422, "VALIDATION_ERROR", "Ảnh tối đa 5 MB")
    kind = storage.sniff_image(data)
    if kind is None:
        raise AppError(422, "VALIDATION_ERROR", "Chỉ nhận ảnh JPEG hoặc PNG")
    ctype, ext = kind
    image_id = uuid.uuid4()
    key = f"rooms/{room.id}/{image_id}.{ext}"  # tên do server sinh, không dùng tên file người dùng gửi
    try:
        storage.put(settings.minio_bucket_public_src, key, data, ctype)
    except Exception as exc:
        log.error("Tải ảnh lên MinIO lỗi: %s", type(exc).__name__)
        raise AppError(503, "UPSTREAM_UNAVAILABLE", "Kho ảnh tạm thời không phản hồi")
    max_pos = db.scalar(select(func.coalesce(func.max(RoomImage.position), -1)).where(RoomImage.room_id == room.id))
    img = RoomImage(id=image_id, room_id=room.id, object_key=key, position=max_pos + 1, moderation="pending")
    db.add(img)
    db.commit()
    db.refresh(img)
    return image_out(img)


@router.delete("/rooms/{room_id}/images/{image_id}")
def delete_image(room_id: uuid.UUID, image_id: uuid.UUID, user: User = Depends(require_landlord), db: Session = Depends(get_db)):
    room = owned_room(db, room_id, user, lock=True)
    img = db.get(RoomImage, image_id)
    if img is None or img.room_id != room.id:
        raise not_found("Không tìm thấy ảnh")
    was_public = img.moderation == "ok"
    key = img.object_key
    db.delete(img)
    if was_public:
        published_room_changed(db, room, "image_delete")
    db.commit()
    storage.remove(settings.minio_bucket_public_src, key)
    return {"id": str(image_id), "deleted": True}
