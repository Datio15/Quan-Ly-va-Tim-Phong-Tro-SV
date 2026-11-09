#!/usr/bin/env python3
"""Sinh dữ liệu GIẢ cho hệ thống phòng trọ (chỉ dùng thư viện chuẩn).

    python3 seed/generate_seed.py --rooms 80 > seed/seed.sql
    psql -v ON_ERROR_STOP=1 -d phongtro -f seed/seed.sql

- Kết quả tái lập được: cùng --seed và --rooms luôn ra cùng dữ liệu, cùng UUID.
- Toàn bộ tên, số điện thoại (đầu 0000...), email (@example.com), CCCD, hợp đồng đều là giả.
- password_hash để giá trị không đăng nhập được; backend đặt mật khẩu demo từ biến
  môi trường SEED_DEMO_PASSWORD (xem SPEC.md mục 18).
- Tọa độ trường là gần đúng, chỉ để demo; nhóm chốt danh sách trường ngày 13/11.
"""
import argparse
import math
import random
import uuid
from datetime import date, datetime, timedelta, timezone

NS = uuid.UUID("6f1c2a52-6b7e-4c55-9a1e-3d0b5c1f2026")  # không gian tên cố định cho uuid5
UNSET_HASH = "!unset-run-backend-seed"

SCHOOLS = [
    # (tên, viết tắt, lat, lng) — tọa độ gần đúng, kiểm tra lại trên Azure Maps
    ("Đại học Quốc gia Hà Nội – 144 Xuân Thủy (ví dụ)", "DHQGHN", 21.0379, 105.7820),
    ("Đại học Bách khoa Hà Nội (ví dụ)", "BKHN", 21.0056, 105.8431),
]
AREAS = ["Cầu Giấy", "Mai Dịch", "Dịch Vọng", "Nghĩa Tân", "Cổ Nhuế", "Mỹ Đình"]
STREETS = ["Xuân Thủy", "Hồ Tùng Mậu", "Trần Quốc Hoàn", "Phạm Văn Đồng", "Nguyễn Phong Sắc",
           "Trần Đăng Ninh", "Duy Tân", "Tô Hiệu", "Hoàng Quốc Việt", "Phan Văn Trường"]
SURNAMES = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Đặng", "Bùi", "Đỗ", "Ngô"]
MIDDLE = ["Văn", "Thị", "Minh", "Đức", "Thu", "Hải", "Ngọc", "Quang"]
GIVEN = ["An", "Bình", "Châu", "Dũng", "Giang", "Hà", "Khánh", "Linh", "Nam", "Phương", "Quân", "Trang"]
AMENITY_CODES = ["gac_lung", "dieu_hoa", "nong_lanh", "ve_sinh_rieng", "cho_de_xe", "may_giat",
                 "tu_lanh", "bep_rieng", "ban_cong", "cua_so", "wifi", "thang_may", "camera",
                 "noi_that", "khong_chung_chu"]
ROOM_WORDS = ["Phòng trọ", "Phòng khép kín", "Phòng có gác lửng", "Căn hộ mini", "Phòng studio"]


def uid(*parts) -> str:
    return str(uuid.uuid5(NS, "/".join(str(p) for p in parts)))


