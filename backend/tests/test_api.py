"""Kiểm thử tích hợp TC01-TC12 (SPEC 22) trên api đang chạy với dữ liệu seed.

Chạy trong container api:
    docker compose exec api pytest -q
Biến môi trường: API_BASE (mặc định http://localhost:8000/api/v1), SEED_DEMO_PASSWORD, DB_* (đọc outbox).
Mỗi lần chạy tạo tài khoản/nhà/phòng mới nên chạy lại được nhiều lần.
"""
import io
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import text

BASE = os.environ.get("API_BASE", "http://localhost:8000/api/v1")
PW = os.environ.get("SEED_DEMO_PASSWORD", "")
VN = timezone(timedelta(hours=7))

pytestmark = pytest.mark.skipif(len(PW) < 8, reason="Cần SEED_DEMO_PASSWORD và api đang chạy")


@pytest.fixture(scope="session")
def http():
    with httpx.Client(base_url=BASE, timeout=20) as c:
        try:
            c.get("/health")
        except httpx.HTTPError:
            pytest.skip("api không chạy")
        yield c


def login(http, email, password=None):
    # Mỗi lần đăng nhập giả một IP riêng (api tin X-Forwarded-For từ 127.0.0.1) để không chạm giới hạn 10 lần/phút.
    fake_ip = f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
    r = http.post("/auth/login", json={"email": email, "password": password or PW}, headers={"X-Forwarded-For": fake_ip})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def fake_ip() -> dict:
    return {"X-Forwarded-For": f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"}


def png_bytes(size=(8, 8), tail: bytes = b"") -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, (200, 120, 40)).save(buf, format="PNG")
    return buf.getvalue() + tail


def upload_image(http, headers, room_id, data: bytes | None = None):
    return http.post(f"/landlord/rooms/{room_id}/images", headers=headers,
                     files={"file": ("a.png", data or png_bytes(), "image/png")})


def new_student(http):
    email = f"sv-{uuid.uuid4().hex[:10]}@example.com"
    r = http.post("/auth/register", json={"email": email, "password": "matkhau123", "full_name": "Sinh Viên Thử",
                                         "phone": "0000000999", "role": "student"}, headers=fake_ip())
    assert r.status_code == 201, r.text
    return login(http, email, "matkhau123")


@pytest.fixture(scope="session")
def admin(http):
    return login(http, "admin@example.com")


@pytest.fixture(scope="session")
def landlord1(http):
    return login(http, "chutro1@example.com")


@pytest.fixture(scope="session")
def landlord2(http):
    return login(http, "chutro2@example.com")


@pytest.fixture(scope="session")
def db():
    from app.db import engine

    with engine.connect() as conn:
        yield conn


def outbox_count(db, room_id) -> int:
    return db.execute(text("SELECT count(*) FROM sync_outbox WHERE entity_id = :id"), {"id": room_id}).scalar_one()


@pytest.fixture(scope="session")
def published_room(http, landlord1, admin, db):
    """TC04 dùng chung: chủ trọ 1 tạo nhà + phòng, gửi duyệt, quản trị duyệt."""
    house = http.post("/landlord/houses", headers=landlord1, json={
        "name": "Nhà thử nghiệm", "address_private": "Số 1 ngõ 2 Xuân Thủy", "street": "Xuân Thủy",
        "ward": "Phường Dịch Vọng", "area": "Cầu Giấy", "city": "Hà Nội", "lat": 21.0381, "lng": 105.7830}).json()
    r = http.post("/landlord/rooms", headers=landlord1, json={
        "house_id": house["id"], "title": "Phòng thử nghiệm 20m²", "description": "Dữ liệu giả cho kiểm thử",
        "price_month": 3000000, "deposit_amount": 3000000, "area_m2": 20, "floor": 3, "max_people": 2,
        "curfew_time": None, "available_from": "2026-12-01", "amenities": ["dieu_hoa", "nong_lanh", "ve_sinh_rieng"],
        "cost_rates": {"electricity_per_kwh": 3800, "water_mode": "per_m3", "water_per_m3": 30000, "water_per_person": 0,
                       "internet_per_month": 50000, "parking_per_vehicle": 100000, "service_per_month": 30000}})
    assert r.status_code == 201, r.text
    room = r.json()
    assert room["status"] == "draft" and room["version"] == 1
    v0, ob0 = room["version"], outbox_count(db, room["id"])

    assert upload_image(http, landlord1, room["id"]).status_code == 201  # BE-09: gửi duyệt cần ít nhất 1 ảnh
    r = http.post(f"/landlord/rooms/{room['id']}/submit", headers=landlord1)
    assert r.status_code == 200 and r.json()["status"] == "pending"
    r = http.post(f"/admin/rooms/{room['id']}/approve", headers=admin, json={})
    assert r.status_code == 200, r.text
    approved = r.json()
    assert approved["status"] == "published"
    assert approved["version"] > v0
    assert outbox_count(db, room["id"]) == ob0 + 1
    op = db.execute(text("SELECT op FROM sync_outbox WHERE entity_id = :id ORDER BY id DESC LIMIT 1"), {"id": room["id"]}).scalar_one()
    assert op == "upsert"
    return approved


