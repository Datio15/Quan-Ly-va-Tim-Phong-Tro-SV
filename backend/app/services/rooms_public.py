"""Đọc bản công khai của phòng từ `v_rooms_public` (nguồn duy nhất, SPEC 8) và tìm kiếm dự phòng (F11)."""
import math
import uuid
from dataclasses import dataclass, field

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import Text as SAText
from sqlalchemy.orm import Session

from ..config import get_settings
from .cost import CostInputs

settings = get_settings()

SORTS = {"relevance", "price_asc", "price_desc", "cost_asc", "distance_asc", "rating_desc", "newest"}


@dataclass
class SearchParams:
    q: str | None = None
    price_min: int | None = None
    price_max: int | None = None
    cost_max: int | None = None
    area_min: float | None = None
    areas: list[str] = field(default_factory=list)
    amenities: list[str] = field(default_factory=list)
    no_curfew: bool = False
    people: int | None = None
    school_lat: float | None = None
    school_lng: float | None = None
    max_distance_m: int | None = None
    verified_only: bool = False
    sort: str = "relevance"
    page: int = 1
    page_size: int = 20

    @property
    def has_school(self) -> bool:
        return self.school_lat is not None and self.school_lng is not None


def image_url(image_id: uuid.UUID | str | None, public_url: str | None) -> str | None:
    """Ảnh đã đồng bộ thì dùng URL Blob; chưa đồng bộ thì phục vụ qua api (đề xuất bổ sung SPEC)."""
    if public_url:
        return public_url
    if image_id:
        return f"/api/v1/images/{image_id}"
    return None


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    """Cùng công thức với hàm distance_m() trong CSDL."""
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)))


_BASE_SELECT = """
SELECT v.id, v.title, v.description, v.price_month, v.deposit_amount, v.area_m2, v.max_people, v.floor,
       v.curfew, v.curfew_time, v.available_from, v.street, v.ward, v.area, v.city, v.lat, v.lng,
       v.amenities, v.rating_avg, v.rating_count, v.landlord_verified, v.version, v.updated_at,
       c.total AS est_monthly_cost,
       th.id AS thumb_id, th.public_url AS thumb_public_url
       {distance_col}
       {count_col}
FROM v_rooms_public v
CROSS JOIN LATERAL room_monthly_cost(v.id, CAST(:kwh AS numeric), CAST(:m3 AS numeric), CAST(:people_est AS integer), CAST(:vehicles AS integer)) c
LEFT JOIN LATERAL (
    SELECT ri.id, ri.public_url FROM room_images ri
    WHERE ri.room_id = v.id AND ri.moderation = 'ok'
    ORDER BY ri.position, ri.created_at LIMIT 1
) th ON true
WHERE v.status = 'published' {where}
"""


def _row_to_item(row) -> dict:
    item = {
        "id": str(row["id"]),
        "title": row["title"],
        "description": row["description"],
        "price_month": row["price_month"],
        "est_monthly_cost": row["est_monthly_cost"],
        "deposit_amount": row["deposit_amount"],
        "area_m2": row["area_m2"],
        "max_people": row["max_people"],
        "floor": row["floor"],
        "area": row["area"],
        "ward": row["ward"],
        "street": row["street"],
        "city": row["city"],
        "lat": row["lat"],
        "lng": row["lng"],
        "distance_m": row.get("distance_m"),
        "amenities": list(row["amenities"] or []),
        "curfew": row["curfew"],
        "curfew_time": row["curfew_time"].strftime("%H:%M") if row["curfew_time"] else None,
        "available_from": row["available_from"].isoformat() if row["available_from"] else None,
        "rating_avg": row["rating_avg"],
        "rating_count": row["rating_count"],
        "landlord_verified": row["landlord_verified"],
        "thumbnail_url": image_url(row["thumb_id"], row["thumb_public_url"]),
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }
    return item


def _cost_params() -> dict:
    d = CostInputs.defaults()
    return {"kwh": d.kwh, "m3": d.m3, "people_est": d.people, "vehicles": d.vehicles}


