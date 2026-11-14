"""Kiểm thử tích hợp TC01-TC12 (SPEC 22) trên api đang chạy với dữ liệu seed.

Chạy trong container api:
    docker compose exec api pytest -q
Biến môi trường: API_BASE (mặc định http://localhost:8000/api/v1), SEED_DEMO_PASSWORD, DB_* (đọc outbox).
Mỗi lần chạy tạo tài khoản/nhà/phòng mới nên chạy lại được nhiều lần.
"""
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


def new_student(http):
    email = f"sv-{uuid.uuid4().hex[:10]}@example.com"
    r = http.post("/auth/register", json={"email": email, "password": "matkhau123", "full_name": "Sinh Viên Thử",
                                         "phone": "0000000999", "role": "student"})
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
                                         "phone": "0000000999", "role": "student"})
    assert r.status_code == 201 and r.json()["role"] == "student"
    assert http.post("/auth/register", json={"email": email.upper(), "password": "matkhau123", "full_name": "B B",
                                            "role": "student"}).json()["error"]["code"] == "EMAIL_TAKEN"
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
        slot = base + timedelta(minutes=5 * random.randint(0, 160))
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
    r = http.post("/landlord/tenants", headers=landlord1, json={
        "room_id": room_id, "full_name": "Khách Thuê Giả", "phone": "0000000777", "start_date": "2026-09-01",
        "end_date": "2027-08-31", "deposit_amount": 3000000, "people_count": 2, "vehicle_count": 1})
    assert r.status_code == 201, r.text
    # Tháng ngẫu nhiên trong tương lai xa để không đụng hóa đơn của các lần chạy trước
    year = random.randint(2030, 2090)
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
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    r = http.post(f"/landlord/rooms/{published_room['id']}/images", headers=landlord1,
                  files={"file": ("a.png", png, "image/png")})
    assert r.status_code == 201, r.text
    assert r.json()["moderation"] == "pending"
    r = http.post(f"/landlord/rooms/{published_room['id']}/images", headers=landlord1,
                  files={"file": ("a.png", b"not an image", "image/png")})
    assert r.status_code == 422