def test_tc01_register_login_me(http):
    email = f"tc01-{uuid.uuid4().hex[:8]}@example.com"
    r = http.post("/auth/register", json={"email": email, "password": "matkhau123", "full_name": "Nguyễn Văn A",
                                         "phone": "0000000999", "role": "student"}, headers=fake_ip())
    assert r.status_code == 201 and r.json()["role"] == "student"
    assert http.post("/auth/register", json={"email": email.upper(), "password": "matkhau123", "full_name": "B B",
                                            "role": "student"}, headers=fake_ip()).json()["error"]["code"] == "EMAIL_TAKEN"
    h = login(http, email, "matkhau123")
    r = http.get("/me", headers=h)
    assert r.status_code == 200 and r.json()["role"] == "student" and r.json()["email"] == email


def test_tc02_student_forbidden_on_landlord_api(http):
    h = login(http, "sinhvien1@example.com")
    r = http.get("/landlord/rooms", headers=h)
    assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"
    assert http.get("/landlord/rooms").status_code == 401


def test_tc03_other_landlord_room_is_404(http, landlord1, landlord2):
    rooms = http.get("/landlord/rooms", headers=landlord1).json()["items"]
    assert rooms
    r = http.get(f"/landlord/rooms/{rooms[0]['id']}", headers=landlord2)
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_landlord_houses_list(http, landlord1, landlord2):
    """GET /landlord/houses không được 500 (GROUP BY + quan hệ joined) và chỉ trả nhà của chính chủ."""
    r1 = http.get("/landlord/houses", headers=landlord1)
    assert r1.status_code == 200, r1.text
    houses1 = r1.json()
    assert houses1 and all("room_count" in h for h in houses1)
    r2 = http.get("/landlord/houses", headers=landlord2)
    assert r2.status_code == 200, r2.text
    assert not ({h["id"] for h in houses1} & {h["id"] for h in r2.json()})


def test_tc04_publish_flow(published_room):
    assert published_room["status"] == "published"


def test_tc05_search_price_and_amenity(http):
    r = http.get("/search/rooms", params={"price_max": 3000000, "amenities": "dieu_hoa", "page_size": 50})
    assert r.status_code == 200
    assert r.headers["X-Search-Source"] in ("azure", "db")
    items = r.json()["items"]
    assert items
    for it in items:
        assert it["price_month"] <= 3000000 and "dieu_hoa" in it["amenities"]


def test_tc06_search_distance_sorted(http):
    school = http.get("/schools").json()[0]
    r = http.get("/search/rooms", params={"school_id": school["id"], "max_distance_m": 1500, "sort": "distance_asc", "page_size": 50})
    assert r.status_code == 200
    d = [it["distance_m"] for it in r.json()["items"]]
    assert all(x <= 1500 for x in d)
    assert d == sorted(d)
    assert http.get("/search/rooms", params={"sort": "distance_asc"}).status_code == 422


def test_tc07_cost_matches_manual(http, published_room):
    r = http.get(f"/rooms/{published_room['id']}/cost", params={"kwh": 120, "m3": 5, "people": 2, "vehicles": 1})
    assert r.status_code == 200
    body = r.json()
    manual = 3000000 + 3800 * 120 + 30000 * 5 + 50000 + 100000 * 1 + 30000
    assert body["total"] == manual
    assert sum(line["amount"] for line in body["lines"]) == manual
    assert [line["code"] for line in body["lines"]] == ["rent", "electricity", "water", "internet", "parking", "service"]