def fetch_public_rooms(db: Session, ids: list[uuid.UUID], school: tuple[float, float] | None = None) -> list[dict]:
    """Lấy các phòng đang công khai theo danh sách id (giữ thứ tự đầu vào)."""
    if not ids:
        return []
    params: dict = {"ids": ids, **_cost_params()}
    distance_col = ""
    if school:
        distance_col = ", CASE WHEN v.lat IS NULL THEN NULL ELSE distance_m(:slat, :slng, v.lat, v.lng) END AS distance_m"
        params.update(slat=school[0], slng=school[1])
    sql = text(_BASE_SELECT.format(distance_col=distance_col, count_col="", where="AND v.id = ANY(:ids)"))
    rows = db.execute(sql, params).mappings().all()
    by_id = {r["id"]: _row_to_item(r) for r in rows}
    return [by_id[i] for i in ids if i in by_id]


def search_db(db: Session, p: SearchParams) -> dict:
    """Tìm kiếm dự phòng trên PostgreSQL, cùng bộ lọc với Azure (SPEC 11.3)."""
    where: list[str] = []
    params: dict = {**_cost_params()}
    binds = []

    if p.q:
        where.append(
            "(v.title ILIKE :q OR v.description ILIKE :q OR v.street ILIKE :q OR v.ward ILIKE :q OR v.area ILIKE :q)"
        )
        params["q"] = f"%{p.q.replace('%', r'\%').replace('_', r'\_')}%"
    if p.price_min is not None:
        where.append("v.price_month >= :price_min")
        params["price_min"] = p.price_min
    if p.price_max is not None:
        where.append("v.price_month <= :price_max")
        params["price_max"] = p.price_max
    if p.cost_max is not None:
        where.append("c.total <= :cost_max")
        params["cost_max"] = p.cost_max
    if p.area_min is not None:
        where.append("v.area_m2 >= :area_min")
        params["area_min"] = p.area_min
    if p.areas:
        where.append("v.area = ANY(:areas)")
        params["areas"] = p.areas
        binds.append(bindparam("areas", type_=ARRAY(SAText)))
    if p.amenities:
        where.append("v.amenities @> :amen")
        params["amen"] = p.amenities
        binds.append(bindparam("amen", type_=ARRAY(SAText)))
    if p.no_curfew:
        where.append("NOT v.curfew")
    if p.people is not None:
        where.append("v.max_people >= :people")
        params["people"] = p.people
    if p.verified_only:
        where.append("v.landlord_verified")

    distance_col = ""
    if p.has_school:
        distance_col = ", CASE WHEN v.lat IS NULL THEN NULL ELSE distance_m(:slat, :slng, v.lat, v.lng) END AS distance_m"
        params.update(slat=p.school_lat, slng=p.school_lng)
        if p.max_distance_m is not None:
            where.append("v.lat IS NOT NULL AND distance_m(:slat, :slng, v.lat, v.lng) <= :maxd")
            params["maxd"] = p.max_distance_m

    order = {
        "relevance": "v.updated_at DESC",
        "newest": "v.updated_at DESC",
        "price_asc": "v.price_month ASC",
        "price_desc": "v.price_month DESC",
        "cost_asc": "c.total ASC",
        "rating_desc": "v.rating_avg DESC NULLS LAST, v.rating_count DESC",
        "distance_asc": "distance_m ASC NULLS LAST" if p.has_school else "v.updated_at DESC",
    }[p.sort]

    sql = _BASE_SELECT.format(
        distance_col=distance_col,
        count_col=", count(*) OVER () AS _total",
        where="".join(f" AND {w}" for w in where),
    ) + f" ORDER BY {order}, v.id LIMIT :limit OFFSET :offset"
    params.update(limit=p.page_size, offset=(p.page - 1) * p.page_size)

    stmt = text(sql)
    if binds:
        stmt = stmt.bindparams(*binds)
    rows = db.execute(stmt, params).mappings().all()
    total = rows[0]["_total"] if rows else 0
    if not rows and p.page > 1:
        # trang vượt quá: vẫn cần tổng số
        count_sql = _BASE_SELECT.format(distance_col=distance_col, count_col="", where="".join(f" AND {w}" for w in where))
        cstmt = text(f"SELECT count(*) FROM ({count_sql}) s")
        if binds:
            cstmt = cstmt.bindparams(*binds)
        total = db.execute(cstmt, params).scalar_one()
    return {
        "items": [_row_to_item(r) for r in rows],
        "page": p.page,
        "page_size": p.page_size,
        "total": total,
        "facets": {"area": [], "amenities": []},
    }
