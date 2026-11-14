"""Kiểm thử đơn vị (không cần CSDL): dịch tham số tìm kiếm sang OData (SPEC 11.3)."""
from app.services.rooms_public import SearchParams, haversine_m
from app.services.search_service import build_filter, build_order_by, odata_str


def test_odata_quote_escaping():
    assert odata_str("O'Brien") == "'O''Brien'"


def test_filter_full():
    p = SearchParams(
        price_min=1_000_000, price_max=3_500_000, cost_max=4_000_000, area_min=15,
        areas=["Cầu Giấy", "Mai Dịch"], amenities=["dieu_hoa", "wifi"], no_curfew=True, people=2,
        school_lat=21.0379, school_lng=105.782, max_distance_m=2000, verified_only=True,
    )
    f = build_filter(p)
    assert "price_month ge 1000000" in f
    assert "price_month le 3500000" in f
    assert "est_monthly_cost le 4000000" in f
    assert "area_m2 ge 15.0" in f
    assert "search.in(area, 'Cầu Giấy|Mai Dịch', '|')" in f
    assert "amenities/any(a: a eq 'dieu_hoa') and amenities/any(a: a eq 'wifi')" in f
    assert "curfew eq false" in f
    assert "max_people ge 2" in f
    # kinh độ trước vĩ độ, đơn vị km
    assert "geo.distance(location, geography'POINT(105.782 21.0379)') le 2.0" in f
    assert "landlord_verified eq true" in f


def test_filter_empty():
    assert build_filter(SearchParams()) is None


def test_order_by():
    assert build_order_by(SearchParams(sort="price_asc")) == ["price_month asc"]
    assert build_order_by(SearchParams(sort="relevance")) is None
    p = SearchParams(sort="distance_asc", school_lat=21.0, school_lng=105.8)
    assert build_order_by(p) == ["geo.distance(location, geography'POINT(105.8 21.0)') asc"]


def test_haversine_matches_known_distance():
    # ĐHQGHN -> ĐHBKHN khoảng 7 km
    d = haversine_m(21.0379, 105.782, 21.0056, 105.8431)
    assert 6500 < d < 7500