def test_tc08_compare_three(http):
    items = http.get("/search/rooms", params={"page_size": 3, "sort": "price_asc"}).json()["items"]
    school = http.get("/schools").json()[0]
    ids = [it["id"] for it in items[:3]]
    r = http.post("/rooms/compare", json={"ids": ids, "school_id": school["id"]})
    assert r.status_code == 200, r.text
    body = r.json()
    rooms = body["rooms"]
    assert len(rooms) == 3
    for key in ("price_month", "est_monthly_cost", "area_m2", "distance_m", "amenities", "curfew", "rating_avg", "landlord_verified"):
        assert key in rooms[0]
    assert body["best"]["price_month"] == min(rooms, key=lambda x: x["price_month"])["id"]
    assert body["best"]["area_m2"] == max(rooms, key=lambda x: x["area_m2"])["id"]
    assert body["best"]["distance_m"] == min(rooms, key=lambda x: x["distance_m"])["id"]


_used_slots: set = set()


def _slot(days=3) -> str:
    """Giờ hẹn ngẫu nhiên không trùng trong một lần chạy (phòng thử nghiệm được tạo mới mỗi lần)."""
    base = (datetime.now(VN) + timedelta(days=days)).replace(hour=7, minute=0, second=0, microsecond=0)
    while True:
        slot = base + timedelta(minutes=15 * random.randint(0, 55))  # mốc 15 phút, 07:00-20:45 (BE-08)
        if slot not in _used_slots:
            _used_slots.add(slot)
            return slot.isoformat()


def test_tc09_booking_conflict(http, published_room):
    s1, s2 = new_student(http), new_student(http)
    slot = _slot()
    r1 = http.post("/bookings", headers=s1, json={"room_id": published_room["id"], "slot_start": slot})
    assert r1.status_code == 201, r1.text
    r2 = http.post("/bookings", headers=s2, json={"room_id": published_room["id"], "slot_start": slot})
    assert r2.status_code == 409 and r2.json()["error"]["code"] == "BOOKING_CONFLICT"


def test_tc10_booking_time_rules(http, published_room):
    s = new_student(http)
    past = (datetime.now(VN) - timedelta(hours=1)).isoformat()
    far = (datetime.now(VN) + timedelta(days=15)).isoformat()
    soon = (datetime.now(VN) + timedelta(minutes=30)).isoformat()
    for slot in (past, far, soon):
        r = http.post("/bookings", headers=s, json={"room_id": published_room["id"], "slot_start": slot})
        assert r.status_code == 422, (slot, r.text)


def test_booking_limit_and_landlord_flow(http, published_room, landlord1):
    s = new_student(http)
    ids = []
    for d in (2, 3, 4):
        r = http.post("/bookings", headers=s, json={"room_id": published_room["id"], "slot_start": _slot(d)})
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    r = http.post("/bookings", headers=s, json={"room_id": published_room["id"], "slot_start": _slot(5)})
    assert r.status_code == 409 and r.json()["error"]["code"] == "BOOKING_LIMIT"
    assert http.post(f"/bookings/{ids[0]}/confirm", headers=landlord1).json()["status"] == "confirmed"
    assert http.post(f"/bookings/{ids[1]}/decline", headers=landlord1).json()["status"] == "declined"
    assert http.post(f"/bookings/{ids[2]}/cancel", headers=s).json()["status"] == "cancelled"
    r = http.post(f"/bookings/{ids[1]}/confirm", headers=landlord1)
    assert r.status_code == 409 and r.json()["error"]["code"] == "INVALID_TRANSITION"
    mine = http.get("/bookings", headers=s).json()
    assert mine["total"] == 3
    confirmed = [b for b in mine["items"] if b["status"] == "confirmed"][0]
    assert "address" in confirmed["room"]


