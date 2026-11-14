# EasyRent – Những điều cần lưu ý (Backend + Frontend)

Ghi chú cho người tiếp nhận phần Backend (`backend/`) và Frontend (`frontend/`) viết ngày 12/11/2026 theo SPEC v0.3.

---

## 1. Code đang nằm ở đâu

| Thư mục | Là gì |
|---|---|
| `Cloud Project/` (thư mục này) | Nơi viết Backend + Frontend. **Không phải repo git.** Có kèm bản chép các file chung của nhóm (schema, seed, scripts, infra, SPEC) để chạy được độc lập. |
| `../Quan-Ly-va-Tim-Phong-Tro-SV/` | Repo git thật của nhóm (`github.com/Datio15/Quan-Ly-va-Tim-Phong-Tro-SV`). **Chưa được sửa gì.** |

**Muốn đưa code lên repo nhóm**, chép sang repo:

- `backend/Dockerfile`, `backend/.dockerignore`, `backend/requirements.txt`, `backend/README.md`, `backend/app/`, `backend/tests/`
  (giữ nguyên `backend/db/schema.sql` của repo)
- toàn bộ `frontend/` (trừ `node_modules/`, `dist/` nếu có)
- `docker-compose.yml` (đã bật `api` và `web`)
- đoạn sửa trong `README.md` (mục "Bắt đầu trong 5 phút" và bảng "Có gì trong kho")

Làm theo quy ước nhóm (SPEC mục 20): tạo nhánh `feature/api-...` và `feature/web-...`, mở pull request, nhờ một người xem trước khi gộp vào `main`.

> ⚠️ **Không chép file `.env`** lên repo. File này chứa mật khẩu và đã bị `.gitignore` chặn.

---

## 2. Cách chạy

### Chạy ở cổng mặc định

```bash
cd "D:/Documents/Tài Liệu Đại Học/Điện toán đám mây/Cloud Project"
docker compose up -d --build
```

| Dịch vụ | Địa chỉ |
|---|---|
| Web | http://localhost |
| API (Swagger) | http://localhost:8000/api/docs |
| MinIO console | http://localhost:9001 |
| PostgreSQL | localhost:5432 |

Kiểm thử: `docker compose exec api pytest -q` (21 kiểm thử, gồm TC01–TC12).

### Tài khoản demo

Mật khẩu chung lấy từ `SEED_DEMO_PASSWORD` trong `.env` (ở máy này là `Demo@12345`).

- Quản trị: `admin@example.com`
- Chủ trọ: `chutro1@example.com` … `chutro4@example.com` (chutro1, 2 đã xác minh)
- Sinh viên: `sinhvien1@example.com` … `sinhvien6@example.com`

Mật khẩu demo được tự đặt khi container `api` khởi động. Muốn đặt lại cho tất cả tài khoản demo: `docker compose exec api python -m app.seed_passwords --all`.

---

## 3. Đụng cổng với stack của repo nhóm ⚠️

Repo nhóm cũng có `docker compose` chạy `db` và `minio` ở cổng **5432** và **9000**. Docker Desktop tự bật lại stack đó mỗi lần khởi động, nên chạy `docker compose up` ở đây sẽ báo lỗi `port is already allocated`.

Cách xử lý (chọn một):

1. Tắt stack của repo nhóm trước:
   ```bash
   docker stop quan-ly-va-tim-phong-tro-sv-db-1 quan-ly-va-tim-phong-tro-sv-minio-1
   ```
2. Hoặc sửa cổng bên trái trong `docker-compose.yml`, ví dụ `"15432:5432"`, `"19000:9000"`, `"8088:80"`.

Cổng **80** cũng có thể đã bị chương trình khác (IIS, Skype, XAMPP…) chiếm. Khi đó đổi `"80:80"` thành `"8080:80"`.

**Stack thử nghiệm đang chạy:** lúc viết code, tôi chạy một stack tên `cloudproject` ở các cổng 8088 / 18000 / 15432 / 19000. Muốn tắt:

```bash
docker compose -p cloudproject down
```

---

## 4. Những gì CHƯA làm

