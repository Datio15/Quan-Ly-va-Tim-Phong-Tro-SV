"""Tìm phòng: Azure AI Search trước, lỗi hoặc quá giờ thì rơi về PostgreSQL (SPEC 3B, 11.3, F11)."""
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from functools import lru_cache

from sqlalchemy.orm import Session

from ..config import get_settings
from . import metrics
from .rooms_public import SearchParams, haversine_m, search_db

log = logging.getLogger(__name__)
settings = get_settings()
_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="azsearch")

SELECT_FIELDS = [
    "id", "title", "description", "price_month", "est_monthly_cost", "deposit_amount", "area_m2", "max_people",
    "floor", "street", "ward", "area", "city", "location", "amenities", "curfew", "curfew_time", "available_from",
    "landlord_verified", "rating_avg", "rating_count", "image_urls", "updated_at",
]


def odata_str(value: str) -> str:
    """Chuỗi OData bao bằng nháy đơn; nháy đơn trong giá trị phải nhân đôi."""
    return "'" + value.replace("'", "''") + "'"


def build_filter(p: SearchParams) -> str | None:
    parts: list[str] = []
    if p.price_min is not None:
        parts.append(f"price_month ge {int(p.price_min)}")
    if p.price_max is not None:
        parts.append(f"price_month le {int(p.price_max)}")
    if p.cost_max is not None:
        parts.append(f"est_monthly_cost le {int(p.cost_max)}")
    if p.area_min is not None:
        parts.append(f"area_m2 ge {float(p.area_min)}")
    if p.areas:
        joined = "|".join(a.replace("|", " ") for a in p.areas)
        parts.append(f"search.in(area, {odata_str(joined)}, '|')")
    for code in p.amenities:
        parts.append(f"amenities/any(a: a eq {odata_str(code)})")
    if p.no_curfew:
        parts.append("curfew eq false")
    if p.people is not None:
        parts.append(f"max_people ge {int(p.people)}")
    if p.has_school and p.max_distance_m is not None:
        km = p.max_distance_m / 1000
        parts.append(f"geo.distance(location, {_point(p)}) le {km}")
    if p.verified_only:
        parts.append("landlord_verified eq true")
    return " and ".join(parts) if parts else None


def _point(p: SearchParams) -> str:
    # Trong POINT(...) kinh độ đứng trước vĩ độ.
    return f"geography'POINT({float(p.school_lng)} {float(p.school_lat)})'"


def build_order_by(p: SearchParams) -> list[str] | None:
    if p.sort == "distance_asc" and p.has_school:
        return [f"geo.distance(location, {_point(p)}) asc"]
    return {
        "price_asc": ["price_month asc"],
        "price_desc": ["price_month desc"],
        "cost_asc": ["est_monthly_cost asc"],
        "rating_desc": ["rating_avg desc"],
        "newest": ["updated_at desc"],
    }.get(p.sort)


@lru_cache
def _client():
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    timeout_s = max(settings.search_timeout_ms / 1000, 0.5)
    return SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index,
        credential=AzureKeyCredential(settings.azure_search_query_key),
        retry_total=0,
        connection_timeout=timeout_s,
        read_timeout=timeout_s,
    )


def _doc_to_item(doc: dict, p: SearchParams) -> dict:
    loc = doc.get("location") or {}
    coords = loc.get("coordinates") if isinstance(loc, dict) else None
    lng, lat = (coords[0], coords[1]) if coords else (None, None)
    distance = None
    if p.has_school and lat is not None:
        distance = haversine_m(p.school_lat, p.school_lng, lat, lng)
    images = doc.get("image_urls") or []
    avail = doc.get("available_from")
    return {
        "id": doc["id"],
        "title": doc.get("title"),
        "description": doc.get("description"),
        "price_month": doc.get("price_month"),
        "est_monthly_cost": doc.get("est_monthly_cost"),
        "deposit_amount": doc.get("deposit_amount"),
        "area_m2": doc.get("area_m2"),
        "max_people": doc.get("max_people"),
        "floor": doc.get("floor"),
        "area": doc.get("area"),
        "ward": doc.get("ward"),
        "street": doc.get("street"),
        "city": doc.get("city"),
        "lat": lat,
        "lng": lng,
        "distance_m": distance,
        "amenities": doc.get("amenities") or [],
        "curfew": doc.get("curfew"),
        "curfew_time": doc.get("curfew_time"),
        "available_from": avail[:10] if isinstance(avail, str) else avail,
        "rating_avg": doc.get("rating_avg"),
        "rating_count": doc.get("rating_count"),
        "landlord_verified": doc.get("landlord_verified"),
        "thumbnail_url": images[0] if images else None,
        "updated_at": doc.get("updated_at"),
    }


def _search_azure(p: SearchParams) -> dict:
    results = _client().search(
        search_text=p.q or "*",
        search_fields=["title", "description", "street", "ward", "area"] if p.q else None,
        filter=build_filter(p),
        order_by=build_order_by(p),
        facets=["area,count:10", "amenities,count:20"],
        include_total_count=True,
        select=SELECT_FIELDS,
        skip=(p.page - 1) * p.page_size,
        top=p.page_size,
    )
    items = [_doc_to_item(doc, p) for doc in results]
    facets_raw = results.get_facets() or {}
    total = results.get_count() or 0
    facets = {
        name: [{"value": f.get("value"), "count": f.get("count")} for f in facets_raw.get(name, [])]
        for name in ("area", "amenities")
    }
    return {"items": items, "page": p.page, "page_size": p.page_size, "total": total, "facets": facets}


def search_rooms(db: Session, p: SearchParams) -> tuple[dict, str]:
    """Trả (kết quả, nguồn) với nguồn là 'azure' hoặc 'db'."""
    if settings.azure_search_enabled:
        started = time.monotonic()
        future = _pool.submit(_search_azure, p)
        try:
            return future.result(timeout=settings.search_timeout_ms / 1000), "azure"
        except FutureTimeout:
            future.cancel()
            reason = "timeout"
        except Exception as exc:
            reason = type(exc).__name__
        log.warning("Azure AI Search lỗi (%s) sau %d ms, dùng tìm kiếm dự phòng", reason, (time.monotonic() - started) * 1000)
        metrics.record_search_fallback(reason)
    return search_db(db, p), "db"


_reach_cache: dict = {"at": 0.0, "ok": False}


def azure_reachable() -> bool:
    """Dùng cho trang trạng thái; lưu đệm 30 giây."""
    if not settings.azure_search_enabled:
        return False
    if time.monotonic() - _reach_cache["at"] < 30:
        return _reach_cache["ok"]

    def _probe() -> bool:
        res = _client().search(search_text="*", top=1, include_total_count=True, select=["id"])
        res.get_count()
        return True

    try:
        ok = _pool.submit(_probe).result(timeout=settings.search_timeout_ms / 1000)
    except Exception:
        ok = False
    _reach_cache.update(at=time.monotonic(), ok=ok)
    return ok