def test_tc11_review_then_hide(http, published_room, admin, db):
    s = new_student(http)
    r = http.post("/bookings", headers=s, json={"room_id": published_room["id"], "slot_start": _slot(6)})
    booking_id = r.json()["id"]
    room_id = published_room["id"]
    assert http.put(f"/rooms/{room_id}/review", headers=s, json={"rating": 2, "comment": "Thử"}).status_code == 403
    # Giả lập đã xem phòng xong (không chờ được đến giờ hẹn trong kiểm thử)
    db.execute(text("UPDATE bookings SET status = 'done' WHERE id = :id"), {"id": booking_id})
    db.commit()
    s2 = new_student(http)
    r = http.post("/bookings", headers=s2, json={"room_id": room_id, "slot_start": _slot(7)})
    db.execute(text("UPDATE bookings SET status = 'done' WHERE id = :id"), {"id": r.json()["id"]})
    db.commit()

    r = http.put(f"/rooms/{room_id}/review", headers=s, json={"rating": 1, "comment": "Đánh giá sai sự thật"})
    assert r.status_code == 200, r.text
    review_id = r.json()["id"]
    assert http.put(f"/rooms/{room_id}/review", headers=s2, json={"rating": 5, "comment": "Tốt"}).status_code == 200
    assert http.get(f"/rooms/{room_id}").json()["rating_avg"] == 3.0

    rep = http.post("/reports", headers=s2, json={"target_type": "review", "target_id": review_id, "reason": "Đánh giá sai"})
    assert rep.status_code == 201
    ob0 = outbox_count(db, room_id)
    r = http.post(f"/admin/reports/{rep.json()['id']}/resolve", headers=admin, json={"action": "resolve", "hide_review": True})
    assert r.status_code == 200, r.text
    detail = http.get(f"/rooms/{room_id}").json()
    assert detail["rating_avg"] == 5.0 and detail["rating_count"] == 1
    db.commit()  # làm mới snapshot
    assert outbox_count(db, room_id) == ob0 + 1


