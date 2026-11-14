# EasyRent – Backend API (Người 2, FastAPI)

API `/api/v1` theo SPEC mục 10. Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL 16, MinIO, Azure AI Search.

## Chạy

```bash
cp .env.example .env            # ở thư mục gốc; điền DB_PASSWORD, MINIO_*, JWT_SECRET, SEED_DEMO_PASSWORD
docker compose up -d --build db minio api
curl http://localhost:8000/api/v1/health
```

- Swagger: http://localhost:8000/api/docs
- Lúc khởi động container tự chạy `python -m app.seed_passwords` (chờ CSDL, đặt mật khẩu demo cho tài khoản seed chưa có mật khẩu), sau đó chạy uvicorn.
- Đặt lại mật khẩu mọi tài khoản demo: `docker compose exec api python -m app.seed_passwords --all`

Chạy không dùng Docker (cần PostgreSQL + MinIO đang chạy):

```bash
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
set -a; . ../.env; set +a; export DB_HOST=localhost MINIO_ENDPOINT=localhost:9000
uvicorn app.main:app --reload
```

## Kiểm thử

```bash
docker compose exec api pytest -q        # 21 kiểm thử: TC01-TC12 + rate limit, upload ảnh, trạng thái hệ thống
```

`tests/test_search_filter.py` không cần CSDL (dịch tham số sang OData). `tests/test_api.py` gọi api thật với dữ liệu seed và tạo dữ liệu thử mới mỗi lần (nhà, phòng "Phòng thử nghiệm 20m²", tài khoản `sv-…@example.com`). Muốn sạch lại: `docker compose down && rm -rf data/postgres && docker compose up -d`.

## Cấu trúc

| Đường dẫn | Nội dung |
|---|---|
| `app/main.py` | Tạo app, middleware đo thời gian (`X-Response-Time-Ms`), gắn router |
| `app/config.py` | Biến môi trường (SPEC 15); giá trị `CHANGE_ME`/`SUFFIX` coi như chưa cấu hình |
| `app/models/` | Model SQLAlchemy ánh xạ `db/schema.sql` (không tự tạo bảng) |
| `app/schemas/` | Pydantic request |
| `app/routers/` | `auth` (đăng ký, đăng nhập, /me, Telegram link), `public` (config, schools, amenities), `rooms` (tìm kiếm, chi tiết, chi phí, so sánh, đánh giá, báo cáo, yêu thích), `bookings`, `landlord` (nhà, phòng, ảnh), `landlord_ops` (khách thuê, chỉ số, hóa đơn), `admin`, `health` |
| `app/services/search_service.py` | Azure AI Search (khóa chỉ đọc, `SEARCH_TIMEOUT_MS`) → lỗi/quá giờ thì `rooms_public.search_db` |
| `app/services/outbox.py` | Tăng `rooms.version` + ghi `sync_outbox` cùng transaction (SPEC 9.2) |
| `app/services/cost.py` | Chi phí thực tế bằng hàm `room_monthly_cost()` |
| `app/services/invoices.py` | Tạo hóa đơn tháng (SPEC 9.8) |

## Bảng đối chiếu chức năng

| Mã | Đã làm |
|---|---|
| F01 | Đăng ký `student`/`landlord`, đăng nhập JWT (argon2), 3 vai trò, giới hạn 10 lần đăng nhập/phút/IP |
| F02, F03 | CRUD nhà/phòng/bảng giá/tiện nghi, tải ảnh JPEG/PNG ≤ 5 MB (kiểm tra chữ ký file, tối đa 10, tên do server sinh), gửi duyệt, duyệt/từ chối (kèm chọn ảnh đạt), ẩn/hiện |
| F04, F11 | `/search/rooms` đủ tham số mục 10.3, header `X-Search-Source: azure|db`, đếm `search_fallback_count` |
| F06, F07 | `/rooms/compare` (kèm `best`), `/rooms/{id}/cost` |
| F08 | Đặt lịch (≥ 2 giờ, ≤ 14 ngày, tối đa 3 lịch chờ, trùng giờ → `BOOKING_CONFLICT`), xác nhận/từ chối/hủy/đã xem |
| F09 | Yêu thích, đánh giá (cần lịch `done`), báo cáo, quản trị ẩn đánh giá (ghi outbox) |
| F10 (phần api) | Ghi outbox ở mọi thay đổi ảnh hưởng tài liệu công khai; `/admin/sync/resync` |
| F12 (phần api) | `POST /me/telegram-link` sinh mã 16 ký tự, hạn 15 phút |
| F13, F14 | `/admin/backup/run`, `/admin/backup/restore-test` tạo `job_runs` queued; `/admin/system/status`, `/admin/jobs/{id}` |
| F16, F17 | Khách thuê, file CCCD/hợp đồng GIẢ vào bucket `private` (URL ký trước 5 phút), chỉ số, hóa đơn (`INVOICE_EXISTS`), đánh dấu đã trả |

**Chưa làm (thuộc worker, Người 2 + 6):** đọc outbox gửi sang Azure, kéo hàng đợi `ops-ticks`, `getUpdates` Telegram, chạy `backup.sh`/`restore-test.sh` cho dòng `job_runs` queued. Trước khi có worker, dòng outbox nằm ở `pending` và việc sao lưu bấm từ giao diện ở trạng thái `queued`.

## Đề xuất bổ sung SPEC (cần nhóm duyệt)

Theo quy ước mục 0, các điểm dưới đây chưa có trong SPEC v0.3, đã code sẵn nhưng cần ghi vào SPEC:

1. `GET /api/v1/images/{image_id}`: phục vụ ảnh phòng từ MinIO `public-src` khi ảnh chưa có `public_url` trên Blob (MinIO chỉ mở cho sg-app nên trình duyệt không truy cập trực tiếp được). Không trả ảnh bị từ chối.
2. `GET /landlord/tenants/{id}/files/{id_card|contract}` trả URL ký trước 5 phút dạng `/api/v1/files/signed?token=…` (api đọc MinIO rồi trả file), vì URL ký trước của MinIO trỏ vào IP nội bộ.
3. `GET /landlord/meter-readings?room_id=` (xem lại chỉ số đã nhập) và `GET /admin/landlords` (danh sách để xác minh).
4. `GET /admin/rooms` thêm `pending_images=true` để duyệt ảnh mới của phòng đang công khai; `POST /admin/rooms/{id}/approve` dùng được cho phòng `published` (chỉ duyệt ảnh), `reject` dùng được để gỡ phòng `published`.
5. `POST /admin/reports/{id}/resolve` body `{"action": "resolve"|"dismiss", "hide_review": bool}`.
6. Lịch `confirmed`: sinh viên thấy `room.address` (số nhà, ngõ) và tên/số điện thoại chủ trọ để đến xem; chủ trọ thấy tên/số điện thoại sinh viên. Dữ liệu này không rời OpenStack.
7. Biến môi trường mới: `CORS_ORIGINS` (mặc định trống vì web và api cùng nguồn qua nginx), `REVIEW_SKIP_BOOKING_CHECK` (cờ demo của mục 9.4), `FORWARDED_ALLOW_IPS` (mạng tin cậy cho header `X-Forwarded-For`, mặc định dải nội bộ).
8. Mã lỗi thêm: `RATE_LIMITED` (429), `INTERNAL_ERROR` (500).
9. Gửi duyệt yêu cầu nhà đã có tọa độ (để tìm theo khoảng cách và bản đồ hoạt động).
