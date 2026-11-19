# Báo cáo kiểm thử EasyRent (Backend + Frontend)

- Ngày kiểm thử: 18/11/2026
- Phiên bản: nhánh `main`, commit `998f5fe`, API v0.3.0
- Môi trường: stack Docker chạy cục bộ (db, api, web/nginx, worker; MinIO dùng bản trong compose). Azure chưa cấu hình nên tìm kiếm chạy bằng CSDL dự phòng.
- Người kiểm thử: vai trò QA (đọc mã nguồn + gọi API thật + kiểm tra bằng Chrome headless)

## 0. Cách đọc báo cáo

**Mức độ**

| Mức | Ý nghĩa |
|---|---|
| Cao | Làm hỏng chức năng chính, mất dữ liệu, hoặc một người dùng làm hỏng hệ thống cho người khác |
| Trung bình | Chức năng sai/thiếu trong tình huống thực tế, có cách né nhưng gây khó chịu hoặc dữ liệu sai |
| Thấp | Trường hợp biên, trải nghiệm, hoặc củng cố |

**Cách xác nhận** (ghi ở mỗi lỗi)

- **[Đã chạy]**: tái hiện được trên hệ thống đang chạy (API thật hoặc Chrome headless).
- **[Đọc mã]**: suy ra từ mã nguồn, chưa chạy được (không có công cụ điều khiển giao diện, hoặc cần khóa Azure/worker thật).

**Phạm vi chưa làm được**

- Không có công cụ điều khiển trình duyệt, nên lỗi frontend chủ yếu là [Đọc mã]. Riêng lỗi `step` của ô số đã được xác nhận bằng Chrome headless (mục FE-01, FE-02).
- Không chạy `npm run build`/`tsc` (máy không có Node), không chạy `pytest` (README ghi pytest tạo thêm dữ liệu rác).
- Azure AI Search, Azure Maps, Function, Telegram thật: chưa cấu hình nên không kiểm thử.
- Giữa chừng Docker dừng nên **chưa dọn được dữ liệu test**; xem mục 6.

---

## 1. Tóm tắt

| | Cao | Trung bình | Thấp |
|---|---|---|---|
| Backend | 3 | 7 | 7 |
| Frontend | 1 | 7 | 7 |

**Năm việc nên sửa trước**

1. **BE-01**: một phòng đã duyệt có bảng giá lớn làm `GET /search/rooms` và trang chi tiết trả 500 cho **mọi người dùng**.
2. **FE-01**: ô "Giá thuê" của form đăng phòng chặn gần như mọi mức giá thật (3.000.000 không nhập được).
3. **BE-02**: hàng loạt đầu vào hợp lệ về schema nhưng gây 500 (số quá lớn, ngày năm 0001/9999, area làm tròn về 0).
4. **BE-03**: một phòng có thể có nhiều khách đang thuê, hóa đơn bị nhân bản.
5. **FE-03**: form sửa phòng mất dữ liệu đang gõ khi tải ảnh hoặc ẩn/hiện tin.

**Những phần đã kiểm tra và đạt** (để biết không cần lo)