def test_tc12_invoice_twice(http, landlord1, published_room):
    room_id = published_room["id"]
    # Năm ngẫu nhiên trong quá khứ (phòng tạo mới mỗi lần nên không đụng lần chạy trước; BE-05 cấm kỳ ở tương lai xa)
    year = random.randint(2001, 2024)
    r = http.post("/landlord/tenants", headers=landlord1, json={
        "room_id": room_id, "full_name": "Khách Thuê Giả", "phone": "0000000777", "start_date": f"{year}-09-01",
        "end_date": f"{year + 1}-08-31", "deposit_amount": 3000000, "people_count": 2, "vehicle_count": 1})
    assert r.status_code == 201, r.text
    for month, e, w in ((f"{year}-10", 1000.0, 50.0), (f"{year}-11", 1120.5, 55.0)):
        r = http.post("/landlord/meter-readings", headers=landlord1,
                      json={"room_id": room_id, "month": month, "electricity_index": e, "water_index": w})
        assert r.status_code == 201, r.text
    r = http.post("/landlord/invoices/generate", headers=landlord1, json={"month": f"{year}-10"})
    assert r.status_code == 201, r.text
    mine = [i for i in r.json()["created"] if i["room_id"] == room_id]
    assert len(mine) == 1
    inv = mine[0]
    assert inv["electricity_used"] == 120.5
    assert inv["electricity_amount"] == round(120.5 * 3800)
    assert inv["water_amount"] == 5 * 30000
    assert inv["parking_amount"] == 100000
    assert inv["code"].startswith(f"HD-{year}10-")
    assert inv["due_date"] == f"{year}-11-10"
    r = http.post("/landlord/invoices/generate", headers=landlord1, json={"month": f"{year}-10"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "INVOICE_EXISTS"
    paid = http.post(f"/landlord/invoices/{inv['id']}/paid", headers=landlord1)
    assert paid.status_code == 200 and paid.json()["status"] == "paid"


def test_login_rate_limit(http):
    ip = {"X-Forwarded-For": f"10.250.{random.randint(0, 255)}.{random.randint(1, 254)}"}
    codes = [http.post("/auth/login", json={"email": "khongco@example.com", "password": "x"}, headers=ip).status_code
             for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_admin_status_and_jobs(http, admin):
    r = http.get("/admin/system/status", headers=admin)
    assert r.status_code == 200
    body = r.json()
    for key in ("db", "minio", "azure_search_reachable", "outbox", "queue", "backup", "restore_test", "search_fallback_last_hour"):
        assert key in body
    job = http.post("/admin/backup/run", headers=admin)
    assert job.status_code == 202
    assert http.get(f"/admin/jobs/{job.json()['job_run_id']}", headers=admin).json()["job"] == "backup"


def test_image_upload_and_validation(http, landlord1, published_room):
    r = upload_image(http, landlord1, published_room["id"])
    assert r.status_code == 201, r.text
    assert r.json()["moderation"] == "pending"
    # BE-10: chữ ký đầu file đúng nhưng nội dung không phải ảnh hợp lệ
    for bad in (b"not an image", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, b"\xff\xd8\xff" + b"garbage" * 10):
        assert upload_image(http, landlord1, published_room["id"], bad).status_code == 422


# ---------- Báo cáo QA 18/11: BE-01, BE-02 ----------
def _room_body(house_id: str, **over) -> dict:
    body = {"house_id": house_id, "title": "Phòng kiểm thử biên", "price_month": 3000000, "area_m2": 20,
            "cost_rates": {"electricity_per_kwh": 3500}}
    body.update(over)
    return body


def test_be02_edge_inputs_return_422_not_500(http, landlord1, published_room):
    """Đầu vào hợp lệ về kiểu nhưng vượt giới hạn cột/ngày tháng: phải 422, không bao giờ 500."""
    house_id, room_id = published_room["house"]["id"], published_room["id"]
    student = new_student(http)
    big = 3_000_000_000
    cases = [
        ("POST", "/landlord/rooms", landlord1, _room_body(house_id, price_month=big)),
        ("POST", "/landlord/rooms", landlord1, _room_body(house_id, deposit_amount=big)),
        ("POST", "/landlord/rooms", landlord1, _room_body(house_id, cost_rates={"electricity_per_kwh": big})),
        ("POST", "/landlord/rooms", landlord1, _room_body(house_id, area_m2=99999.99)),
        ("POST", "/landlord/rooms", landlord1, _room_body(house_id, area_m2=0.04)),
        ("POST", "/landlord/rooms", landlord1, _room_body(house_id, area_m2=20.55)),
        ("POST", "/landlord/rooms", landlord1, _room_body(house_id, available_from="0001-01-01")),
        ("POST", "/landlord/tenants", landlord1, {"room_id": room_id, "full_name": "Khách Biên", "start_date": "2026-11-01", "deposit_amount": big}),
        ("POST", "/landlord/tenants", landlord1, {"room_id": room_id, "full_name": "Khách Biên", "start_date": "0001-01-01"}),
        ("POST", "/landlord/meter-readings", landlord1, {"room_id": room_id, "month": "2026-11", "electricity_index": 1e12, "water_index": 1}),
        ("POST", "/landlord/meter-readings", landlord1, {"room_id": room_id, "month": "2026-11", "electricity_index": 100.04, "water_index": 1}),
        ("POST", "/bookings", student, {"room_id": room_id, "slot_start": "0001-01-01T00:00:00+07:00"}),
        ("POST", "/landlord/invoices/generate", landlord1, {"month": "9999-12"}),
        ("GET", "/landlord/invoices?month=0000-01", landlord1, None),
    ]
    for method, path, headers, body in cases:
        r = http.request(method, path, headers=headers, json=body)
        assert r.status_code == 422, (path, body, r.status_code, r.text)
    # 1e999 trong JSON được đọc thành vô cực
    raw = '{"room_id": "%s", "month": "2026-11", "electricity_index": 1e999, "water_index": 1}' % room_id
    r = http.post("/landlord/meter-readings", headers={**landlord1, "Content-Type": "application/json"}, content=raw)
    assert r.status_code == 422, r.text


def test_be01_max_cost_rates_do_not_break_search(http, landlord1, admin, published_room):
    """Phòng công khai có bảng giá ở mức tối đa cho phép: chi phí, chi tiết, so sánh, tìm kiếm vẫn 200."""
    rates = {"electricity_per_kwh": 100_000, "water_mode": "per_m3", "water_per_m3": 1_000_000,
             "internet_per_month": 10_000_000, "parking_per_vehicle": 10_000_000, "service_per_month": 10_000_000}
    r = http.post("/landlord/rooms", headers=landlord1,
                  json=_room_body(published_room["house"]["id"], price_month=100_000_000, cost_rates=rates))
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    assert upload_image(http, landlord1, rid).status_code == 201
    assert http.post(f"/landlord/rooms/{rid}/submit", headers=landlord1).status_code == 200
    assert http.post(f"/admin/rooms/{rid}/approve", headers=admin, json={}).status_code == 200
    try:
        cost = http.get(f"/rooms/{rid}/cost", params={"kwh": 10000, "m3": 1000, "people": 20, "vehicles": 20})
        assert cost.status_code == 200, cost.text  # trước đây tràn int4 -> 500
        assert cost.json()["total"] == 2_147_483_647  # tổng thật > giới hạn integer nên được kẹp
        assert http.get(f"/rooms/{rid}").status_code == 200
        assert http.get("/search/rooms", params={"sort": "price_desc"}).status_code == 200
        assert http.post("/rooms/compare", json={"ids": [rid, published_room["id"]]}).status_code == 200
    finally:
        http.post(f"/landlord/rooms/{rid}/hide", headers=landlord1)


# ---------- Báo cáo QA 18/11: các lỗi còn lại (nhánh fix/qa-bao-cao-18-11) ----------
def _new_room(http, landlord, house_id, publish_with=None, **over) -> str:
    r = http.post("/landlord/rooms", headers=landlord, json=_room_body(house_id, **over))
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    if publish_with is not None:
        assert upload_image(http, landlord, rid).status_code == 201
        assert http.post(f"/landlord/rooms/{rid}/submit", headers=landlord).status_code == 200
        assert http.post(f"/admin/rooms/{rid}/approve", headers=publish_with, json={}).status_code == 200
    return rid


def test_be03_one_active_tenant_per_room(http, landlord1, published_room):
    rid = _new_room(http, landlord1, published_room["house"]["id"], max_people=2)
    base = {"room_id": rid, "full_name": "Khách Một", "start_date": "2026-09-01"}
    r = http.post("/landlord/tenants", headers=landlord1, json={**base, "people_count": 3})
    assert r.status_code == 422, r.text  # vượt sức chứa
    t1 = http.post("/landlord/tenants", headers=landlord1, json=base)
    assert t1.status_code == 201, t1.text
    r = http.post("/landlord/tenants", headers=landlord1, json={**base, "full_name": "Khách Hai"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "TENANT_EXISTS"
    assert http.post("/landlord/tenants", headers=landlord1, json={**base, "email": "khong-hop-le"}).status_code == 422
    # Kết thúc hợp đồng cũ thì thêm được khách mới; bật lại hợp đồng cũ thì bị chặn
    assert http.patch(f"/landlord/tenants/{t1.json()['id']}", headers=landlord1, json={"is_active": False}).status_code == 200
    t2 = http.post("/landlord/tenants", headers=landlord1, json={**base, "full_name": "Khách Hai"})
    assert t2.status_code == 201, t2.text
    r = http.patch(f"/landlord/tenants/{t1.json()['id']}", headers=landlord1, json={"is_active": True})
    assert r.status_code == 409


def test_be04_be05_invoice_void_and_meter_rules(http, landlord1, published_room):
    rid = _new_room(http, landlord1, published_room["house"]["id"])
    year = random.randint(2001, 2024)
    t = http.post("/landlord/tenants", headers=landlord1, json={
        "room_id": rid, "full_name": "Khách Hủy", "start_date": f"{year}-01-01", "end_date": f"{year}-06-30"})
    assert t.status_code == 201, t.text

    def reading(month, e, w):
        return http.post("/landlord/meter-readings", headers=landlord1,
                         json={"room_id": rid, "month": month, "electricity_index": e, "water_index": w})

    assert reading(f"{year}-03", 100, 10).status_code == 201
    assert reading(f"{year}-04", 150, 12).status_code == 201
    assert reading(f"{year}-05", 90, 12).status_code == 422          # nhỏ hơn kỳ trước
    assert reading(f"{year}-02", 120, 5).status_code == 422          # lớn hơn kỳ sau
    assert reading("2099-01", 1, 1).status_code == 422               # tương lai xa
    r = http.post("/landlord/invoices/generate", headers=landlord1, json={"month": f"{year}-03"})
    inv = [i for i in r.json()["created"] if i["room_id"] == rid][0]
    v = http.post(f"/landlord/invoices/{inv['id']}/void", headers=landlord1)
    assert v.status_code == 200 and v.json()["status"] == "void"
    assert http.post(f"/landlord/invoices/{inv['id']}/void", headers=landlord1).status_code == 409
    r = http.post("/landlord/invoices/generate", headers=landlord1, json={"month": f"{year}-03"})
    assert r.status_code == 201 and [i for i in r.json()["created"] if i["room_id"] == rid], r.text  # tạo lại được
    # Hợp đồng kết thúc 30/6: tháng 8 không còn hóa đơn
    assert reading(f"{year}-08", 300, 20).status_code == 201
    assert reading(f"{year}-09", 350, 22).status_code == 201
    r = http.post("/landlord/invoices/generate", headers=landlord1, json={"month": f"{year}-08"})
    assert not [i for i in r.json().get("created", []) if i["room_id"] == rid]


def test_be06_successful_logins_not_limited(http):
    ip = fake_ip()
    codes = [http.post("/auth/login", json={"email": "sinhvien1@example.com", "password": PW}, headers=ip).status_code
             for _ in range(12)]
    assert codes == [200] * 12


def test_be07_register_validation(http):
    base = {"password": "matkhau123", "full_name": "Người Thử", "role": "student"}
    sfx = uuid.uuid4().hex[:8]
    for email in ("a@b.c", "x@y..z", f"qa..{sfx}@example.com", f".qa{sfx}@example.com"):
        assert http.post("/auth/register", json={**base, "email": email}, headers=fake_ip()).status_code == 422, email
    weak = http.post("/auth/register", json={**base, "email": f"w{sfx}@example.com", "password": "aaaaaaaa"}, headers=fake_ip())
    assert weak.status_code == 422
    html = http.post("/auth/register", json={**base, "email": f"h{sfx}@example.com", "full_name": "<script>x</script>"},
                     headers=fake_ip())
    assert html.status_code == 422
    # Mật khẩu có khoảng trắng hai đầu được giữ nguyên
    email = f"sp{sfx}@example.com"
    r = http.post("/auth/register", json={**base, "email": email, "password": "  matkhau123 "}, headers=fake_ip())
    assert r.status_code == 201, r.text
    assert http.post("/auth/login", json={"email": email, "password": "  matkhau123 "}, headers=fake_ip()).status_code == 200
    assert http.post("/auth/login", json={"email": email, "password": "matkhau123"}, headers=fake_ip()).status_code == 401


def test_be08_booking_slot_rules(http, published_room):
    s = new_student(http)
    day = (datetime.now(VN) + timedelta(days=9)).replace(second=0, microsecond=0)
    room = published_room["id"]
    for bad in (day.replace(hour=10, minute=7), day.replace(hour=3, minute=0), day.replace(hour=21, minute=15),
                day.replace(hour=10, minute=0, second=13)):
        r = http.post("/bookings", headers=s, json={"room_id": room, "slot_start": bad.isoformat()})
        assert r.status_code == 422, (bad, r.text)
    ok = http.post("/bookings", headers=s, json={"room_id": room, "slot_start": day.replace(hour=10, minute=0).isoformat(),
                                                 "student_note": "Đi cùng bạn"})
    assert ok.status_code == 201, ok.text
    other = next(i["id"] for i in http.get("/search/rooms", params={"page_size": 5}).json()["items"] if i["id"] != room)
    r = http.post("/bookings", headers=s, json={"room_id": other, "slot_start": day.replace(hour=10, minute=30).isoformat()})
    assert r.status_code == 409 and r.json()["error"]["code"] == "BOOKING_CONFLICT"
    c = http.post(f"/bookings/{ok.json()['id']}/cancel", headers=s, json={"note": "bận đột xuất"})
    assert c.status_code == 200 and "bận đột xuất" in c.json()["student_note"] and "Đi cùng bạn" in c.json()["student_note"]


def test_be09_publish_requires_image(http, landlord1, admin, published_room):
    rid = _new_room(http, landlord1, published_room["house"]["id"])
    r = http.post(f"/landlord/rooms/{rid}/submit", headers=landlord1)
    assert r.status_code == 422, r.text
    assert upload_image(http, landlord1, rid).status_code == 201
    assert http.post(f"/landlord/rooms/{rid}/submit", headers=landlord1).status_code == 200
    r = http.post(f"/admin/rooms/{rid}/approve", headers=admin, json={"image_ids_ok": []})
    assert r.status_code == 422, r.text  # loại hết ảnh thì không được công khai
    assert http.post(f"/admin/rooms/{rid}/approve", headers=admin, json={}).json()["status"] == "published"
    v = http.get(f"/landlord/rooms/{rid}", headers=landlord1).json()["version"]
    # Duyệt ảnh khi không có ảnh chờ: không tăng version
    assert http.post(f"/admin/rooms/{rid}/approve", headers=admin, json={}).json()["version"] == v
    http.post(f"/landlord/rooms/{rid}/hide", headers=landlord1)


def test_be10_image_access_and_reencode(http, landlord1, published_room):
    up = upload_image(http, landlord1, published_room["id"], png_bytes(tail=b"<script>alert(1)</script>"))
    assert up.status_code == 201, up.text
    img = up.json()
    # Ảnh chờ duyệt: ẩn danh không xem được; URL ký (trang chủ trọ) thì được, và ảnh đã được mã hóa lại sạch
    assert http.get(f"/images/{img['id']}").status_code == 404
    signed = http.get(img["url"].removeprefix("/api/v1"))
    assert signed.status_code == 200 and b"<script>" not in signed.content
    assert signed.headers.get("x-content-type-options") == "nosniff"
    assert http.get(f"/images/{img['id']}", params={"t": "sai"}).status_code == 401


def test_be12_search_unaccent_and_facets(http, published_room):
    if http.get("/search/rooms", params={"page_size": 1}).headers.get("X-Search-Source") == "azure":
        # Ca này kiểm tra tìm kiếm dự phòng CSDL. Qua Azure: analyzer vi.microsoft không bỏ dấu, và phòng thử
        # nghiệm chỉ vào chỉ mục khi worker + Function ingest-room đã chạy.
        pytest.skip("Đang dùng Azure AI Search; ca này chỉ áp cho tìm kiếm dự phòng CSDL")
    r = http.get("/search/rooms", params={"q": "xuan thuy"})  # phòng thử nghiệm ở đường Xuân Thủy
    assert r.status_code == 200 and r.json()["total"] >= 1
    assert http.get("/search/rooms", params={"q": "Xuân   Thủy cầu giấy"}).json()["total"] >= 1
    assert http.get("/search/rooms", params={"price_min": 5_000_000, "price_max": 1_000_000}).status_code == 422
    facets = http.get("/search/rooms").json()["facets"]
    assert facets["area"] and facets["amenities"] and {"value", "count"} <= set(facets["area"][0])


def test_be13_be14_report_dedupe_and_timezone(http, published_room, admin):
    s = new_student(http)
    body = {"target_type": "room", "target_id": published_room["id"], "reason": "Thông tin sai"}
    r1 = http.post("/reports", headers=s, json=body)
    r2 = http.post("/reports", headers=s, json=body)
    assert r1.status_code == 201 and r2.status_code == 200 and r1.json()["id"] == r2.json()["id"]
    res = http.post(f"/admin/reports/{r1.json()['id']}/resolve", headers=admin, json={"action": "dismiss"})
    assert res.status_code == 200 and res.json()["resolved_at"].endswith("+07:00")


def test_be15_house_coordinates(http, landlord1, published_room):
    house = {"name": "Nhà nửa tọa độ", "address_private": "1", "street": "A", "ward": "B", "area": "C"}
    assert http.post("/landlord/houses", headers=landlord1, json={**house, "lat": 21.0}).status_code == 422
    r = http.patch(f"/landlord/houses/{published_room['house']['id']}", headers=landlord1, json={"lat": None, "lng": None})
    assert r.status_code == 422  # nhà đang có phòng hiển thị


def test_compare_reports_missing_rooms(http, published_room):
    ids = [i["id"] for i in http.get("/search/rooms", params={"page_size": 2}).json()["items"]]
    r = http.post("/rooms/compare", json={"ids": ids + [str(uuid.uuid4())]})
    assert r.status_code == 200 and len(r.json()["missing"]) == 1
    r = http.post("/rooms/compare", json={"ids": [ids[0], str(uuid.uuid4())]})
    assert r.status_code == 404 and len(r.json()["error"]["details"]["missing"]) == 1
