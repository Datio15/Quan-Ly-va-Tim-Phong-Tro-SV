"""Tìm phòng, chi tiết, chi phí, so sánh, đánh giá, báo cáo, yêu thích (F04-F07, F09, F11)."""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..errors import AppError, not_found
from ..models import Booking, Favorite, Report, Review, Room, RoomImage, School, User
from ..schemas import CompareIn, ReportIn, ReviewIn
from ..security import get_optional_user, require_student
from ..services.cost import CostInputs, cost_breakdown
from ..services.outbox import published_room_changed
from ..services.rooms_public import SearchParams, fetch_public_rooms, image_url
from ..services.search_service import search_rooms
from .common import Page, iso, short_name

settings = get_settings()
router = APIRouter(tags=["rooms"])

SortT = Literal["relevance", "price_asc", "price_desc", "cost_asc", "distance_asc", "rating_desc", "newest"]


def _school(db: Session, school_id: uuid.UUID | None) -> School | None:
    if school_id is None:
        return None
    school = db.get(School, school_id)
    if school is None:
        raise not_found("Không tìm thấy trường")
    return school


@router.get("/search/rooms")
def search(
    response: Response,
    q: str | None = Query(None, max_length=200),
    price_min: int | None = Query(None, ge=0),
    price_max: int | None = Query(None, ge=0),
    cost_max: int | None = Query(None, ge=0),
    area_min: float | None = Query(None, ge=0),
    area: list[str] = Query(default_factory=list),
    amenities: list[str] = Query(default_factory=list),
    no_curfew: bool = False,
    people: int | None = Query(None, ge=1, le=20),
    school_id: uuid.UUID | None = None,
    max_distance_m: int | None = Query(None, ge=0, le=100000),
    verified_only: bool = False,
    sort: SortT = "relevance",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    if sort == "distance_asc" and school_id is None:
        raise AppError(422, "VALIDATION_ERROR", "Sắp xếp theo khoảng cách cần chọn trường (school_id)")
    if max_distance_m is not None and school_id is None:
        raise AppError(422, "VALIDATION_ERROR", "Lọc theo khoảng cách cần chọn trường (school_id)")
    school = _school(db, school_id)
    params = SearchParams(
        q=(q or "").strip() or None,
        price_min=price_min,
        price_max=price_max,
        cost_max=cost_max,
        area_min=area_min,
        areas=[a.strip() for a in area if a.strip()],
        amenities=[a.strip() for a in amenities if a.strip()],
        no_curfew=no_curfew,
        people=people,
        school_lat=school.lat if school else None,
        school_lng=school.lng if school else None,
        max_distance_m=max_distance_m,
        verified_only=verified_only,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    result, source = search_rooms(db, params)
    response.headers["X-Search-Source"] = source
    return result


def _public_room_or_404(db: Session, room_id: uuid.UUID, school: School | None = None) -> dict:
    rooms = fetch_public_rooms(db, [room_id], (school.lat, school.lng) if school else None)
    if not rooms:
        raise not_found("Không tìm thấy phòng")
    return rooms[0]


@router.get("/rooms/{room_id}")
def room_detail(
    room_id: uuid.UUID,
    school_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    room = _public_room_or_404(db, room_id, _school(db, school_id))
    images = db.scalars(
        select(RoomImage).where(RoomImage.room_id == room_id, RoomImage.moderation == "ok").order_by(RoomImage.position, RoomImage.created_at)
    ).all()
    room["images"] = [{"id": str(i.id), "url": image_url(i.id, i.public_url)} for i in images]
    room["cost"] = cost_breakdown(db, room_id, CostInputs.defaults())
    room["is_favorite"] = bool(
        user and user.role == "student" and db.get(Favorite, {"user_id": user.id, "room_id": room_id})
    )
    return room


@router.get("/rooms/{room_id}/cost")
def room_cost(
    room_id: uuid.UUID,
    kwh: float | None = Query(None, ge=0, le=10000),
    m3: float | None = Query(None, ge=0, le=1000),
    people: int | None = Query(None, ge=1, le=20),
    vehicles: int | None = Query(None, ge=0, le=20),
    db: Session = Depends(get_db),
):
    room = db.get(Room, room_id)
    if room is None or room.status != "published":
        raise not_found("Không tìm thấy phòng")
    d = CostInputs.defaults()
    inputs = CostInputs(
        kwh=d.kwh if kwh is None else kwh,
        m3=d.m3 if m3 is None else m3,
        people=d.people if people is None else people,
        vehicles=d.vehicles if vehicles is None else vehicles,
    )
    return cost_breakdown(db, room_id, inputs)


@router.post("/rooms/compare")
def compare(body: CompareIn, db: Session = Depends(get_db)):
    ids = list(dict.fromkeys(body.ids))
    if len(ids) < 2:
        raise AppError(422, "VALIDATION_ERROR", "Cần 2-3 phòng khác nhau để so sánh")
    school = _school(db, body.school_id)
    rooms = fetch_public_rooms(db, ids, (school.lat, school.lng) if school else None)
    if len(rooms) != len(ids):
        raise not_found("Có phòng không tồn tại hoặc không còn công khai")
    out = [
        {
            "id": r["id"], "title": r["title"], "price_month": r["price_month"], "est_monthly_cost": r["est_monthly_cost"],
            "deposit_amount": r["deposit_amount"], "area_m2": r["area_m2"], "max_people": r["max_people"],
            "distance_m": r["distance_m"], "amenities": r["amenities"], "curfew": r["curfew"],
            "curfew_time": r["curfew_time"], "rating_avg": r["rating_avg"], "rating_count": r["rating_count"],
            "landlord_verified": r["landlord_verified"], "area": r["area"], "street": r["street"],
            "thumbnail_url": r["thumbnail_url"],
        }
        for r in rooms
    ]

    def best(key: str, lowest: bool) -> str | None:
        cands = [r for r in out if r.get(key) is not None]
        if not cands:
            return None
        pick = min(cands, key=lambda r: r[key]) if lowest else max(cands, key=lambda r: r[key])
        return pick["id"]

    return {
        "rooms": out,
        "best": {
            "price_month": best("price_month", True),
            "est_monthly_cost": best("est_monthly_cost", True),
            "area_m2": best("area_m2", False),
            "distance_m": best("distance_m", True),
            "rating_avg": best("rating_avg", False),
        },
    }


# ---------- Đánh giá ----------
def _review_out(rv: Review, me: User | None) -> dict:
    return {
        "id": str(rv.id),
        "rating": rv.rating,
        "comment": rv.comment,
        "student_name": short_name(rv.student.full_name),
        "created_at": iso(rv.created_at),
        "is_mine": bool(me and me.id == rv.student_id),
    }


@router.get("/rooms/{room_id}/reviews")
def room_reviews(
    room_id: uuid.UUID,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    room = db.get(Room, room_id)
    if room is None or room.status != "published":
        raise not_found("Không tìm thấy phòng")
    base = select(Review).where(Review.room_id == room_id, Review.is_hidden.is_(False))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(Review.created_at.desc()).limit(page.page_size).offset(page.offset)).unique().all()
    result = page.wrap([_review_out(r, user) for r in rows], total)
    result["can_review"] = False
    result["my_review"] = None
    if user and user.role == "student":
        mine = db.scalars(select(Review).where(Review.room_id == room_id, Review.student_id == user.id)).first()
        result["my_review"] = _review_out(mine, user) | {"is_hidden": mine.is_hidden} if mine else None
        result["can_review"] = settings.review_skip_booking_check or _has_done_booking(db, room_id, user.id)
    return result


def _has_done_booking(db: Session, room_id: uuid.UUID, student_id: uuid.UUID) -> bool:
    return bool(
        db.scalar(
            select(exists().where(Booking.room_id == room_id, Booking.student_id == student_id, Booking.status == "done"))
        )
    )


@router.put("/rooms/{room_id}/review")
def put_review(room_id: uuid.UUID, body: ReviewIn, user: User = Depends(require_student), db: Session = Depends(get_db)):
    room = db.scalars(select(Room).where(Room.id == room_id).with_for_update(of=Room)).first()
    if room is None or room.status != "published":
        raise not_found("Không tìm thấy phòng")
    if not settings.review_skip_booking_check and not _has_done_booking(db, room_id, user.id):
        raise AppError(403, "FORBIDDEN", "Chỉ đánh giá được sau khi đã xem phòng (có lịch hoàn thành)")
    review = db.scalars(select(Review).where(Review.room_id == room_id, Review.student_id == user.id)).first()
    created = review is None
    if created:
        review = Review(room_id=room_id, student_id=user.id, rating=body.rating, comment=body.comment)
        db.add(review)
    else:
        review.rating = body.rating
        review.comment = body.comment
    if not review.is_hidden:
        published_room_changed(db, room, "review")  # rating_avg đổi
    db.commit()
    db.refresh(review)
    return _review_out(review, user) | {"created": created}


# ---------- Báo cáo ----------
@router.post("/reports", status_code=201)
def create_report(body: ReportIn, user: User = Depends(require_student), db: Session = Depends(get_db)):
    if body.target_type == "room":
        target = db.get(Room, body.target_id)
        ok = target is not None and target.status == "published"
    else:
        target = db.get(Review, body.target_id)
        ok = target is not None and not target.is_hidden
    if not ok:
        raise not_found("Không tìm thấy đối tượng cần báo cáo")
    report = Report(target_type=body.target_type, target_id=body.target_id, reporter_id=user.id, reason=body.reason)
    db.add(report)
    db.commit()
    return {"id": str(report.id), "status": report.status}


# ---------- Yêu thích ----------
@router.get("/favorites")
def list_favorites(user: User = Depends(require_student), db: Session = Depends(get_db)):
    ids = db.scalars(select(Favorite.room_id).where(Favorite.user_id == user.id).order_by(Favorite.created_at.desc())).all()
    rooms = fetch_public_rooms(db, list(ids))
    return {"items": rooms, "page": 1, "page_size": len(rooms), "total": len(rooms)}


@router.put("/favorites/{room_id}")
def add_favorite(room_id: uuid.UUID, user: User = Depends(require_student), db: Session = Depends(get_db)):
    room = db.get(Room, room_id)
    if room is None or room.status != "published":
        raise not_found("Không tìm thấy phòng")
    if db.get(Favorite, {"user_id": user.id, "room_id": room_id}) is None:
        db.add(Favorite(user_id=user.id, room_id=room_id))
        db.commit()
    return {"room_id": str(room_id), "is_favorite": True}


@router.delete("/favorites/{room_id}")
def remove_favorite(room_id: uuid.UUID, user: User = Depends(require_student), db: Session = Depends(get_db)):
    fav = db.get(Favorite, {"user_id": user.id, "room_id": room_id})
    if fav is None:
        raise not_found("Phòng không có trong danh sách yêu thích")
    db.delete(fav)
    db.commit()
    return {"room_id": str(room_id), "is_favorite": False}