| Phần | Tình trạng | Hệ quả khi chạy |
|---|---|---|
| **Worker** (`worker/`, Người 2 + 6) | Chưa viết | `sync_outbox` nằm mãi ở `pending` (trang Hệ thống hiện 65 dòng chờ). Bấm "Sao lưu ngay" / "Khôi phục thử" thì việc chỉ ở trạng thái `queued`. Không có nhắc lịch Telegram. Liên kết Telegram sinh được link nhưng chưa ai khớp mã. |
| **Azure Functions** `ingest-room`, `daily-ticks` (Người 5) | Chưa viết | Chưa có tin nào lên Azure AI Search. |
| **Kết nối Azure thật** | Chưa thử | Tìm kiếm luôn dùng CSDL (huy hiệu "Dự phòng CSDL"). Bản đồ hiện "Chưa cấu hình Azure Maps". Code gọi Azure Search / Maps đã viết nhưng **chưa được kiểm tra với dịch vụ thật**. |
| **Application Insights** | Có code, chưa thử | Chỉ bật khi có `APPLICATIONINSIGHTS_CONNECTION_STRING`. |
| **Alembic** | Chưa dựng | `schema.sql` vẫn là nguồn duy nhất. Đổi CSDL về sau thì dựng Alembic. |
| **Chạy trên VM OpenStack** | Chưa thử | Theo "Định nghĩa xong" (SPEC 20), phải chạy được trên VM thật mới tính là xong. |

### Khi có khóa Azure

Điền vào `.env` rồi chạy `docker compose up -d` để nạp lại cấu hình:

```
AZURE_SEARCH_ENDPOINT=https://srch-phongtro-<SUFFIX>.search.windows.net
AZURE_SEARCH_INDEX=rooms-public
AZURE_SEARCH_QUERY_KEY=<khóa CHỈ ĐỌC, không dùng khóa admin>
AZURE_MAPS_KEY=<khóa riêng cho Maps>
AZURE_BLOB_PUBLIC_BASE_URL=https://stphongtro<SUFFIX>.blob.core.windows.net/public-images
```

Kiểm tra: tìm phòng trên web phải thấy huy hiệu **"Azure AI Search"**, hoặc gọi `curl -I "http://localhost/api/v1/search/rooms"` thấy `X-Search-Source: azure`. Lưu ý: chỉ mục chỉ có dữ liệu sau khi worker và Function `ingest-room` đã chạy.

---

## 5. Những điểm mình tự thêm, chưa có trong SPEC ⚠️

SPEC mục 0 quy định: **muốn đổi hay thêm API thì sửa SPEC trước, báo cả nhóm**. Các điểm dưới đây đã code sẵn, cần nhóm trưởng (Người 1) duyệt và ghi vào SPEC trước khi gộp. Chi tiết ở cuối `backend/README.md`.

1. `GET /api/v1/images/{image_id}`: phục vụ ảnh phòng từ MinIO khi ảnh chưa được đẩy lên Blob.
2. `GET /landlord/tenants/{id}/files/{id_card|contract}`: trả URL ký trước 5 phút dạng `/api/v1/files/signed?token=...`.
3. `GET /landlord/meter-readings?room_id=` và `GET /admin/landlords`.
4. `GET /admin/rooms?pending_images=true`. Ngoài ra `approve` dùng được cho phòng đang `published` (để duyệt ảnh mới), `reject` dùng được để gỡ phòng đang `published`.
5. Body của `POST /admin/reports/{id}/resolve`: `{"action": "resolve"|"dismiss", "hide_review": bool}`.
6. Khi lịch xem đã **xác nhận**, sinh viên thấy số nhà, ngõ và số điện thoại chủ trọ. Dữ liệu này không rời OpenStack.
7. Biến môi trường mới: `CORS_ORIGINS`, `REVIEW_SKIP_BOOKING_CHECK`, `FORWARDED_ALLOW_IPS`. Cần thêm vào `.env.example` và SPEC mục 15.
8. Mã lỗi mới: `RATE_LIMITED` (429), `INTERNAL_ERROR` (500).
9. Phải có tọa độ nhà thì mới gửi duyệt phòng được.

---

## 6. Lưu ý về bảo mật

- **Không commit `.env`.** Không dán khóa, mật khẩu, token vào chat với AI (SPEC mục 0, 19).
- Trên VM thật, **tạo lại** `JWT_SECRET` (`openssl rand -hex 32`), `DB_PASSWORD`, `MINIO_ROOT_PASSWORD`, `SEED_DEMO_PASSWORD`. Không dùng lại giá trị của máy cá nhân.
- **Không mở cổng 8000 ra ngoài trên VM.** `sg-app` chỉ mở 80/443, mọi request phải đi qua nginx. Lý do: api tin header `X-Forwarded-For` từ các dải IP nội bộ, và nginx ghi đè header này. Nếu api bị truy cập thẳng, người dùng có thể giả IP để vượt giới hạn đăng nhập.
- Giới hạn đăng nhập (10 lần/phút/IP) nằm **trong bộ nhớ** của tiến trình api. Vì vậy api chạy `--workers 1`; tăng số worker thì giới hạn tính riêng cho từng worker.
- Chỉ dùng **khóa truy vấn (chỉ đọc)** của AI Search cho api. Khóa admin chỉ để ở Function (Key Vault).
- `AZURE_MAPS_KEY` sẽ lộ ra trình duyệt qua `/api/v1/config`, nên dùng khóa riêng chỉ cho Maps.
- Che khóa, token, mật khẩu khi chụp màn hình hoặc quay video báo cáo.