- Phân quyền: 40+ ca IDOR/vai trò (chủ trọ B đọc/sửa/xóa tài nguyên chủ trọ A, sinh viên gọi API admin, hủy lịch của người khác, token ký dùng làm token đăng nhập và ngược lại, `alg:none`) đều trả 401/403/404 đúng.
- Đồng thời: 8 yêu cầu đặt cùng một khung giờ chỉ 1 thành công; 6 lần đăng ký cùng email chỉ 1 thành công.
- Upload: từ chối SVG, GIF, WebP, HTML đội lốt, file rỗng, ảnh >5 MB, ảnh thứ 11, file `.exe` giả PDF.
- SQL injection qua `q` (kể cả `'; DROP TABLE`, `%`, `_`, `\`): an toàn.
- Định dạng lỗi chung `{"error": {...}}` nhất quán cho 401/403/404/409/422.

---

## 2. Lỗi Backend

### BE-01 [Cao] [Đã chạy] Một phòng có bảng giá lớn làm sập tìm kiếm toàn site

**Hiện tượng.** Chủ trọ tạo phòng với `cost_rates.electricity_per_kwh = 2000000000` và `service_per_month = 2000000000`, gửi duyệt, admin duyệt. Từ lúc đó:

- `GET /search/rooms` (không lọc gì) → **500 INTERNAL_ERROR**
- `GET /rooms/{id}` của phòng đó → 500
- `POST /rooms/compare` chứa phòng đó → 500

Ẩn phòng (`POST /landlord/rooms/{id}/hide`) thì tìm kiếm hoạt động lại. Tôi đã ẩn phòng thử ngay sau khi xác nhận.

**Nguyên nhân.** `room_monthly_cost()` trong `backend/db/schema.sql` tính bằng `integer` (int4) và cộng các khoản. `_BASE_SELECT` trong `backend/app/services/rooms_public.py` dùng `CROSS JOIN LATERAL room_monthly_cost(...)` cho **mọi** phòng công khai, nên một dòng tràn số làm hỏng cả truy vấn. API `/rooms/{id}/cost` cũng tràn với `kwh=10000` nếu giá điện > 214.748đ/kWh.

**Ảnh hưởng.** Một chủ trọ (cố ý hoặc gõ nhầm thêm vài số 0) khiến toàn bộ sinh viên không tìm được phòng. Admin duyệt xong mới lộ ra và không có cảnh báo.

**Đề xuất sửa.**

1. Chặn ở schema (`backend/app/schemas/__init__.py`): mọi trường tiền có `le` hợp lý, ví dụ `price_month <= 100_000_000`, `deposit_amount <= 1_000_000_000`, `electricity_per_kwh <= 100_000`, `water_per_m3 <= 1_000_000`, các khoản tháng `<= 50_000_000`.
2. Đổi `room_monthly_cost` sang `bigint`/`numeric` và `LEAST(..., 2147483647)` cho `total`, để dữ liệu xấu cũ không làm hỏng truy vấn.
3. Thêm CHECK trong `schema.sql` cho các cột tiền (cùng ngưỡng).
4. Trang duyệt của admin hiển thị `est_monthly_cost` để người duyệt thấy số bất thường.

---

### BE-02 [Cao] [Đã chạy] Nhiều đầu vào hợp lệ về schema gây HTTP 500

Mọi ca dưới đây trả `500 INTERNAL_ERROR` thay vì 422 có thông điệp. Người dùng chỉ thấy "Lỗi máy chủ".

| # | Yêu cầu | Nguyên nhân |
|---|---|---|
| 1 | `POST /landlord/rooms` `price_month = 3000000000` | `integer` Postgres tràn, schema chỉ có `gt=0` |
| 2 | `deposit_amount = 3000000000` | như trên |
| 3 | `cost_rates.electricity_per_kwh = 3000000000` | như trên |
| 4 | `POST /landlord/tenants` `deposit_amount = 3000000000` | như trên |
| 5 | `area_m2 = 99999.99` | cột `numeric(6,1)` làm tròn thành 100000.0, tràn |
| 6 | `area_m2 = 0.04` | `lt/gt` qua được, nhưng làm tròn về `0.0` vi phạm `CHECK (area_m2 > 0)` |
| 7 | `POST /landlord/meter-readings` `electricity_index = 1e12` | `numeric(10,1)` tràn |
| 8 | `electricity_index = 1e999` (thành `inf`) | `ge=0` cho `inf` đi qua |
| 9 | `POST /bookings` `slot_start = "0001-01-01T00:00:00+07:00"` | `astimezone(utc)` ném `OverflowError` |
| 10 | `POST /landlord/invoices/generate` `month = "9999-12"` | `next_month()` tạo `date(10000, 1, 1)` → `ValueError` |
| 11 | `GET /landlord/invoices?month=0000-01` | regex của Query cho qua, `parse_month` ném `ValueError` không được bắt |

Ngoài ra (dữ liệu sai nhưng không lỗi): `area_m2 = 20.55` lưu thành `20.6`; chỉ số `100.04` lưu thành `100.0`; ngày bắt đầu thuê `0001-01-01` được chấp nhận.

**Đề xuất sửa.**

- Thêm `le=` cho mọi số nguyên tiền/đếm (xem BE-01).
- `area_m2`: `Field(ge=1, le=9999, decimal_places=1)` (hoặc `multiple_of=0.1`).
- Chỉ số công tơ: `Field(ge=0, le=99_999_999, allow_inf_nan=False)`.
- `parse_month`: giới hạn năm 2000–2100, và dùng chung trong `Query` qua validator (hiện Query chỉ dùng regex).
- `BookingIn`: validator kiểm tra `2000 <= year <= 2100` trước khi `astimezone`.
- Ngày thuê: giới hạn khoảng năm hợp lý.
- Handler `Exception` trong `errors.py` đã bắt mọi thứ thành 500; thêm handler riêng cho `sqlalchemy.exc.DataError`/`IntegrityError` trả 422 để lỗi sót vẫn có thông điệp đúng.

---

### BE-03 [Cao] [Đã chạy] Một phòng có thể có nhiều khách đang thuê, hóa đơn nhân bản

**Hiện tượng.** Tạo liên tiếp 5 khách thuê cùng phòng, cùng ngày bắt đầu → cả 5 được chấp nhận. `POST /landlord/invoices/generate {"month":"2026-09"}` sinh **5 hóa đơn, mỗi hóa đơn thu đủ 3.000.000đ tiền phòng** (tổng 19.275.000đ cho một phòng 3 triệu). Còn thấy:

- `people_count = 20` cho phòng `max_people = 2` được chấp nhận.
- Tạo khách thuê cho phòng đang `draft` được chấp nhận.
- `email = "not-an-email"` được chấp nhận (`TenantIn.email` chỉ là `str | None`).
- Khách có `start_date = 0001-01-01` được chấp nhận.

**Nguyên nhân.** `tenants` không có ràng buộc duy nhất cho khách đang thuê trong cùng phòng; `create_tenant` chỉ gọi `owned_room`.

**Đề xuất sửa.**

- CSDL: `CREATE UNIQUE INDEX tenants_one_active_per_room ON tenants (room_id) WHERE is_active;` (nếu hệ thống cho thuê ghép thì thay bằng kiểm tra tổng `people_count <= max_people`).
- `create_tenant`: kiểm tra trạng thái phòng (chỉ `published`/`hidden` đã từng duyệt), `people_count <= room.max_people`, email hợp lệ.
- Ánh xạ `IntegrityError` của index trên thành `409 TENANT_EXISTS`.
- Frontend: xem FE-04 (tạo trùng do thử lại).

---

### BE-04 [Trung bình] [Đã chạy + đọc mã] Hóa đơn: sinh cho khách đã hết hạn, không sửa/hủy được

- `generate_for_landlord` (`backend/app/services/invoices.py`) lọc `is_active` và `start_date <= month_end`, **không** lọc `end_date >= period`. Khách có `end_date` trước tháng đó nhưng chưa bị tắt `is_active` vẫn bị tính tiền (đã thấy: khách có `end_date = 2026-09-30` vẫn có hóa đơn tháng 9, đúng, nhưng với tháng 10 cũng sẽ có).
- Không có prorate cho khách vào/ra giữa tháng.
- Trạng thái `void` có trong enum, `INVOICE_STATUS_LABEL` và UI nhưng **không có API nào** chuyển sang `void`; nhập sai chỉ số rồi tạo hóa đơn thì không sửa được, tạo lại thì `INVOICE_EXISTS`.
- `POST /landlord/invoices/generate` trả **201** với `created: []` khi toàn bộ bị bỏ qua (thiếu chỉ số): nên là 200, hoặc 422 kèm lý do.

**Đề xuất sửa.** Thêm điều kiện `(Tenant.end_date IS NULL OR Tenant.end_date >= period)`; thêm `POST /landlord/invoices/{id}/void` (chỉ khi `unpaid`) cho phép tạo lại; ghi rõ quy tắc prorate trong SPEC (hoặc ghi "không prorate").

---

### BE-05 [Trung bình] [Đã chạy] Chỉ số công tơ không được kiểm tra hợp lý

`POST /landlord/meter-readings` chấp nhận: chỉ số tháng 11 (50) **nhỏ hơn** tháng 10 (250); tháng `9999-12`; tháng `2099-01`. Hóa đơn chỉ phát hiện về sau ("Chỉ số tháng sau nhỏ hơn tháng trước") và chỉ ở bước tạo hóa đơn.

**Đề xuất sửa.** Khi lưu, so với kỳ liền trước/liền sau của cùng phòng, báo 422 nếu không tăng dần (cho phép ghi đè có xác nhận nếu công tơ bị thay). Giới hạn kỳ không quá tháng hiện tại + 1.

---

### BE-06 [Trung bình] [Đã chạy] Giới hạn đăng nhập tính cả lần đăng nhập thành công

`login_rate_limit` (`backend/app/security.py`) ghi mọi lần gọi. 10 lần đăng nhập **đúng** trong 1 phút từ cùng IP → lần thứ 11 trả 429 ("Thử quá nhiều lần"). Sinh viên dùng chung wifi trường/KTX (cùng IP NAT) sẽ khóa lẫn nhau. Ngoài ra `_hits` là `defaultdict` chỉ được dọn khi cùng IP quay lại nên bộ nhớ tăng theo số IP; chỉ `/auth/login` có giới hạn (đăng ký, đặt lịch, báo cáo, tải ảnh không có).

**Đề xuất sửa.** Chỉ đếm lần thất bại, khóa theo cặp (IP, email); xóa khóa rỗng; giới hạn thêm cho `/auth/register`, `/reports`, `/bookings`, upload; nếu chạy nhiều worker thì dùng kho chung (Redis/bảng DB).

---

### BE-07 [Trung bình] [Đã chạy] Kiểm tra đăng ký/hồ sơ quá lỏng

- Email `a@b.c` và `x@y..z` được chấp nhận (regex `^[^@\s]+@[^@\s]+\.[^@\s]+$` quá rộng; cùng regex nằm trong CHECK của DB).
- Mật khẩu `aaaaaaaa` được chấp nhận (chỉ có độ dài tối thiểu 8).
- Họ tên `<script>alert(1)</script>` được lưu. React đang tự thoát ký tự nên giao diện web an toàn, nhưng dữ liệu đã bẩn, các kênh khác (Telegram, email, PDF hóa đơn sau này, bản đồ `htmlContent`) dễ dính.
- `str_strip_whitespace=True` áp dụng cả cho mật khẩu: mật khẩu `"  abc12345  "` bị cắt âm thầm; mật khẩu 8 dấu cách báo "ít hơn 8 ký tự" dù ô nhập đã vượt `minLength=8` của trình duyệt.
- Tiêu đề phòng `<img src=x onerror=alert(1)>` được lưu (cùng nhóm).

**Đề xuất sửa.** Dùng `email-validator`; yêu cầu mật khẩu có ≥ 1 chữ + 1 số hoặc kiểm tra danh sách mật khẩu yếu; không strip mật khẩu (`Field(..., strip_whitespace=False)`) ; giới hạn ký tự tên (chữ, khoảng trắng, dấu `.'-`); sanitize tiêu đề/mô tả khi xuất sang kênh không phải HTML.

---

### BE-08 [Trung bình] [Đã chạy + đọc mã] Đặt lịch xem phòng

- Khung giờ không chuẩn hóa: `16:38:13.123456` và `16:38:14` cho **cùng phòng** đều được nhận, nên unique index `(room_id, slot_start)` không chặn được trùng thực tế. Giao diện giới hạn mốc 15 phút (commit `278cfd9`) nhưng API thì không.
- Không có khung giờ làm việc: đặt lịch 3:00 sáng được chấp nhận (ca này bị chặn bởi giới hạn 3 lịch nên không chạy trọn, nhưng không có kiểm tra giờ trong mã).
- Một sinh viên đặt được nhiều phòng cùng một giờ (chỉ kiểm tra `room_id + slot`).
- Chủ trọ xác nhận được lịch đã quá giờ (`confirm` không kiểm tra `slot_start`).
- Ghi chú khi sinh viên hủy lịch bị bỏ âm thầm (`_transition` chỉ lưu ghi chú nếu là chủ trọ; đã chạy: gửi `{"note":"bận đột xuất"}` thì cả `landlord_note` và `student_note` đều `null`).

**Đề xuất sửa.** `BookingIn`: yêu cầu `second == 0 and microsecond == 0 and minute % 15 == 0`; giới hạn giờ 07:00–21:00 (hoặc cấu hình); kiểm tra sinh viên không có lịch khác trong ±1 giờ; `confirm` chỉ khi `slot_start > now`; lưu ghi chú hủy của sinh viên vào cột riêng hoặc trả 422 nếu không hỗ trợ.

---

### BE-09 [Trung bình] [Đã chạy] Phòng được công khai không cần ảnh; sửa sau duyệt không qua kiểm duyệt

- `POST /landlord/rooms/{id}/submit` thành công khi phòng chưa có ảnh nào. Admin gọi `approve` với `{"image_ids_ok": []}` loại hết ảnh chờ duyệt mà vẫn xuất bản. Kết quả: tin công khai không ảnh (đã tạo `QA phòng chính` theo cách này).
- Với phòng đã `published`, chủ trọ sửa tiêu đề, mô tả, giá bằng `PATCH` thì thay đổi hiển thị ngay (chỉ ảnh mới mới phải duyệt). Quản trị viên không thấy nội dung mới.

**Đề xuất sửa.** Yêu cầu ≥ 1 ảnh để `submit` và để `approve` (kiểm tra số ảnh `ok` sau khi áp dụng `image_ids_ok`). Quyết định chính sách: sửa trường nhạy cảm (tiêu đề/mô tả/giá) của tin công khai đưa lại về `pending`, hoặc ghi vào audit và hiện cờ "đã sửa sau duyệt" cho admin.

---

### BE-10 [Trung bình] [Đã chạy] Ảnh: phục vụ công khai chưa kiểm duyệt, kiểm tra file chỉ bằng magic byte

- `GET /api/v1/images/{id}` (không cần đăng nhập) trả ảnh có `moderation = pending` của phòng `draft/pending/hidden`. Đã chạy: ảnh vừa tải lên của phòng nháp tải được ẩn danh (200). UUID khó đoán nên rủi ro thực tế thấp, nhưng bỏ qua mục đích kiểm duyệt.
- `sniff_image` chỉ xem 3 byte đầu: file `\xff\xd8\xff` + chuỗi rác được chấp nhận là "JPEG"; PNG hợp lệ + đuôi `<script>` được lưu và phục vụ nguyên xi (`Content-Type: image/png`, không có `X-Content-Type-Options: nosniff`).

**Đề xuất sửa.** `GET /images/{id}`: chỉ phục vụ ẩn danh khi `moderation == 'ok'` và phòng đang `published`; với chủ phòng/admin thì kiểm tra token (hoặc dùng URL ký). Dùng Pillow `Image.open().verify()` rồi mã hóa lại ảnh (loại bỏ metadata, polyglot). Thêm `X-Content-Type-Options: nosniff`.

---

### BE-11 [Thấp] [Đã chạy] URL ký trước cho CCCD/hợp đồng dùng được không cần đăng nhập

`GET /landlord/tenants/{id}/files/{kind}` trả `/api/v1/files/signed?token=...`; đã gọi URL đó **không có header Authorization** → 200 và trả file (đúng thiết kế SPEC 19, hạn 5 phút). Rủi ro: token nằm trong query nên rơi vào log nginx/access log, lịch sử trình duyệt, header Referer; ai có đường link trong 5 phút đều xem được CCCD.

**Đề xuất sửa.** Rút hạn còn 60 giây và dùng một lần (lưu `jti` đã dùng); hoặc để frontend tải bằng `fetch` kèm Bearer rồi mở `blob:`; che query string trong log nginx (`map $request_uri` hoặc `access_log` với `$uri`).

---

### BE-12 [Thấp] [Đã chạy] Tìm kiếm văn bản kém cho tiếng Việt

- `q=cau giay` (không dấu) → 0 kết quả, trong khi `Cầu Giấy` → 11.
- `q=Cầu  Giấy` (hai dấu cách) → 0; `q=phòng cầu giấy gần bách khoa` → 0 (khớp cả chuỗi con, không tách từ).
- `price_min=5000000&price_max=1000000` → 200 với 0 kết quả, không báo khoảng sai.
- Bộ lọc `area` so khớp chính xác chuỗi tự do chủ trọ nhập (`Cầu Giấy` ≠ `cầu giấy` ≠ `Cau Giay`), facet trả mảng rỗng khi dùng CSDL dự phòng.

**Đề xuất sửa.** Bật `unaccent` + `pg_trgm` (hoặc `to_tsvector('simple', unaccent(...))`), tách từ theo khoảng trắng và yêu cầu tất cả từ khớp; trả 422 khi `price_min > price_max`; chuẩn hóa `area` (danh mục khu vực hoặc `lower(unaccent())`), tính facet trong `search_db`.

---

### BE-13 [Thấp] [Đã chạy] Báo cáo (report) có thể gửi trùng không giới hạn

Cùng sinh viên, cùng phòng, cùng lý do: 3 lần liên tiếp đều 201. Có thể làm ngập hàng đợi của admin. **Sửa:** unique `(reporter_id, target_type, target_id)` khi `status='open'`, hoặc trả lại báo cáo cũ; giới hạn tần suất.

---

### BE-14 [Thấp] [Đã chạy] Múi giờ không nhất quán trong phản hồi

`POST /admin/reports/{id}/resolve` trả `resolved_at` dạng `+00:00` trong khi `created_at` dạng `+07:00`; `telegram-link` trả `expires_at` `+00:00`. Do giá trị `datetime.now(timezone.utc)` được trả lại mà không `refresh`. Frontend dùng `Intl` nên hiển thị đúng; chỉ ảnh hưởng client khác. **Sửa:** `db.refresh()` trước khi trả, hoặc chuẩn hóa hàm `iso()` về `+07:00`.

---

### BE-15 [Thấp] [Đã chạy] Nhà trọ: tọa độ nửa vời

`POST /landlord/houses` với `lat` mà thiếu `lng` được lưu (lat=21.0, lng=null). `PATCH` với `lat: null` cho nhà đang có phòng công khai làm các phòng đó mất tọa độ trên bản đồ/khoảng cách. **Sửa:** validator "cả hai hoặc không"; không cho xóa tọa độ khi nhà có phòng `published`.

---

### BE-16 [Thấp] [Đọc mã + quan sát] Việc nền và đồng bộ

- `worker/worker/main.py:process_job_runs` vẫn là `TODO`: "Sao lưu ngay"/"Khôi phục thử" tạo dòng `queued` không bao giờ chạy. `_queue_job` thấy dòng `queued/running` thì trả `already_queued` mãi, không có hạn chờ nên một dòng `running` bị bỏ lại (worker sập giữa chừng) khóa chức năng vĩnh viễn. Kiểm tra TOCTOU: hai lần bấm đồng thời có thể tạo hai dòng.
- `sync_outbox` tích lũy (đang có 68 dòng `pending`, `last_sent_at = null`) vì Azure chưa cấu hình; không có dọn dẹp hay cảnh báo tăng.
- `worker/outbox.py` coi `AZURE_FUNCTION_INGEST_URL` chứa `SUFFIX` là đã cấu hình, trong khi API (`_is_set`) coi `SUFFIX` là chưa cấu hình; nếu có khóa mà URL còn placeholder thì worker gọi host không tồn tại, 10 lần rồi `failed`.

**Sửa.** Hoàn thiện `process_job_runs`; coi `queued/running` quá 15–30 phút là bỏ (đổi `failed`); khóa bằng `pg_advisory_xact_lock` hoặc partial unique index trên `job_runs`; dùng chung hàm `_is_set` giữa api và worker.

---

### BE-17 [Thấp] Củng cố bảo mật triển khai [Đã chạy]

- nginx không gửi `X-Content-Type-Options`, `X-Frame-Options`/`frame-ancestors`, `Referrer-Policy`, CSP.
- `/api/docs` và `/api/openapi.json` mở công khai.
- Đăng nhập, đăng ký trả thông điệp phân biệt được email tồn tại (`409 EMAIL_TAKEN`): chấp nhận được nhưng nên ghi vào rủi ro.
- `JWT` 12 giờ, không có thu hồi; mật khẩu đổi không vô hiệu token cũ.

**Sửa.** Thêm header ở `frontend/nginx.conf`; tắt docs ở môi trường sản xuất (biến `ENABLE_DOCS`); cân nhắc `token_version` trong bảng `users`.

---

## 3. Lỗi Frontend

### FE-01 [Cao] [Đã chạy bằng Chrome headless] Ô "Giá thuê" chặn mọi giá thật

`frontend/src/pages/landlord/RoomEdit.tsx`: `<Input type="number" required min={1} step={50000} ...>`. Theo chuẩn HTML, gốc của `step` là `min`, nên giá trị hợp lệ chỉ là 1, 50.001, 100.001, … Đã kiểm tra trên Chrome: `3000000`, `3050000`, `2500000` đều `stepMismatch = true` (form bị trình duyệt chặn, hiện "Please enter a valid value. The two nearest valid values are…"); chỉ `50001` hợp lệ. Hệ quả: chủ trọ **không tạo/lưu được phòng** với giá phổ biến.

**Sửa.** `min={0} step={50000}` (đúng bội 50.000) hoặc tốt hơn `step="any"`/`step={1000}` vì giá thực tế có thể là 2.750.000, 3.150.000. Thêm `noValidate` cho form nếu muốn tự hiển thị lỗi.

### FE-02 [Trung bình] [Đã chạy bằng Chrome headless] Các ô số khác dùng `step` sai

| Vị trí | Thuộc tính | Giá trị bị chặn (đã xác nhận) |
|---|---|---|
| `FilterPanel.tsx` giá từ/đến và chi phí tối đa | `min=0 step=100000` | `2550000`, `1250000` |
| `FilterPanel.tsx` diện tích từ | `min=0` (mặc định step=1) | `20.5` (backend nhận float) |
| `RoomEdit.tsx` đặt cọc | `min=0 step=50000` | `3025000` |
| `Invoices.tsx` chỉ số công tơ | `step=0.1` | `100.04` (hợp lý, nhưng thông điệp trình duyệt khó hiểu) |

Với bộ lọc, nhấn "Áp dụng" im lặng không làm gì (tooltip của trình duyệt chỉ hiện ở ô lỗi, dễ bị bỏ sót, nhất là khi bộ lọc nằm trong ngăn kéo di động).

**Sửa.** `step="any"` cho tiền/diện tích trong bộ lọc, hoặc `noValidate` và tự kiểm tra; chọn sẵn mức giá bằng preset.

### FE-03 [Trung bình] [Đọc mã] Form sửa phòng mất dữ liệu đang gõ

`RoomEdit.tsx`:

```ts
useEffect(() => { if (room.data) setF(toForm(room.data)); }, [room.data]);
```

`room.data` đổi mỗi khi query được làm mới: sau khi tải ảnh (`refresh()` → `invalidateQueries(["landlord-room", id])`), sau khi xóa ảnh, sau `transition` (ẩn/hiện/gửi duyệt dùng `setQueryData`). Mỗi lần như vậy form bị ghi đè bằng dữ liệu máy chủ, nên mọi thay đổi chưa bấm "Lưu" biến mất. Kịch bản: sửa giá và mô tả → tải thêm một ảnh → giá và mô tả quay về giá trị cũ.

**Sửa.** Chỉ khởi tạo form một lần cho mỗi `id` (cờ `initialized`/`useRef`), hoặc chỉ ghi đè khi form chưa bị sửa (`isDirty`). Hiện cảnh báo khi rời trang với thay đổi chưa lưu.

### FE-04 [Trung bình] [Đọc mã] Thử lại sau lỗi tải file tạo khách thuê trùng

`Tenants.tsx` `TenantModal`: mutation gọi `POST /landlord/tenants`, rồi tải CCCD/hợp đồng. Nếu bước tải file lỗi (file >10 MB, định dạng sai, MinIO tạm ngắt), mutation báo lỗi nhưng khách thuê **đã được tạo**; modal vẫn mở ở chế độ "thêm mới" (`tenant = null`), người dùng sửa file và bấm Lưu lần nữa → `POST` lần hai tạo khách thứ hai. Kết hợp BE-03 sẽ ra hóa đơn trùng.

**Sửa.** Sau khi tạo thành công, lưu `savedId` vào state và chuyển sang `PATCH`; tách lỗi tải file thành thông báo riêng ("Đã lưu khách thuê, tải file lỗi: …") cho phép thử lại chỉ phần file.

### FE-05 [Trung bình] [Đọc mã] Ô từ khóa tìm kiếm lệch với URL

`Search.tsx`: `const [q, setQ] = useState(filters.q)` chỉ khởi tạo một lần. Khi URL đổi mà `SearchPage` không bị gỡ (bấm logo/"Tìm phòng" đến `/`, nút Back, nút "Xóa lọc") thì ô vẫn hiện từ khóa cũ trong khi kết quả đã bỏ lọc. Nhấn "Áp dụng" ở bộ lọc rồi lại áp dụng lại từ khóa cũ (`apply({...f, q})`).

**Sửa.** `useEffect(() => setQ(filters.q), [filters.q])`.

### FE-06 [Trung bình] [Đọc mã, cần khóa Maps] Bản đồ nhảy lại mỗi lần rê chuột vào thẻ phòng

`MapView.tsx`: effect vẽ ghim có `highlightedId` trong deps và kết thúc bằng `map.setCamera({ bounds ... })`. Rê chuột lên mỗi `RoomCard` làm xóa/vẽ lại toàn bộ ghim và đưa bản đồ về khung ban đầu, hủy thao tác kéo/zoom của người dùng; tốn hiệu năng với 20 ghim.

**Sửa.** Tách hai effect: (1) tạo ghim và `setCamera` khi `rooms/school/radius` đổi; (2) chỉ đổi màu ghim đang nổi bật theo `highlightedId` (giữ tham chiếu marker theo `id`).

### FE-07 [Trung bình, tiềm ẩn] [Đọc mã] Vòng lặp làm mới ở trang Hệ thống sau khi một việc nền kết thúc

`SystemStatus.tsx`: `<JobWatcher onDone={() => qc.invalidateQueries(...)} />` truyền hàm mới mỗi lần render; trong `JobWatcher`, `useEffect(() => { if (finished) onDone(); }, [finished, onDone])`. Khi việc đã `success/failed`: `onDone` làm trang cha làm mới → trang cha render lại (`isFetching` thay đổi) → `onDone` mới → effect chạy lại → làm mới tiếp… gọi liên tục `/admin/system/status` (mỗi lần còn gọi dò Azure). Hiện chưa xảy ra vì worker chưa chạy việc nền (BE-16) nhưng sẽ xảy ra ngay khi hoàn thiện.

**Sửa.** Bọc `onDone` bằng `useCallback`, hoặc lưu bằng `useRef` và chạy effect chỉ theo `finished`.

### FE-08 [Trung bình] [Đọc mã] Chọn tọa độ nhà trọ dễ gây nhầm

`MapPicker.tsx`:

- Nhà mới: ghim đặt ở giữa Hà Nội nhưng `lat/lng` vẫn `null`, người dùng tưởng đã đặt ghim rồi bấm Lưu; về sau "gửi duyệt" mới báo "Nhà chưa có tọa độ".
- Gõ vĩ độ khi kinh độ trống tự điền kinh độ `105.79` (HANOI_CENTER) thành một tọa độ giả.
- Không xóa được ô: `onChange={(e) => e.target.value && onChange(...)}` bỏ qua giá trị rỗng nên backspace về rỗng bị hoàn lại.

**Sửa.** Chỉ coi là đã đặt khi người dùng bấm/kéo/định vị; để ô lat/lng độc lập (`null` cho từng ô) và kiểm tra cả hai khi lưu; cho phép rỗng; báo trước khi lưu nhà không có tọa độ.

### FE-09 [Thấp] [Đọc mã] Bảng chi phí nuốt lỗi 422

`CostTable.tsx` cho phép nhập `kwh` vượt `10000`, `m3 > 1000`, `people > 20`; API trả 422 nhưng chỉ đọc `data, isFetching`, nên bảng giữ kết quả cũ trong khi ô nhập hiện số mới (hiển thị sai). Hàm `Number(value) || 0` khiến không xóa trống được ô (xóa là về `0`). **Sửa:** `max` trong input, kẹp giá trị, hiện `error`.

### FE-10 [Thấp] [Đọc mã] Danh sách phòng bị cắt ở 50

`TenantModal` và `MeterReadingCard` chỉ lấy `page_size: 50` phòng. Chủ trọ có hơn 50 phòng không chọn được phòng thứ 51 trở đi. **Sửa:** tải đủ trang hoặc dùng ô chọn có tìm kiếm.

### FE-11 [Thấp] [Đọc mã] Ngày theo UTC thay vì giờ Việt Nam

`new Date().toISOString().slice(0, 10)` (ngày bắt đầu mặc định, ngày kết thúc khi "Kết thúc thuê") là ngày UTC: từ 00:00 đến 07:00 giờ Việt Nam sẽ ra ngày hôm trước. `currentMonth()` dùng giờ máy khách. `soon(end_date)` gắn "Sắp hết hạn" cả khi hợp đồng đã quá hạn. **Sửa:** dùng `Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Ho_Chi_Minh'})` (đã có sẵn kiểu này ở `vnInputValue`), thêm nhãn "Đã hết hạn".

### FE-12 [Thấp] [Đọc mã] Khu vực lọc cứng trong mã

`FilterPanel.tsx` có `KNOWN_AREAS` cố định (6 khu vực); khu vực mới do chủ trọ nhập (chuỗi tự do) chỉ xuất hiện khi Azure trả facet, mà chế độ dự phòng CSDL trả facet rỗng (BE-12) nên không lọc được. **Sửa:** API `/areas` (distinct từ phòng công khai) hoặc tính facet trong `search_db`.

### FE-13 [Thấp] [Đọc mã] So sánh phòng

Chỉ cần 1 trong 3 phòng đã gỡ công khai là `POST /rooms/compare` trả 404 cho cả bảng, thông báo không nói phòng nào; danh sách so sánh lưu `localStorage` nên lỗi tồn tại qua phiên. Khi hai phòng bằng nhau về giá/chi phí thì chỉ phòng đầu được gắn 🏆. **Sửa:** API bỏ qua phòng không còn công khai và trả danh sách `missing`; frontend tự gỡ khỏi danh sách; so sánh tất cả giá trị bằng nhau.

### FE-14 [Thấp] [Đọc mã] Trình duyệt không hỗ trợ `type="month"`

Trang Hóa đơn dùng `<Input type="month">` (3 chỗ). Firefox và Safari trên máy tính không hỗ trợ, ô trở thành văn bản tự do, nhập `10/2026` sẽ nhận 422. **Sửa:** hai ô chọn tháng/năm hoặc kiểm tra định dạng `YYYY-MM` phía client.

### FE-15 [Thấp] Vặt về giao diện và trải nghiệm [Đọc mã]

- `alert()`/`confirm()` khắp nơi (đặt lịch, hóa đơn, nhà trọ, khách thuê): chặn luồng, không đẹp trên di động; nên dùng toast/`Modal`.
- `Modal` không đóng được bằng phím Esc, không giữ tiêu điểm, không có `role="dialog"`/`aria-modal`.
- Header trên màn hình nhỏ (< `sm`) ẩn nút "Đăng ký" và menu ☰ cũng không có mục Đăng ký/Đăng nhập cho khách.
- Trang đăng nhập hiển thị chú thích "Tài khoản demo: admin@, chutro1..4@… (mật khẩu SEED_DEMO_PASSWORD)" cho cả môi trường sản xuất. Nên ẩn bằng biến build (`import.meta.env.DEV`).
- Người đã đăng nhập vẫn vào được `/login`, `/register`.
- `BookingModal`: giờ mặc định tính một lần lúc tải trang; để trang mở lâu rồi mở modal, giá trị mặc định có thể nhỏ hơn `min`. Thời điểm sau khi đặt xong vẫn giữ giờ cũ nên đặt lần hai sẽ 409.
- `ModerationCard`: nút "Duyệt ảnh" hiện cho mọi phòng `published` kể cả khi không có ảnh chờ; bấm sẽ tăng `version` và ghi outbox vô ích. `okIds` khởi tạo một lần nên không cập nhật khi có ảnh mới.
- Thông báo ở trang sửa phòng "đồng bộ sang Azure AI Search trong vài giây" không đúng khi outbox đang tạm dừng (chưa cấu hình Azure).
- `ImagesCard`: tải nhiều ảnh theo tuần tự và dừng ở ảnh lỗi đầu tiên, không nói đã tải lên được mấy ảnh; không kiểm tra kích thước phía client.

---

## 4. Gợi ý bổ sung kiểm thử tự động

`backend/tests/test_api.py` hiện có 21 ca (TC01–TC12). Nên thêm:

1. Bảng tham số hóa "đầu vào biên → 422, không bao giờ 500" cho mọi endpoint ghi (BE-02): số lớn, `0`, `inf`, ngày năm 0001/9999, chuỗi dài, JSON sai.
2. Ca "phòng công khai có bảng giá lớn không làm hỏng tìm kiếm" (BE-01).
3. Ca không trùng khách thuê/hóa đơn (BE-03) và ca hóa đơn tháng sau ngày kết thúc (BE-04).
4. Ca đặt lịch: khung giờ lẻ, chồng giờ, giờ đêm (BE-08).
5. Frontend: thêm Playwright cho 3 luồng chính (đăng ký → tìm phòng → đặt lịch; chủ trọ tạo nhà → phòng → gửi duyệt; admin duyệt) để bắt các lỗi như FE-01/02 mà kiểm thử API không thấy.
6. CI: chạy `tsc --noEmit`, `pytest` và Playwright cho mỗi pull request.

## 5. Thứ tự sửa đề xuất

| Đợt | Việc | Công sức |
|---|---|---|
| 1 (ngay) | BE-01, BE-02 (ràng buộc tại schema + CHECK DB), FE-01, FE-02 | Nhỏ: vài giờ |
| 2 | BE-03, FE-03, FE-04, FE-05, BE-09 | Vừa |
| 3 | BE-04, BE-05, BE-06, BE-07, BE-08, BE-10, FE-06, FE-07, FE-08 | Vừa |
| 4 | Các mục Thấp, nhóm củng cố (BE-11..17, FE-09..15), thêm kiểm thử tự động | Tùy |

## 6. Dữ liệu thử nghiệm còn lại trong CSDL cục bộ (cần dọn)

Các lần chạy test để lại dữ liệu giả (README đã cảnh báo kiểm thử tạo dữ liệu). Docker dừng giữa chừng nên tôi **chưa dọn**. Nội dung:

- Tài khoản: `qa-*@example.com`, `a@b.c`, `x@y..z`.
- Chủ trọ `chutro1`: nhà "QA House", "QA only lat"; nhiều phòng tên bắt đầu bằng "QA"; khách thuê, chỉ số công tơ (kể cả `9999-12`, `2099-01`), hóa đơn `HD-202609-*` của các phòng QA; ảnh phòng và một hợp đồng giả trong MinIO.
- Đặt lịch, báo cáo, yêu thích gắn vào phòng QA.
- **Sửa dữ liệu mẫu có sẵn:** `sinhvien5@example.com` bị đặt `phone = NULL` (lúc test `PATCH /me`; giá trị gốc tôi không ghi lại, xem `seed/seed.sql` hoặc nạp lại dữ liệu mẫu).

Khi Docker chạy lại, dọn bằng SQL (đã soạn, **chưa chạy**; xem lại trước khi chạy):

```sql
BEGIN;
CREATE TEMP TABLE qa_rooms AS
  SELECT r.id FROM rooms r JOIN houses h ON h.id = r.house_id WHERE h.name LIKE 'QA %';
DELETE FROM sync_outbox WHERE entity_id IN (SELECT id FROM qa_rooms);
DELETE FROM reports     WHERE target_id IN (SELECT id FROM qa_rooms);
DELETE FROM invoices    WHERE room_id   IN (SELECT id FROM qa_rooms);
DELETE FROM tenants     WHERE room_id   IN (SELECT id FROM qa_rooms);
DELETE FROM houses      WHERE name LIKE 'QA %';           -- phòng, ảnh, lịch, chỉ số xóa theo
DELETE FROM users WHERE email LIKE 'qa-%@example.com' OR email IN ('a@b.c', 'x@y..z');
COMMIT;
```

Cách nhanh và sạch nhất theo README: `docker compose down && rm -rf data/postgres data/minio && docker compose up -d` (nạp lại dữ liệu mẫu).

## 7. Phụ lục: ca kiểm thử đã chạy

Script tái hiện nằm ngoài repo, trong thư mục tạm của phiên (`qa_a.py` … `qa_d.py`, `step.html`); nếu cần giữ lại để chạy hồi quy, có thể chuyển vào `backend/tests/`.

| Nhóm | Số ca (xấp xỉ) | Kết quả |
|---|---|---|
| Xác thực, đăng ký, JWT, giới hạn tần suất | 24 | BE-06, BE-07 |
| Tìm kiếm, so sánh, chi tiết, chi phí | 30 | BE-12 |
| Nhà, phòng, biên dữ liệu, duyệt | 28 | BE-01, BE-02, BE-09, BE-15 |
| Đặt lịch + IDOR | 17 | BE-02 (#9), BE-08 |
| Khách thuê, chỉ số, hóa đơn | 27 | BE-02, BE-03, BE-04, BE-05 |
| Đánh giá, báo cáo, yêu thích | 13 | BE-13 |
| Ma trận phân quyền | 22 | Đạt |
| Upload ảnh/file, URL ký | 19 | BE-10, BE-11 |
| Đồng thời (đặt lịch, đăng ký, hóa đơn) | 3 | Đạt |
| Admin, hồ sơ, Telegram | 12 | BE-14 |
| Kiểm tra `step` bằng Chrome headless | 19 giá trị | FE-01, FE-02 |

---

## 8. Kết quả kiểm thử lại (19/11/2026, commit `b9290df`)

Môi trường: stack Docker cục bộ, api/web đã build lại từ mã mới; migration `2026-11-18-gioi-han-tien.sql` được áp lên CSDL đang chạy trong lúc kiểm thử.

| Mã | Kết quả | Ghi chú |
|---|---|---|
| BE-01 | **Đã sửa** | Đặt thẳng giá điện/phí dịch vụ 2 tỷ vào CSDL (giả lập dữ liệu cũ). Sau migration: `/search/rooms` 200, `/rooms/{id}` 200, `/rooms/{id}/cost?kwh=10000` 200 (tổng kẹp ở 2.147.483.647). CSDL từ chối ghi mới (`violates check constraint "cost_rates_limits"`). |
| BE-02 | **Đã sửa** | 11/11 ca trả 422 có thông điệp: giá/cọc/giá điện > ngưỡng, area 99999.99 và 0.04 và 20.55, cọc khách thuê 3e9, ngày bắt đầu 0001, chỉ số 1e12 và `inf`, đặt lịch năm 0001/9999, hóa đơn `9999-12`/`0000-01`, danh sách hóa đơn `month=0000-01`. |
| FE-01 | **Đã sửa** | Giá thuê `min=1000 max=1e8 step=1000`: Chrome headless chấp nhận 3.000.000, 2.750.000, 3.150.000, 100.000.000; từ chối 1.500 và 100.001.000. Bundle đang phục vụ chứa thuộc tính mới. |
| FE-02 | **Đã sửa** | Bộ lọc giá `step=1000` nhận 2.550.000 và 1.250.000; ô diện tích `step=any` nhận 20.5. Đặt cọc nhận 3.025.000. Ô tiền cọc khách thuê (`Tenants.tsx`) và chỉ số công tơ vẫn như cũ. |
| Hồi quy | Đạt | Tạo phòng giá 3.000.000 (area 20.5) → 201; giá 100.000.000 + cọc 1.000.000.000 → 201 (đúng biên). |

**Lưu ý phát sinh**

1. **Phải áp migration cho CSDL đang chạy.** Trước khi áp, mã API mới đã có nhưng hàm SQL `room_monthly_cost` vẫn là bản cũ, nên dữ liệu cũ có giá lớn vẫn làm hỏng tìm kiếm (xem điểm 2). `docker compose up -d --build` không tự áp migration.
2. **Handler lỗi CSDL mới trả 422 cho cả lệnh GET.** Trước migration, `GET /search/rooms` với dữ liệu cũ bị hỏng trả `422 "Giá trị vượt giới hạn cho phép"` thay vì 500. Mã 422 báo lỗi do người gọi trong khi thật ra lỗi nằm ở dữ liệu máy chủ; người dùng sẽ tự trách mình và nhóm vận hành không thấy cảnh báo lỗi 5xx. Nên chỉ ánh xạ `DataError` thành 422 cho yêu cầu ghi (POST/PUT/PATCH), còn GET vẫn trả 500 và ghi log.
3. Các mục còn mở không thuộc đợt sửa này (BE-03…BE-17, FE-03…FE-15) chưa được kiểm tra lại; riêng BE-05 vẫn tái hiện (chỉ số tháng `2099-01` được chấp nhận).
4. Lần kiểm thử lại để thêm hai phòng "QA retest …" vào dữ liệu thử (cùng nhóm dữ liệu ở mục 6). Giá điện và phí dịch vụ của "QA phòng chính" đã được khôi phục về 3.500 và 50.000.

---

## 9. Trạng thái sửa trên nhánh `fix/qa-bao-cao-18-11` (19/11/2026)

Commit `baa11bb` (backend, worker) và `e8eb166` (web). Kiểm chứng: `pytest` 35/35 đạt (thêm 12 ca mới cho từng lỗi), `tsc --noEmit` + `vite build` đạt, Chrome headless render được `/`, `/login`, `/register`, `/compare`, kiểm tra qua nginx (ảnh URL ký, header bảo mật, log đã che token).

| Mã | Trạng thái | Cách kiểm chứng |
|---|---|---|
| BE-03, BE-04, BE-05 | Đã sửa | pytest `test_be03_*`, `test_be04_be05_*` |
| BE-06, BE-07 | Đã sửa | pytest `test_be06_*`, `test_be07_*`, `test_login_rate_limit`; 12 lần đăng nhập đúng qua nginx đều 200 |
| BE-08, BE-09, BE-10 | Đã sửa | pytest `test_be08_*`, `test_be09_*`, `test_be10_*`, `test_image_upload_and_validation` |
| BE-11 | Đã sửa một phần | Hạn 60 giây, log nginx che query. Token vẫn dùng được nhiều lần trong 60 giây; log lỗi (error.log) của nginx vẫn ghi đủ URL khi có lỗi upstream |
| BE-12, BE-13, BE-14, BE-15 | Đã sửa | pytest `test_be12_*`, `test_be13_be14_*`, `test_be15_*` |
| BE-16 | Đã sửa một phần | Việc treo > 30 phút được đánh dấu hỏng, khóa chống tạo trùng, worker xóa `public_url` khi gỡ blob. `process_job_runs` (chạy backup.sh/restore-test.sh) vẫn là TODO của worker |
| BE-17 | Đã sửa một phần | Header bảo mật, `API_DOCS`. Chưa có CSP (cần thử với Azure Maps SDK), chưa có thu hồi JWT |
| Mục 8 điểm 2 (422 cho GET) | Đã sửa | Lỗi CSDL ở lệnh đọc trả 500 |
| FE-03 … FE-15 | Đã sửa | Đọc mã + build; chưa thao tác giao diện thật (không có công cụ điều khiển trình duyệt). FE-12 được giải quyết nhờ facet mới ở backend. `alert()`/`confirm()` vẫn giữ nguyên |
| Chưa làm | | Sửa tin đã duyệt đưa về chờ duyệt (BE-09, cần nhóm quyết chính sách); xóa blob khi xóa một ảnh của phòng đang công khai; prorate hóa đơn |

**Khi triển khai nhánh này lên CSDL đang chạy**, áp lần lượt hai migration `2026-11-18-gioi-han-tien.sql` và `2026-11-19-sua-loi-qa.sql`, rồi `docker compose up -d --build api worker web`. Trên máy này migration in NOTICE bỏ qua index một-khách-mỗi-phòng vì phòng "QA phòng chính" (dữ liệu thử của tôi) đang có nhiều khách; dọn dữ liệu QA (mục 6) rồi chạy lại migration thì index được tạo.
