"""Cấu hình cho giao diện, danh mục, phục vụ ảnh và file ký trước."""
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..errors import not_found
from ..models import Amenity, Room, RoomImage, School
from ..security import decode_signed_token
from ..services import storage

settings = get_settings()
router = APIRouter(tags=["public"])


@router.get("/config")
def config():
    return {
        "maps_key": settings.maps_key_public,
        "telegram_bot": settings.telegram_bot_name,
        "est_defaults": {
            "kwh": settings.est_kwh_per_month,
            "m3": settings.est_water_m3_per_month,
            "people": settings.est_people,
            "vehicles": settings.est_vehicles,
        },
    }


@router.get("/schools")
def schools(db: Session = Depends(get_db)):
    rows = db.scalars(select(School).order_by(School.name)).all()
    return [{"id": str(s.id), "name": s.name, "short_name": s.short_name, "lat": s.lat, "lng": s.lng} for s in rows]


@router.get("/amenities")
def amenities(db: Session = Depends(get_db)):
    rows = db.scalars(select(Amenity).order_by(Amenity.label_vi)).all()
    return [{"code": a.code, "label": a.label_vi} for a in rows]


@router.get("/images/{image_id}", include_in_schema=False)
def image(image_id: uuid.UUID, t: str | None = Query(None, max_length=2000), db: Session = Depends(get_db)):
    """Đề xuất bổ sung SPEC: ảnh phòng (bucket public-src) khi chưa có bản trên Blob.
    MinIO chỉ mở cho sg-app nên trình duyệt không truy cập thẳng được.

    Không có token: chỉ ảnh đã duyệt của phòng đang công khai. Có token ký (trang chủ trọ/quản trị):
    mọi ảnh của phòng đó, kể cả chờ duyệt (BE-10)."""
    img = db.get(RoomImage, image_id)
    if img is None:
        raise not_found("Không tìm thấy ảnh")
    if t is not None:
        if decode_signed_token(t, "image").get("img") != str(image_id):
            raise not_found("Không tìm thấy ảnh")
        cache = "private, max-age=300"
    else:
        room = db.get(Room, img.room_id)
        if img.moderation != "ok" or room is None or room.status != "published":
            raise not_found("Không tìm thấy ảnh")
        cache = "public, max-age=300"
    try:
        data, ctype = storage.get(settings.minio_bucket_public_src, img.object_key)
    except Exception:
        raise not_found("Không tìm thấy ảnh")
    return Response(content=data, media_type=ctype, headers={"Cache-Control": cache})


@router.get("/files/signed", include_in_schema=False)
def signed_file(token: str = Query(...)):
    """URL ký trước, hạn 5 phút, cho file trong bucket private (SPEC 19)."""
    payload = decode_signed_token(token, "private-file")
    try:
        data, ctype = storage.get(settings.minio_bucket_private, payload["key"])
    except Exception:
        raise not_found("Không tìm thấy file")
    return Response(content=data, media_type=ctype, headers={"Cache-Control": "private, no-store"})