---

## 7. Lưu ý về dữ liệu và kiểm thử

- `pytest` **tạo thêm dữ liệu** mỗi lần chạy: nhà "Nhà thử nghiệm", phòng "Phòng thử nghiệm 20m²", tài khoản `sv-...@example.com`, đặt lịch, đánh giá. Ngoài ra nó để lại một dòng `job_runs` sao lưu ở trạng thái `queued`.
  → **Trước khi demo hoặc quay video, nạp lại dữ liệu sạch:**
  ```bash
  docker compose down
  rm -rf data/postgres data/minio
  docker compose up -d
  ```
- Không có lệnh làm sạch riêng: TC11 sửa thẳng CSDL để giả lập lịch đã xem (`status='done'`).
- Dữ liệu seed không có ảnh phòng, nên các thẻ phòng hiện biểu tượng 🏠. Muốn có ảnh cho demo, đăng nhập chủ trọ → sửa phòng → tải ảnh → đăng nhập quản trị → duyệt. Ảnh phải tự chụp hoặc có giấy phép dùng lại (SPEC 18).
- Seed có sẵn hóa đơn tháng 9 và 10/2026. Tạo lại hóa đơn tháng 10 sẽ báo `INVOICE_EXISTS` (đúng TC12).
- Đánh giá yêu cầu lịch xem ở trạng thái **"Đã xem"**, mà chủ trọ chỉ đánh dấu được sau giờ hẹn. Để demo nhanh, đặt `REVIEW_SKIP_BOOKING_CHECK=true` trong `.env`.

---

## 8. Khi gặp lỗi

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `port is already allocated` | Stack repo nhóm hoặc chương trình khác chiếm cổng | Xem mục 3 |
| `failed to connect to the docker API` | Docker Desktop chưa chạy | Mở Docker Desktop, đợi biểu tượng chuyển xanh |
| api log lặp "Đang chờ CSDL..." | db chưa sẵn sàng hoặc sai `DB_HOST`/mật khẩu | Đợi 30 giây. Trên vm-app, `DB_HOST` phải là IP nội bộ của vm-data |
| Đăng nhập báo sai mật khẩu với tài khoản demo | Seed nạp trước khi đặt `SEED_DEMO_PASSWORD` | `docker compose exec api python -m app.seed_passwords --all` |
| Đổi `DB_PASSWORD` xong db không vào được | PostgreSQL chỉ đọc mật khẩu ở lần khởi tạo đầu tiên | Xóa `data/postgres` để khởi tạo lại (mất dữ liệu) |
| Sửa code xong không thấy thay đổi | Image chưa được build lại | `docker compose up -d --build api web` |
| Web trắng hoặc lỗi 502 ở `/api` | Container api chưa chạy | `docker compose logs api --tail 50` |
| Bản đồ báo "Chưa cấu hình Azure Maps" | Thiếu `AZURE_MAPS_KEY` | Điền khóa vào `.env` rồi chạy `docker compose up -d api` |

---

## 9. Việc nên làm tiếp (theo thứ tự)

1. Nhờ nhóm trưởng duyệt các đề xuất ở mục 5 và cập nhật SPEC.
2. Đưa `backend/` và `frontend/` lên repo nhóm qua pull request.
3. Viết **worker** (outbox → `ingest-room`, kéo hàng đợi `ops-ticks`, Telegram `getUpdates`, chạy `backup.sh`/`restore-test.sh`), cần cho TC13–TC18 và TC20–TC21.
4. Người 5 xong Function `ingest-room`, rồi thử TC13: duyệt một phòng → phải tìm thấy trên Azure trong vòng 15 giây.
5. Triển khai lên VM OpenStack (`vm-app`: `api`, `web`, `worker`; `vm-data`: `db`, `minio`), thử TC19.
6. Chụp màn hình vào `docs/` cho báo cáo.