def q(v) -> str:
    """Giá trị Python -> literal SQL."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (date, datetime)):
        return "'" + v.isoformat() + "'"
    if isinstance(v, list):
        return "ARRAY[" + ",".join(q(x) for x in v) + "]::text[]"
    return "'" + str(v).replace("'", "''") + "'"


def insert(table, cols, rows):
    if not rows:
        return ""
    vals = ",\n  ".join("(" + ", ".join(q(r[c]) for c in cols) + ")" for r in rows)
    return f"INSERT INTO {table} ({', '.join(cols)}) VALUES\n  {vals};\n\n"


def fake_name(rng):
    return f"{rng.choice(SURNAMES)} {rng.choice(MIDDLE)} {rng.choice(GIVEN)}"


def point_near(rng, lat, lng, max_km):
    """Điểm ngẫu nhiên trong bán kính max_km quanh (lat, lng)."""
    r = max_km * math.sqrt(rng.random())
    a = rng.random() * 2 * math.pi
    dlat = (r / 111.32) * math.cos(a)
    dlng = (r / (111.32 * math.cos(math.radians(lat)))) * math.sin(a)
    return round(lat + dlat, 6), round(lng + dlng, 6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rooms", type=int, default=80, help="số phòng (50-100 cho demo)")
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    out = ["-- Sinh bởi seed/generate_seed.py — DỮ LIỆU GIẢ, không chỉnh tay.\nBEGIN;\n\n"]

    # --- Trường ---
    schools = [{"id": uid("school", s[1]), "name": s[0], "short_name": s[1], "lat": s[2], "lng": s[3]}
               for s in SCHOOLS]
    out.append(insert("schools", ["id", "name", "short_name", "lat", "lng"], schools))

    # --- Người dùng: 1 quản trị, 4 chủ trọ, 6 sinh viên ---
    users = [{"id": uid("user", "admin"), "email": "admin@example.com", "full_name": "Quản Trị Viên",
              "phone": None, "role": "admin", "verified": True}]
    for i in range(1, 5):
        users.append({"id": uid("user", "landlord", i), "email": f"chutro{i}@example.com",
                      "full_name": fake_name(rng), "phone": f"0000000{100 + i}",
                      "role": "landlord", "verified": i <= 2})
    for i in range(1, 7):
        users.append({"id": uid("user", "student", i), "email": f"sinhvien{i}@example.com",
                      "full_name": fake_name(rng), "phone": f"0000000{200 + i}",
                      "role": "student", "verified": False})
    for u in users:
        u["password_hash"] = UNSET_HASH
    out.append(insert("users", ["id", "email", "password_hash", "full_name", "phone", "role", "verified"], users))
    landlords = [u for u in users if u["role"] == "landlord"]
    students = [u for u in users if u["role"] == "student"]

    # --- Nhà: mỗi nhà 4-8 phòng ---
    houses, rooms, room_amen, rates = [], [], [], []
    base = schools[0]
    h_idx = 0
    while len(rooms) < args.rooms:
        h_idx += 1
        lat, lng = point_near(rng, base["lat"], base["lng"], 3.5)
        street = rng.choice(STREETS)
        area = rng.choice(AREAS)
        house = {"id": uid("house", h_idx), "landlord_id": rng.choice(landlords)["id"],
                 "name": f"Nhà trọ số {h_idx}", "address_private": f"Số {rng.randint(1, 200)} ngõ {rng.randint(1, 150)} {street}",
                 "street": street, "ward": f"Phường {area}", "area": area, "city": "Hà Nội",
                 "lat": lat, "lng": lng}
        houses.append(house)
        for f in range(rng.randint(4, 8)):
            if len(rooms) >= args.rooms:
                break
            n = len(rooms) + 1
            area_m2 = round(rng.uniform(12, 35), 1)
            price = int(round((1_200_000 + area_m2 * 90_000 + rng.randint(-300_000, 500_000)) / 100_000) * 100_000)
            k = rng.random()
            status = "published" if k < 0.85 else ("pending" if k < 0.93 else ("draft" if k < 0.97 else "hidden"))
            curfew = None if rng.random() < 0.6 else rng.choice(["22:30", "23:00", "23:30"])
            kind = rng.choice(ROOM_WORDS)
            room = {"id": uid("room", n), "house_id": house["id"],
                    "title": f"{kind} {area_m2:g}m² gần {street}",
                    "description": f"{kind} tầng {f + 1}, {house['area']}. Dữ liệu giả phục vụ demo.",
                    "price_month": price, "deposit_amount": price, "area_m2": area_m2,
                    "floor": f + 1, "max_people": 1 if area_m2 < 15 else (2 if area_m2 < 25 else 3),
                    "curfew_time": curfew, "available_from": date(2026, 12, 1) if rng.random() < 0.3 else None,
                    "status": status,
                    "published_at": datetime(2026, 11, 1, tzinfo=timezone.utc) if status == "published" else None}
            rooms.append(room)
            # Tiện nghi: phòng đắt có nhiều hơn
            want = min(len(AMENITY_CODES), 3 + int((price - 1_500_000) / 600_000) + rng.randint(0, 2))
            for code in sorted(rng.sample(AMENITY_CODES, max(2, want))):
                room_amen.append({"room_id": room["id"], "amenity_code": code})
            per_person = rng.random() < 0.4
            rates.append({"room_id": room["id"], "electricity_per_kwh": rng.choice([3500, 3800, 4000]),
                          "water_mode": "per_person" if per_person else "per_m3",
                          "water_per_m3": 0 if per_person else rng.choice([25000, 30000, 35000]),
                          "water_per_person": rng.choice([80000, 100000, 120000]) if per_person else 0,
                          "internet_per_month": rng.choice([0, 50000, 100000]),
                          "parking_per_vehicle": rng.choice([0, 100000, 150000]),
                          "service_per_month": rng.choice([0, 30000, 50000])})

    out.append(insert("houses", ["id", "landlord_id", "name", "address_private", "street", "ward", "area",
                                 "city", "lat", "lng"], houses))
    out.append(insert("rooms", ["id", "house_id", "title", "description", "price_month", "deposit_amount",
                                "area_m2", "floor", "max_people", "curfew_time", "available_from", "status",
                                "published_at"], rooms))
    out.append(insert("room_amenities", ["room_id", "amenity_code"], room_amen))
    out.append(insert("cost_rates", ["room_id", "electricity_per_kwh", "water_mode", "water_per_m3",
                                     "water_per_person", "internet_per_month", "parking_per_vehicle",
                                     "service_per_month"], rates))

    published = [r for r in rooms if r["status"] == "published"]
    rate_of = {r["room_id"]: r for r in rates}

    # --- Đánh giá: khoảng 1/3 phòng công khai ---
    reviews = []
    for r in published:
        if rng.random() < 0.35:
            for s in rng.sample(students, rng.randint(1, 3)):
                reviews.append({"id": uid("review", r["id"], s["id"]), "room_id": r["id"], "student_id": s["id"],
                                "rating": rng.choice([3, 4, 4, 5, 5]),
                                "comment": rng.choice(["Phòng sạch, chủ dễ tính.", "Hơi ồn buổi tối.",
                                                       "Gần trường, đi bộ được.", "Giá hợp lý."])})
    out.append(insert("reviews", ["id", "room_id", "student_id", "rating", "comment"], reviews))

    # --- Lịch xem phòng: vài lịch trong tuần demo ---
    bookings = []
    for i, r in enumerate(rng.sample(published, min(8, len(published)))):
        slot = datetime(2026, 11, 20 + i % 6, 10 + (i % 4) * 2, 0, tzinfo=timezone.utc)
        bookings.append({"id": uid("booking", i), "room_id": r["id"], "student_id": students[i % len(students)]["id"],
                         "slot_start": slot, "status": rng.choice(["requested", "confirmed", "confirmed"]),
                         "student_note": "Em muốn xem phòng buổi chiều."})
    out.append(insert("bookings", ["id", "room_id", "student_id", "slot_start", "status", "student_note"], bookings))

    # --- Khách thuê, chỉ số công tơ, hóa đơn: 12 phòng đang có người ---
    tenants, readings, invoices = [], [], []
    rented = rng.sample(published, min(12, len(published)))
    periods = [date(2026, 9, 1), date(2026, 10, 1), date(2026, 11, 1)]
    inv_no = 0
    for i, r in enumerate(rented):
        t_id = uid("tenant", r["id"])
        people, vehicles = rng.randint(1, r["max_people"]), rng.randint(0, 2)
        tenants.append({"id": t_id, "room_id": r["id"], "full_name": fake_name(rng),
                        "phone": f"0000000{300 + i}", "email": f"khachthue{i + 1}@example.com",
                        "id_card_object_key": f"private/tenants/{t_id}/cccd-gia.jpg",
                        "contract_object_key": f"private/tenants/{t_id}/hop-dong-gia.pdf",
                        "start_date": date(2026, 9, 1),
                        "end_date": date(2026, 12, 15) if i < 3 else date(2027, 8, 31),  # 3 hợp đồng sắp hết hạn
                        "deposit_amount": r["price_month"], "people_count": people, "vehicle_count": vehicles})
        e_idx, w_idx = rng.randint(1000, 5000), rng.randint(100, 400)
        prev = None
        for p in periods:
            cur = (e_idx, w_idx)
            readings.append({"id": uid("reading", r["id"], p), "room_id": r["id"], "period": p,
                             "electricity_index": float(e_idx), "water_index": float(w_idx)})
            if prev is not None:
                rate = rate_of[r["id"]]
                e_used, w_used = cur[0] - prev[0], cur[1] - prev[1]
                water_amt = (rate["water_per_m3"] * w_used if rate["water_mode"] == "per_m3"
                             else rate["water_per_person"] * people)
                inv_no += 1
                bill_period = (p - timedelta(days=1)).replace(day=1)  # chỉ số đầu tháng này chốt hóa đơn tháng trước
                is_last = p == periods[-1]
                status = "unpaid" if is_last else "paid"
                if is_last and i % 4 == 0:
                    status = "overdue"
                invoices.append({"id": uid("invoice", r["id"], bill_period), "code": f"HD-{bill_period:%Y%m}-{inv_no:04d}",
                                 "tenant_id": t_id, "room_id": r["id"], "period": bill_period,
                                 "rent": r["price_month"], "electricity_used": float(e_used),
                                 "electricity_amount": rate["electricity_per_kwh"] * e_used,
                                 "water_used": float(w_used), "water_amount": water_amt,
                                 "internet_amount": rate["internet_per_month"],
                                 "parking_amount": rate["parking_per_vehicle"] * vehicles,
                                 "service_amount": rate["service_per_month"], "status": status,
                                 "due_date": p + timedelta(days=9),
                                 "paid_at": datetime(p.year, p.month, 5, tzinfo=timezone.utc) if status == "paid" else None})
            prev = cur
            e_idx += rng.randint(60, 160)
            w_idx += rng.randint(3, 8)
    out.append(insert("tenants", ["id", "room_id", "full_name", "phone", "email", "id_card_object_key",
                                  "contract_object_key", "start_date", "end_date", "deposit_amount",
                                  "people_count", "vehicle_count"], tenants))
    out.append(insert("meter_readings", ["id", "room_id", "period", "electricity_index", "water_index"], readings))
    out.append(insert("invoices", ["id", "code", "tenant_id", "room_id", "period", "rent", "electricity_used",
                                   "electricity_amount", "water_used", "water_amount", "internet_amount",
                                   "parking_amount", "service_amount", "status", "due_date", "paid_at"], invoices))

    # --- Hộp thư đi: mọi phòng công khai chờ đồng bộ lần đầu sang Azure ---
    out.append("INSERT INTO sync_outbox (entity_type, entity_id, entity_version, op)\n"
               "SELECT 'room', id, version, 'upsert' FROM rooms WHERE status = 'published' ORDER BY id;\n\n")
    out.append("COMMIT;\n")
    print("".join(out), end="")


if __name__ == "__main__":
    main()
