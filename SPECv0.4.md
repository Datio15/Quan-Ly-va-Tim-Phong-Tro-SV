# SPEC – Quản lý và tìm phòng trọ cho sinh viên (Azure + OpenStack)

Phiên bản 0.4 · 14/11/2026 · Người giữ file: Người 1 (Đặng Thế Đạt, nhóm trưởng)

File này là **nguồn sự thật duy nhất** về kiến trúc, dữ liệu, API và quy ước. Khi nhờ AI sinh code, dán phần liên quan của file này (mục 0 chỉ rõ phần nào cho mô-đun nào). **Muốn đổi tên bảng, API hay luồng dữ liệu thì sửa file này trước, báo cả nhóm, rồi mới sửa code.**

Các lựa chọn đánh dấu *mặc định* là đề xuất ban đầu. Các quyết định đã chốt nằm ở mục 23 và được ưu tiên khi có chỗ lệch.

**Mục lục**

0. Cách dùng với AI · 1. Mục tiêu và phạm vi · 2. Kiến trúc · 3. Luồng chi tiết · 4. Phân loại dữ liệu · 5. Công nghệ · 6. Cấu trúc kho mã · 7. Vai trò và quyền · 8. Mô hình dữ liệu · 9. Quy tắc nghiệp vụ · 10. API · 11. Tích hợp Azure · 12. Worker · 13. Hạ tầng OpenStack · 14. Hạ tầng Azure · 15. Biến môi trường · 16. Sao lưu và khôi phục · 17. Giám sát và cảnh báo · 18. Dữ liệu mẫu · 19. Bảo mật · 20. Quy ước làm việc · 21. Mô-đun và tiêu chí nghiệm thu · 22. Kịch bản kiểm thử · 23. Quyết định đã chốt · 24. Mốc · 25. Thuật ngữ

File đi kèm (đã chạy thử, xem README):

| File | Nội dung |
|---|---|
| `backend/db/schema.sql` | Toàn bộ bảng, kiểu, view `v_rooms_public`, hàm `room_monthly_cost`, `distance_m` |
| `seed/generate_seed.py`, `seed/seed.sql` | Bộ sinh dữ liệu giả tái lập được và kết quả (80 phòng) |
| `azure-functions/search-index.json` | Định nghĩa chỉ mục Azure AI Search `rooms-public` |
| `scripts/backup.sh`, `scripts/restore-test.sh` | Sao lưu mã hóa lên Azure Blob, khôi phục thử có đối chiếu |
| `infra/openstack/setup.sh`, `cloud-init.yaml` | Dựng project, mạng, security group, VM, volume, floating IP |
| `infra/azure/setup.sh` | Dựng Storage, AI Search + chỉ mục, Maps, Key Vault, App Insights, Function App |
| `backend/app/`, `backend/tests/` | Backend API đã code (FastAPI), 21 kiểm thử gồm TC01–TC12 |
| `frontend/` | Web đã code (React 18 + Vite + TypeScript + Tailwind), nginx proxy `/api/*` |
| `azure-functions/function_app.py` | `ingest-room`, `tick-now`, `daily-ticks-morning`, `daily-ticks-backup` (mục 11) |
| `LUU-Y.md`, `backend/README.md` | Cách chạy, tài khoản demo, lưu ý cổng và bảo mật của web |

### Thành viên

| Người | Họ tên | Phụ trách |
|---|---|---|
| 1 | Đặng Thế Đạt (nhóm trưởng) | Quản lý, SPEC, dữ liệu mẫu, kiểm thử; Thông báo Telegram (F12, mục 3F); Logic App cảnh báo (F15) |
| 2 | Dương Hoàng Anh | OpenStack (tiếp nhận từ Người 4 ngày 14/11) |
| 3 | Nguyễn Tiến Đạt | Frontend |
| 4 | Vũ Tuấn Anh | Backend API và web trong repo EasyRent: bảo trì, sửa lỗi; bàn giao OpenStack cho Người 2 |
| 5 | Trịnh Thị Vân | Azure, Azure Functions |
| 6 | Phạm Nguyễn Thu Giang | Worker; tích hợp, kiểm thử hai cloud; sao lưu (F13) |

### Mã nguồn chuẩn (từ v0.4)

Backend API và web đã code xong phần lõi trong repo `Anh-cybersecurity/EasyRent` (thư mục `backend/`, `frontend/`; 21 kiểm thử, gồm TC01–TC12, đạt ở máy cá nhân). **Từ v0.4, mã này là bản chuẩn.** Chỗ nào SPEC v0.3 và mã khác nhau thì SPEC đã sửa theo mã (bảng dưới). Worker, Azure Functions và OpenStack viết theo SPEC này để khớp với web đã có, không sửa API của web nếu chưa sửa SPEC.

### Hiện trạng ngày 14/11

| Phần | Tình trạng |
|---|---|
| Backend API | Xong F01–F09, F11, F14, F16, F17 (phần api của F10, F12, F13); chưa chạy trên VM |
| Web | Xong các trang ở mục 6; build thành công; chưa chạy trên VM |
| Hạ tầng Azure | Đã kiểm đạt 14/11: Storage, AI Search + chỉ mục, Key Vault, Function App (chưa có hàm), Maps, Budget |
| Azure Functions | Đang viết và deploy, hạn 15/11 (Người 5) |
| Worker | Đang viết vòng outbox, hạn 15/11 (Người 6) |
| OpenStack | VM chưa chạy được (lỗi cloud-init); Tailscale chưa ai cài; Người 2 tiếp nhận |
| Telegram, Logic App | Chưa làm (Người 1) |

### Thay đổi so với v0.3

| Mục | Thay đổi | Lý do |
|---|---|---|
| Thành viên, 0, 2, 13, 21 | Người 2 chuyển sang OpenStack; worker do Người 6; Người 4 giữ backend và web đã code | Phân công lại 14/11 |
| 5, 6 | Cấu trúc thư mục và trang web theo mã thật; chưa dùng Alembic | Theo mã |
| 7, 9.3 | Lịch `confirmed`: hai bên thấy liên hệ của nhau; bỏ "lưu tìm kiếm" (F20 đã bỏ) | Theo mã |
| 9.1 | Gửi duyệt cần nhà có tọa độ; `approve` duyệt ảnh mới của phòng đang công khai; `reject` gỡ phòng đang công khai | Theo mã |
| 9.4, 15 | Ba biến mới: `CORS_ORIGINS`, `REVIEW_SKIP_BOOKING_CHECK`, `FORWARDED_ALLOW_IPS` | Theo mã |
| 10.1 | Mã lỗi mới: `METHOD_NOT_ALLOWED`, `RATE_LIMITED`, `INTERNAL_ERROR`, `HTTP_ERROR`; header `X-Response-Time-Ms` | Theo mã |
| 10.2 | Endpoint mới: `/images/{id}`, `/files/signed`, `GET /landlord/tenants/{id}/files/{kind}`, `GET /landlord/meter-readings`, `GET /admin/landlords`, lọc `pending_images`; body `resolve`; sao lưu trả 202 | Theo mã |
| 10.4 | `/admin/system/status` thêm `outbox_failed_rows`, `recent_jobs` | Theo mã |
| 11.1, 11.4 | Mã phản hồi của `ingest-room`; Timer tách hai hàm `daily-ticks-morning`, `daily-ticks-backup`; `tick-now` kiểm tra `type` | Mỗi hàm Timer chỉ có một lịch |
| 12 | `daily_backup` tạo dòng `job_runs(job='backup')`; outbox tạm dừng khi chưa có khóa hàm | Bổ sung chi tiết |
| 14 | Key Vault dùng **access policy** (v0.3 ghi nhầm RBAC); Maps vùng `global`; Function gói FC1; thêm bí mật `azure-maps-key`; Budget US$30 | Theo tài nguyên đã tạo |
| 19 | api chỉ nhận request qua nginx; giới hạn đăng nhập trong bộ nhớ, api chạy `--workers 1` | Theo mã |

---

## 0. Cách dùng với AI

### Mẫu mở đầu cho mọi lần nhờ AI

```
Bạn đang làm mô-đun <TÊN MÔ-ĐUN> của hệ thống mô tả trong SPEC.md (đính kèm các mục liên quan).
Ràng buộc:
- Dùng đúng tên bảng, cột, kiểu enum, API, mã lỗi và biến môi trường trong SPEC.md và schema.sql.
  Nếu cần thêm hoặc đổi, hãy ĐỀ XUẤT sửa SPEC.md, không tự đổi.
- Phiên bản: Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL 16, Node 20, React 18 + Vite + TypeScript,
  Docker Compose v2, Ubuntu 24.04 trên VM. Với OpenStack và Azure, dùng lệnh và SDK hiện hành
  (azure-search-documents, azure-storage-blob, azure-storage-queue, azure-functions mô hình Python v2),
  không dùng cú pháp của bản cũ.
- Không viết mật khẩu, khóa, token vào code; đọc từ biến môi trường (SPEC mục 15).
- Không ghi dữ liệu cá nhân (tên, số điện thoại, email, CCCD) vào log.
- Viết kèm hướng dẫn chạy thử và một kiểm thử nhỏ.
Việc cần làm: <mô tả cụ thể, kèm mã chức năng F.. và mã kiểm thử TC.. nếu có>
```

### Mục nào dán cho mô-đun nào

| Mô-đun | Mục cần dán | File cần dán |
|---|---|---|
| Backend API (Người 4) | 2, 3, 7, 8, 9, 10, 19 | `schema.sql` |
| Worker (Người 6) | 3, 4, 11, 12, 16 | `schema.sql` (bảng sync_outbox, job_runs, notifications) |
| Frontend (Người 3) | 1, 7, 9, 10 | – |
| Azure Functions (Người 5) | 3, 4, 11 | `search-index.json` |
| OpenStack (Người 2) | 2, 13, 15, 16, 19 | `infra/openstack/*` |
| Thông báo Telegram, Logic App (Người 1) | 3C, 3F, 12, 17 | – |

Không dán khóa, mật khẩu hay token thật vào khung chat với AI.

---

## 1. Mục tiêu và phạm vi

Nền tảng hai phía: **sinh viên** tìm và so sánh phòng trọ, biết chi phí thật mỗi tháng; **chủ trọ** đăng tin, quản lý khách thuê và hóa đơn; **quản trị viên** kiểm duyệt. Dữ liệu cá nhân ở OpenStack (private cloud); tìm kiếm, bản đồ, hẹn giờ, sao lưu và giám sát ở Azure (public cloud).

### Danh sách chức năng

Ưu tiên: **M** = MVP (bắt buộc trước 23/11), **S** = nên có. Mức C (F18 đến F22) đã bỏ ở mục 23.

| Mã | Chức năng | Ưu tiên | Người chính |
|---|---|---|---|
| F01 | Đăng ký, đăng nhập, phân quyền 3 vai trò | M | 2, 3 |
| F02 | Chủ trọ quản lý nhà, phòng, bảng giá dịch vụ, tiện nghi | M | 2, 3 |
| F03 | Tải ảnh phòng (MinIO), gửi duyệt, quản trị duyệt hoặc từ chối | M | 2, 3 |
| F04 | Tìm phòng: từ khóa, giá, diện tích, khu vực, tiện nghi, giờ giấc, khoảng cách tới trường, sắp xếp | M | 2, 3, 5 |
| F05 | Bản đồ các phòng và khoảng cách tới trường (Azure Maps) | M | 3, 5 |
| F06 | So sánh 2-3 phòng cạnh nhau | M | 2, 3 |
| F07 | Chi phí thực tế mỗi tháng, chỉnh được số điện, nước, người, xe | M | 2, 3 |
| F08 | Đặt lịch xem phòng; chủ trọ xác nhận hoặc từ chối | M | 2, 3 |
| F09 | Yêu thích; đánh giá sau khi xem/thuê; báo cáo đánh giá sai | M | 2, 3 |
| F10 | Đồng bộ tin công khai OpenStack → Azure AI Search + Blob, có thử lại và đồng bộ lại bằng tay | M | 2, 5, 4 |
| F11 | Tìm kiếm dự phòng bằng CSDL khi Azure không phản hồi | M | 2 |
| F12 | Nhắc lịch xem phòng qua Telegram (hẹn giờ từ Azure, gửi từ OpenStack) | M | 1, 5 |
| F13 | Sao lưu hằng ngày mã hóa sang Azure Blob; khôi phục thử có đo thời gian | M | 4, 5, 6 |
| F14 | Trang trạng thái hệ thống cho quản trị (đồng bộ, sao lưu, việc nền) | M | 2, 3 |
| F15 | Giám sát Application Insights và cảnh báo lỗi qua Telegram/email | M | 1, 5, 6 |
| F16 | Khách thuê, hợp đồng (file giả), nhắc hợp đồng sắp hết hạn | S | 2, 3 |
| F17 | Nhập chỉ số điện nước, tạo hóa đơn tháng, đánh dấu đã trả, nhắc quá hạn | S | 2, 3 |

Cột "Người chính" giữ theo phân công ban đầu. Phân công hiện tại xem mục 21.

**Ngoài phạm vi:** F18 đến F22 (hóa đơn PDF kèm VietQR, báo cáo doanh thu, lưu tiêu chí tìm, kiểm duyệt ảnh và đọc công tơ bằng AI; đã bỏ ở mục 23), thanh toán thật, gửi SMS, ứng dụng di động riêng, dữ liệu thật của người khác, cào dữ liệu từ trang khác.

---

## 2. Kiến trúc

```
                  Sinh viên / Chủ trọ / Quản trị  (trình duyệt)
                                  |
                       http 80 (floating IP của vm-app)
                                  v
 ┌────────────────────────── OpenStack (private cloud) ─────────────────────────┐
 │  vm-app  (sg-app: 80/443 mở, 22 từ ADMIN_CIDR)                                 │
 │   ├─ web     React build, nginx; /api/* proxy sang api                         │
 │   ├─ api     FastAPI :8000                                                     │
 │   └─ worker  outbox → Azure, poll hàng đợi, thông báo, gọi backup.sh           │
 │                       │ 5432, 9000 (chỉ từ sg-app)                             │
 │  vm-data (sg-data)    v                                                        │
 │   ├─ PostgreSQL 16  ┐                                                         │
 │   ├─ MinIO          ├─ /srv/data trên volume Cinder vol-data (snapshot)       │
 │   └─ cron 02:00 backup.sh                                                      │
 └──────────┬──────────────────────────────────────────────────▲─────────────────┘
   CHỈ kết nối RA (HTTPS 443)                                    │ worker kéo tin (poll)
            │                                                    │
 ┌──────────▼───────────────────────── Azure (public cloud) ─────┴───────────────┐
 │ Function ingest-room (HTTP) ──► AI Search: rooms-public                        │
 │ Blob public-images (ảnh công khai)      Function daily-ticks-* (Timer) ──► Queue│
 │ Blob backups (bản sao lưu mã hóa)       Storage Queue ops-ticks                 │
 │ Azure Maps (bản đồ, geocode)            Key Vault (khóa, mật khẩu sao lưu)     │
 │ Application Insights + Azure Monitor ──► Action Group ──► Logic Apps ──► Telegram│
 │ Cost Management: Budget + cảnh báo                                             │
 └────────────────────────────────────────────────────────────────────────────────┘
```

### Thành phần

| Thành phần | Chạy ở | Cổng | Người |
|---|---|---|---|
| web (React + nginx) | vm-app, Docker | 80 | 3 |
| api (FastAPI) | vm-app, Docker | 8000 (nội bộ, không mở ra ngoài) | 4 |
| worker (Python) | vm-app, Docker | – | 6 |
| PostgreSQL 16 | vm-data, Docker | 5432 (chỉ từ sg-app) | 2 |
| MinIO | vm-data, Docker | 9000 (chỉ từ sg-app), 9001 console | 2 |
| Function `ingest-room`, `tick-now`, `daily-ticks-morning`, `daily-ticks-backup` | Azure Functions | HTTPS | 5 |
| AI Search, Blob, Queue, Maps, Key Vault, App Insights | Azure | HTTPS | 5 |
| Logic Apps (cảnh báo) | Azure | – | 1 |

### Nguyên tắc bất di bất dịch

1. **Azure không bao giờ gọi vào OpenStack.** Mọi kết nối giữa hai cloud là chiều đi ra từ OpenStack (HTTPS 443). Không mở cổng vào máy host, không cần VPN.
2. **Dữ liệu định danh cá nhân không rời OpenStack** (mục 4). Function `ingest-room` từ chối mọi tài liệu có trường ngoài danh sách cho phép.
3. **Azure hỏng thì hệ thống vẫn chạy:** tìm kiếm rơi về CSDL (F11), thay đổi nằm lại trong `sync_outbox` và gửi bù khi Azure trở lại.
4. **Mọi thứ chạy được bằng một lệnh:** `docker compose up` ở local và trên VM, cùng file.

---

## 3. Luồng chi tiết

### A. Đăng tin → tìm thấy trên Azure (F02, F03, F10)

1. Chủ trọ tạo phòng (`status = draft`), nhập bảng giá, tiện nghi, tải ảnh.
2. Chủ trọ bấm "Gửi duyệt" → `pending` (nhà phải có tọa độ, mục 9.1). Quản trị duyệt → `published`, `published_at = now()`.
3. Trong **cùng transaction** với bước 2 (và mọi lần sửa phòng đang công khai), api tăng `rooms.version` và chèn một dòng `sync_outbox(entity_type='room', entity_id, entity_version, op)`. `op = 'upsert'` nếu phòng đang `published`, ngược lại `'delete'`.
4. worker (5 giây một lần) lấy các dòng đến hạn (mục 12.2), dựng tài liệu công khai từ `v_rooms_public` (không dùng `payload` cũ), đẩy ảnh mới lên Blob, gọi Function `ingest-room`.
5. Function kiểm tra danh sách trường, so `version`, ghi vào AI Search.
6. worker đánh dấu `sent`; lỗi thì thử lại tăng dần. Quản trị thấy số dòng chờ/lỗi ở trang trạng thái và có nút đồng bộ lại.

Thời gian mục tiêu từ lúc duyệt đến lúc tìm thấy: **dưới 15 giây** (đo và ghi vào báo cáo).

### B. Tìm kiếm (F04, F05, F11)

1. Trình duyệt gọi `GET /api/v1/search/rooms?...`.
2. api dịch tham số sang truy vấn AI Search (mục 11.3), gọi với khóa **chỉ đọc**, giới hạn `SEARCH_TIMEOUT_MS`.
3. Thành công → trả kết quả, header `X-Search-Source: azure`.
4. Lỗi hoặc quá giờ → truy vấn `v_rooms_public` trong PostgreSQL với cùng bộ lọc, header `X-Search-Source: db`, tăng số đo `search_fallback_count`.
5. Khoảng cách tới trường tính bằng `distance_m()`; bản đồ vẽ bằng Azure Maps Web SDK từ `lat/lng` trong kết quả.

### C. Nhắc việc: Azure hẹn giờ, OpenStack xử lý (F12, F16, F17)

1. Hai Function Timer `daily-ticks-morning` và `daily-ticks-backup` chạy theo lịch (mục 11.4) và đưa tin vào Storage Queue `ops-ticks`, ví dụ `{"id":"...","type":"viewing_reminder","at":"..."}`. **Tin không chứa dữ liệu cá nhân.**
2. worker kéo hàng đợi 30 giây một lần, bỏ qua tin đã xử lý (`processed_messages`), chạy việc tương ứng **trên dữ liệu cục bộ**, gửi Telegram trực tiếp từ OpenStack, ghi `notifications` để không gửi trùng.
3. Nội dung thông báo chỉ có thông tin tối thiểu (mục 12.4).

Vì sao thiết kế như vậy: hẹn giờ và hàng đợi là thế mạnh của public cloud, còn dữ liệu cá nhân vẫn ở private cloud; OpenStack chỉ cần kết nối ra ngoài.

### D. Sao lưu và khôi phục thử (F13)

Xem mục 16. Tóm tắt: `pg_dump` + MinIO → nén → mã hóa AES-256 → tải lên Blob `backups` bằng SAS chỉ-ghi; khôi phục thử tải bản mới nhất bằng SAS chỉ-đọc, giải mã, nạp vào CSDL riêng, đối chiếu số dòng, ghi thời gian vào `job_runs`.

### E. Giám sát và cảnh báo (F15)

api và worker gửi số đo (mục 17) lên Application Insights. Quy tắc cảnh báo của Azure Monitor gọi Action Group → Logic Apps → Telegram nhóm quản trị. Chỉ cảnh báo kỹ thuật, không chứa dữ liệu cá nhân.

### F. Liên kết Telegram cho người dùng (F12)

1. Người dùng bấm "Nhận thông báo Telegram" → `POST /api/v1/me/telegram-link` → api sinh mã ngẫu nhiên 16 ký tự, lưu `telegram_link_code`, hạn 15 phút, trả link `https://t.me/<tên_bot>?start=<mã>`.
2. Người dùng mở link, bấm Start; Telegram gửi `/start <mã>` cho bot.
3. worker gọi `getUpdates` của Telegram Bot API (chiều đi ra), khớp mã → lưu `telegram_chat_id`, xóa mã, trả lời "Đã liên kết".

---

## 4. Phân loại dữ liệu

| Dữ liệu | Nơi lưu | Rời OpenStack? |
|---|---|---|
| Họ tên, số điện thoại, email, mật khẩu băm, telegram_chat_id | PostgreSQL (vm-data) | Không |
| Số nhà, ngõ (`houses.address_private`) | PostgreSQL | Không |
| Ảnh CCCD, hợp đồng thuê (GIẢ) | MinIO bucket `private` | Không |
| Khách thuê, chỉ số điện nước, hóa đơn | PostgreSQL | Không |
| Tin đăng công khai (các trường ở dưới) và ảnh phòng đã duyệt | Gốc ở OpenStack; bản công khai ở AI Search và Blob `public-images` | **Có, chỉ bản công khai** |
| Bản sao lưu CSDL và file | Blob `backups` | Có, **mã hóa trước khi rời máy**, khóa trong Key Vault |
| Số đo, nhật ký kỹ thuật | Application Insights | Có, không chứa dữ liệu cá nhân |
| Tín hiệu hẹn giờ | Storage Queue | Có, không chứa dữ liệu cá nhân |

### Danh sách trường cho phép gửi sang Azure (tài liệu `rooms-public`)

`id, title, description, price_month, est_monthly_cost, deposit_amount, area_m2, max_people, floor, street, ward, area, city, location, amenities, curfew, curfew_time, available_from, landlord_verified, rating_avg, rating_count, image_urls, version, updated_at`

Function `ingest-room` trả `400 FIELD_NOT_ALLOWED` nếu tài liệu có trường khác. **Không bao giờ** gửi: tên/điện thoại/email chủ trọ, `address_private`, `house_id`, `landlord_id`, thông tin khách thuê.

Lưu ý cho báo cáo: bản sao lưu tuy đã mã hóa vẫn là dữ liệu cá nhân đi ra hạ tầng bên ngoài; báo cáo cần nêu rõ biện pháp (mã hóa phía máy nguồn, khóa tách riêng ở Key Vault, SAS tách quyền ghi/đọc) và trích dẫn quy định hiện hành về bảo vệ dữ liệu cá nhân (nhóm tự kiểm tra văn bản đang có hiệu lực).

---

## 5. Công nghệ (mặc định)

| Thành phần | Chọn | Ghi chú |
|---|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2 (chưa dùng Alembic) | Mật khẩu băm argon2 (`argon2-cffi`) hoặc bcrypt; JWT (`pyjwt`) |
| CSDL | PostgreSQL 16 | `schema.sql` là nguồn duy nhất; muốn đổi CSDL thì sửa `schema.sql`, sửa SPEC và báo nhóm |
| Kho file | MinIO (API S3) | Thư viện `minio` hoặc `boto3` |
| Worker | Python 3.12, cùng mã nguồn mô hình với backend | `azure-storage-blob`, `azure-storage-queue`, `httpx` |
| Frontend | React 18, Vite, TypeScript, React Router, TanStack Query | CSS: Tailwind (đã chốt, mục 23) |
| Bản đồ | Azure Maps Web SDK v3 | Khóa riêng cho Maps |
| Tìm kiếm | Azure AI Search, gói Free, API `2024-07-01` | `azure-search-documents` |
| Hàm | Azure Functions, Python 3.11, mô hình lập trình v2 | Gói Flex Consumption (FC1, đã tạo) |
| Giám sát | `azure-monitor-opentelemetry` | Gửi số đo và trace |
| Thông báo | Telegram Bot API (`sendMessage`, `getUpdates`) | Gọi từ worker trên OpenStack |
| VM | Ubuntu 24.04 cloud image | Có sẵn `postgresql-client-16` khớp phiên bản máy chủ |
| Triển khai | Docker Engine + Compose v2 | Cùng `docker-compose.yml` |

**Ảnh công khai:** phục vụ trực tiếp từ Blob `public-images`. Không bật CDN mặc định: theo tôi biết Azure CDN cổ điển không còn cho tạo mới và Azure Front Door có phí cố định hằng tháng; báo cáo có thể nêu CDN là hướng mở rộng (nhóm kiểm tra lại tình trạng dịch vụ).

---

## 6. Cấu trúc kho mã

```
phongtro/
├─ SPEC.md  README.md  LUU-Y.md  docker-compose.yml  .env.example  .gitignore
├─ backend/
│  ├─ Dockerfile
│  ├─ db/schema.sql            # bản đầu của CSDL (đã chạy thử)
│  ├─ app/
│  │  ├─ main.py               # tạo FastAPI, gắn router, middleware đo thời gian
│  │  ├─ config.py             # đọc biến môi trường (pydantic-settings)
│  │  ├─ db.py                 # engine, session
│  │  ├─ models/               # SQLAlchemy model theo schema.sql
│  │  ├─ schemas/              # Pydantic request/response
│  │  ├─ routers/              # auth, public, rooms, bookings, landlord, landlord_ops, admin, health
│  │  ├─ services/             # search_service (Azure + dự phòng), rooms_public, cost, outbox, storage, invoices
│  │  ├─ security.py           # băm mật khẩu, JWT, phụ thuộc kiểm tra vai trò
│  │  └─ seed_passwords.py     # đặt mật khẩu tài khoản demo từ SEED_DEMO_PASSWORD
│  └─ tests/                   # test_api.py (TC01-TC12 và thêm), test_search_filter.py
├─ worker/
│  ├─ Dockerfile
│  └─ worker/                  # main.py (vòng lặp), db.py, outbox.py, queue.py, telegram.py, jobs/
├─ frontend/
│  ├─ Dockerfile  nginx.conf
│  └─ src/
│     ├─ pages/                # Search, RoomDetail, Compare, Bookings, Auth (Login, Register, Profile, Favorites),
│     │                        # landlord/ (Houses, Rooms, RoomEdit, Tenants, Invoices),
│     │                        # admin/ (Moderation, ReportsLandlords, SystemStatus)
│     ├─ components/           # Layout, MapView, MapPicker, CostTable, ...
│     └─ api/                  # client gọi /api/v1
├─ azure-functions/
│  ├─ search-index.json
│  ├─ function_app.py          # ingest-room, tick-now (HTTP); daily-ticks-morning, daily-ticks-backup (Timer)
│  └─ requirements.txt  host.json
├─ infra/
│  ├─ openstack/setup.sh  cloud-init.yaml
│  └─ azure/setup.sh
├─ scripts/backup.sh  restore-test.sh
├─ seed/generate_seed.py  seed.sql
└─ docs/                       # ảnh chụp, kết quả đo, ghi chú cho báo cáo
```

### Trang web (theo `frontend/src/App.tsx`)

| Đường dẫn | Trang | Vai trò |
|---|---|---|
| `/` | Tìm phòng: bộ lọc, danh sách, bản đồ | Mọi người |
| `/rooms/:id` | Chi tiết phòng, bản đồ, chi phí thực tế, đánh giá, đặt lịch | Mọi người (đặt lịch, đánh giá: sinh viên) |
| `/compare` | So sánh 2–3 phòng | Mọi người |
| `/login`, `/register` | Đăng nhập, đăng ký | Khách |
| `/profile` | Hồ sơ, liên kết Telegram | Đã đăng nhập |
| `/favorites` | Yêu thích | Sinh viên |
| `/bookings` | Lịch xem phòng | Sinh viên, chủ trọ |
| `/landlord/houses` | Nhà, đặt ghim tọa độ trên bản đồ | Chủ trọ |
| `/landlord/rooms`, `/landlord/rooms/:id` | Danh sách phòng; sửa phòng, bảng giá, tiện nghi, ảnh, gửi duyệt | Chủ trọ |
| `/landlord/tenants` | Khách thuê, file CCCD và hợp đồng GIẢ | Chủ trọ |
| `/landlord/invoices` | Chỉ số điện nước, hóa đơn | Chủ trọ |
| `/admin/moderation` | Duyệt tin, duyệt ảnh mới | Quản trị |
| `/admin/reports`, `/admin/landlords` | Xử lý báo cáo; xác minh chủ trọ | Quản trị |
| `/admin/system` | Trạng thái hệ thống, đồng bộ lại, sao lưu, khôi phục thử | Quản trị |

---

## 7. Vai trò và quyền

| Hành động | Khách | Sinh viên | Chủ trọ | Quản trị |
|---|:-:|:-:|:-:|:-:|
| Tìm, xem phòng công khai, so sánh, xem chi phí | ✓ | ✓ | ✓ | ✓ |
| Yêu thích, đặt lịch xem, đánh giá, báo cáo | | ✓ | | |
| Hủy lịch của mình | | ✓ | | |
| Quản lý nhà, phòng, ảnh, bảng giá **của mình** | | | ✓ | |
| Xác nhận/từ chối lịch xem phòng **của mình** | | | ✓ | |
| Xem liên hệ của bên kia khi lịch đã `confirmed` (mục 9.3) | | ✓ | ✓ | |
| Khách thuê, chỉ số, hóa đơn **của mình** | | | ✓ | |
| Duyệt tin và ảnh, gỡ tin đang công khai, xác minh chủ trọ, ẩn đánh giá, xử lý báo cáo | | | | ✓ |
| Trang trạng thái, đồng bộ lại, sao lưu, khôi phục thử | | | | ✓ |

Mọi API của chủ trọ phải kiểm tra **quyền sở hữu** (`houses.landlord_id = người đang đăng nhập`), không chỉ vai trò. Truy cập tài nguyên của người khác trả `404` (không lộ là có tồn tại).

---

## 8. Mô hình dữ liệu

Chi tiết cột, ràng buộc, chỉ mục nằm trong `backend/db/schema.sql` (21 bảng, đã nạp thử trên PostgreSQL 16). Quy ước: khóa chính `uuid` (`gen_random_uuid()`), thời gian `timestamptz` lưu UTC và hiển thị UTC+7, tiền là số nguyên VND, diện tích `numeric(6,1)`.

### Quan hệ chính

```
users (landlord) 1─n houses 1─n rooms 1─n room_images
                                  │ 1─1 cost_rates
                                  │ n─n amenities (room_amenities)
                                  │ 1─n bookings  n─1 users (student)
                                  │ 1─n reviews   n─1 users (student)
                                  │ 1─n tenants 1─n invoices
                                  │ 1─n meter_readings
users (student) n─n rooms (favorites) · users 1─n saved_searches
sync_outbox, job_runs, processed_messages, notifications, audit_log: bảng kỹ thuật
```

### Nhóm bảng

| Nhóm | Bảng | Ghi chú |
|---|---|---|
| Người dùng | `users`, `schools` | Email duy nhất không phân biệt hoa thường |
| Tin đăng | `houses`, `rooms`, `room_amenities`, `amenities`, `room_images`, `cost_rates` | `houses.area` là khu vực quen gọi để lọc (mục 9.6) |
| Sinh viên | `favorites`, `saved_searches`, `bookings`, `reviews`, `reports` | Chỉ mục duy nhất chặn hai lịch hiệu lực trùng giờ; `saved_searches` có trong `schema.sql` nhưng chưa dùng (F20 đã bỏ) |
| Chủ trọ | `tenants`, `meter_readings`, `invoices` | `invoices.total` là cột tự tính |
| Kỹ thuật | `sync_outbox`, `job_runs`, `processed_messages`, `notifications`, `audit_log` | Xem mục 12, 16 |

### Đối tượng dựng sẵn trong CSDL

| Tên | Dùng cho |
|---|---|
| `v_rooms_public` | Nguồn **duy nhất** để dựng tài liệu gửi Azure và để tìm kiếm dự phòng; chỉ chứa trường công khai |
| `room_monthly_cost(room_id, kwh, m3, people, vehicles)` | Chi phí thực tế (F07), bảng so sánh, trường `est_monthly_cost` |
| `distance_m(lat1, lng1, lat2, lng2)` | Khoảng cách theo đường chim bay (mét) |

### Mã tiện nghi

`gac_lung` Gác lửng · `dieu_hoa` Điều hòa · `nong_lanh` Bình nóng lạnh · `ve_sinh_rieng` Vệ sinh khép kín · `cho_de_xe` Chỗ để xe · `may_giat` Máy giặt · `tu_lanh` Tủ lạnh · `bep_rieng` Bếp riêng · `ban_cong` Ban công · `cua_so` Cửa sổ · `wifi` Wifi · `thang_may` Thang máy · `camera` Camera an ninh · `noi_that` Có nội thất · `khong_chung_chu` Không chung chủ. "Giờ giấc tự do" suy ra từ `curfew_time IS NULL`.

---

## 9. Quy tắc nghiệp vụ

### 9.1 Trạng thái phòng

```
draft ──gửi duyệt──► pending ──duyệt──► published ◄──hiện lại── hidden
  ▲                    │                   │ ──ẩn (chủ trọ/quản trị)──► hidden
  └──sửa lại── rejected ◄──từ chối──┘
```

- Chỉ `published` mới xuất hiện khi tìm và được gửi sang Azure.
- Sửa phòng đang `published`: giữ `published`, tăng `version`, ghi outbox `upsert`. Ảnh mới thêm vẫn qua kiểm duyệt riêng (`room_images.moderation`).
- Chuyển khỏi `published` (ẩn, bị từ chối): ghi outbox `delete`.
- Từ chối phải có `reject_reason`.
- Gửi duyệt yêu cầu nhà đã có tọa độ (`lat`, `lng`); thiếu thì `422 VALIDATION_ERROR`. Lý do: tìm theo khoảng cách và bản đồ cần tọa độ.
- Quản trị gỡ phòng đang `published` bằng `reject` (ghi outbox `delete`). Gọi `approve` trên phòng đang `published` chỉ duyệt các ảnh mới đang chờ, phòng giữ `published`.

### 9.2 Khi nào ghi `sync_outbox`

Ghi một dòng (cùng transaction) khi có thay đổi ảnh hưởng tài liệu công khai của phòng: đổi trạng thái vào/ra `published`; sửa trường công khai; đổi tiện nghi; đổi bảng giá (ảnh hưởng `est_monthly_cost`); ảnh được duyệt/xóa; thêm hoặc ẩn đánh giá (đổi `rating_avg`); quản trị đổi `verified` của chủ trọ (ghi cho **mọi** phòng công khai của chủ trọ đó).

### 9.3 Lịch xem phòng

```
requested ──chủ trọ xác nhận──► confirmed ──sau giờ hẹn──► done
    │ ──chủ trọ từ chối──► declined
    └──sinh viên/chủ trọ hủy──► cancelled ◄── confirmed
```

- Chỉ đặt cho phòng `published`, giờ hẹn trong tương lai, cách hiện tại ít nhất 2 giờ, tối đa 14 ngày tới.
- Hai lịch `requested/confirmed` trùng phòng và giờ → `409 BOOKING_CONFLICT` (do chỉ mục duy nhất trong CSDL).
- Mỗi sinh viên tối đa 3 lịch `requested` cùng lúc.
- Nhắc lịch: lúc 08:00 mỗi ngày gửi cho các lịch `confirmed` trong 24 giờ tới (một lần, ghi `reminded_at`).
- Khi lịch ở `confirmed`: sinh viên thấy số nhà, ngõ (`houses.address_private`), tên và số điện thoại chủ trọ; chủ trọ thấy tên và số điện thoại sinh viên. Dữ liệu này chỉ trả qua api trong OpenStack, không bao giờ vào tài liệu gửi Azure hay tin Telegram.

### 9.4 Đánh giá

Sinh viên đánh giá được phòng khi có ít nhất một lịch `done` với phòng đó (để demo, đặt `REVIEW_SKIP_BOOKING_CHECK=true` trong `.env` để bỏ qua điều kiện này). Mỗi sinh viên một đánh giá mỗi phòng (sửa được). `rating_avg` làm tròn 1 chữ số, chỉ tính đánh giá không bị ẩn.

### 9.5 Chi phí thực tế mỗi tháng (F07)

```
total = price_month
      + electricity_per_kwh × kwh
      + (water_mode = per_m3 ? water_per_m3 × m3 : water_per_person × people)
      + internet_per_month
      + parking_per_vehicle × vehicles
      + service_per_month
```

Mặc định lấy `EST_KWH_PER_MONTH`, `EST_WATER_M3_PER_MONTH`, `EST_PEOPLE`, `EST_VEHICLES` từ `.env`; người dùng chỉnh được trên giao diện. Trả về từng khoản để vẽ bảng. `est_monthly_cost` trong chỉ mục tính với các giá trị mặc định này.

### 9.6 Địa chỉ và khu vực

Từ 1/7/2025 Việt Nam bỏ cấp quận/huyện, nên dữ liệu dùng `ward` (phường/xã) và `area` (khu vực quen gọi, ví dụ "Cầu Giấy", để lọc theo thói quen của sinh viên). Dữ liệu là giả nên tên phường không cần khớp danh mục hành chính. Tọa độ lấy bằng Azure Maps Search (geocode) khi chủ trọ nhập địa chỉ, cho phép kéo ghim trên bản đồ để sửa.

### 9.7 Khoảng cách tới trường

Đường chim bay bằng `distance_m()` (đủ cho lọc và sắp xếp). Trang chi tiết có thể hiện thêm quãng đường đi thật bằng Azure Maps Route (S).

### 9.8 Hóa đơn (F17)

- Chỉ số công tơ là số cộng dồn, chốt ngày 1 hằng tháng (`meter_readings.period` = ngày 1).
- Hóa đơn tháng M: `điện dùng = chỉ số ngày 1/(M+1) − chỉ số ngày 1/M`; tương tự nước nếu tính theo m³.
- Tiền nước theo người dùng `tenants.people_count`; gửi xe theo `tenants.vehicle_count`.
- Mã hóa đơn `HD-YYYYMM-NNNN` (NNNN tăng theo tháng). Hạn thanh toán ngày 10 tháng M+1.
- Mỗi khách thuê một hóa đơn mỗi tháng (ràng buộc duy nhất). Tạo lại tháng đã có → `409 INVOICE_EXISTS`.
- `unpaid` quá hạn → việc nền `invoice_due_check` chuyển `overdue` và nhắc chủ trọ.

### 9.9 Hợp đồng sắp hết hạn (F16)

Khách thuê đang hiệu lực có `end_date` trong 30 ngày tới → nhắc chủ trọ một lần mỗi khách (bảng `notifications`).

---

## 10. API

### 10.1 Quy ước chung

- Tiền tố `/api/v1`. JSON `snake_case`. Thời gian ISO 8601 có múi giờ (`2026-11-20T10:00:00+07:00`).
- Xác thực: header `Authorization: Bearer <JWT>`. JWT chứa `sub` (user id), `role`, `exp`.
- Phân trang: `page` (từ 1), `page_size` (mặc định 20, tối đa 50). Trả `{ "items": [...], "page": 1, "page_size": 20, "total": 57 }`.
- Mọi phản hồi có header `X-Response-Time-Ms` (thời gian xử lý ở api).
- Lỗi: mã HTTP chuẩn và thân

```json
{ "error": { "code": "BOOKING_CONFLICT", "message": "Khung giờ này đã có người đặt", "details": {} } }
```

| Mã lỗi | HTTP | Khi nào |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Dữ liệu vào sai định dạng; `details.fields` liệt kê trường sai |
| `UNAUTHORIZED` | 401 | Thiếu hoặc sai token |
| `FORBIDDEN` | 403 | Sai vai trò |
| `NOT_FOUND` | 404 | Không có, hoặc không thuộc quyền sở hữu |
| `EMAIL_TAKEN` | 409 | Đăng ký trùng email |
| `BOOKING_CONFLICT` | 409 | Trùng lịch |
| `BOOKING_LIMIT` | 409 | Quá 3 lịch đang chờ |
| `ROOM_NOT_PUBLISHED` | 409 | Thao tác cần phòng công khai |
| `INVALID_TRANSITION` | 409 | Chuyển trạng thái không hợp lệ (mục 9) |
| `INVOICE_EXISTS` | 409 | Hóa đơn tháng đã tạo |
| `METHOD_NOT_ALLOWED` | 405 | Sai phương thức HTTP |
| `RATE_LIMITED` | 429 | Quá 10 lần đăng nhập mỗi phút từ một IP |
| `INTERNAL_ERROR` | 500 | Lỗi không lường trước; không trả chi tiết lỗi cho người dùng |
| `UPSTREAM_UNAVAILABLE` | 503 | Dịch vụ Azure cần thiết không phản hồi (trừ tìm kiếm, vốn có dự phòng) |
| `HTTP_ERROR` | khác | Mã HTTP khác không có trong bảng |

### 10.2 Danh sách endpoint

**Xác thực và hồ sơ**

| Method | Path | Vai trò | Mô tả |
|---|---|---|---|
| POST | /auth/register | Khách | Đăng ký `student` hoặc `landlord` |
| POST | /auth/login | Khách | Trả JWT |
| GET | /me | Đã đăng nhập | Hồ sơ |
| PATCH | /me | Đã đăng nhập | Sửa tên, số điện thoại |
| POST | /me/telegram-link | Đã đăng nhập | Sinh link liên kết Telegram (mục 3F) |

**Công khai và sinh viên**

| Method | Path | Vai trò | Mô tả |
|---|---|---|---|
| GET | /config | Khách | Cấu hình cho giao diện: `{"maps_key": "...", "telegram_bot": "<tên bot>", "est_defaults": {"kwh": 100, "m3": 4, "people": 1, "vehicles": 1}}` |
| GET | /schools | Khách | Danh sách trường |
| GET | /amenities | Khách | Danh mục tiện nghi |
| GET | /search/rooms | Khách | Tìm phòng (10.3) |
| GET | /rooms/{id} | Khách | Chi tiết phòng công khai |
| GET | /rooms/{id}/cost | Khách | Chi phí thực tế; query `kwh, m3, people, vehicles` |
| POST | /rooms/compare | Khách | Body `{"ids":[...2-3], "school_id"?}` |
| GET | /rooms/{id}/reviews | Khách | Đánh giá (phân trang) |
| GET | /images/{image_id} | Khách | Ảnh phòng đã duyệt, đọc từ MinIO `public-src` khi ảnh chưa có `public_url` trên Blob; ảnh bị từ chối trả 404 |
| GET | /files/signed?token=... | Người có link | Trả file CCCD hoặc hợp đồng GIẢ từ bucket `private`; link do api cấp, hạn 5 phút |
| PUT | /rooms/{id}/review | Sinh viên | Tạo hoặc sửa đánh giá của mình |
| POST | /reports | Sinh viên | Báo cáo phòng/đánh giá |
| GET, PUT, DELETE | /favorites, /favorites/{room_id} | Sinh viên | Yêu thích |
| POST | /bookings | Sinh viên | Đặt lịch |
| GET | /bookings | Sinh viên, Chủ trọ | Lịch của tôi (chủ trọ: lịch các phòng của mình); lọc `status`; lịch `confirmed` kèm liên hệ hai bên (mục 9.3) |
| POST | /bookings/{id}/confirm, /decline, /cancel, /done | Theo mục 9.3 | Chuyển trạng thái |

**Chủ trọ** (tiền tố `/landlord`, chỉ dữ liệu của chính mình)

| Method | Path | Mô tả |
|---|---|---|
| GET, POST | /houses | Danh sách, tạo nhà |
| GET, PATCH, DELETE | /houses/{id} | Chi tiết, sửa, xóa (chỉ khi không còn phòng có khách) |
| GET, POST | /rooms | Danh sách (lọc theo nhà, trạng thái), tạo phòng |
| GET, PATCH | /rooms/{id} | Chi tiết đầy đủ, sửa (kèm `amenities`, `cost_rates`) |
| POST | /rooms/{id}/submit, /hide, /unhide | Chuyển trạng thái |
| POST | /rooms/{id}/images | Tải ảnh (multipart, JPEG/PNG ≤ 5 MB, tối đa 10 ảnh) |
| DELETE | /rooms/{id}/images/{image_id} | Xóa ảnh |
| GET, POST | /tenants | Khách thuê (S) |
| PATCH | /tenants/{id} | Sửa, kết thúc thuê (S) |
| POST | /tenants/{id}/files | Tải CCCD/hợp đồng GIẢ vào bucket private (S) |
| GET | /tenants/{id}/files/{kind} | `kind` là `id_card` hoặc `contract`; trả link `/api/v1/files/signed?token=...` hạn 5 phút (S) |
| GET, POST | /meter-readings | Xem chỉ số đã nhập (lọc `room_id`), nhập chỉ số tháng (S) |
| POST | /invoices/generate | Body `{"month":"2026-10"}`: tạo hóa đơn cho mọi khách đang thuê (S) |
| GET | /invoices | Lọc `month`, `status` (S) |
| POST | /invoices/{id}/paid | Đánh dấu đã trả (S) |

**Quản trị** (tiền tố `/admin`)

| Method | Path | Mô tả |
|---|---|---|
| GET | /rooms?status=pending | Tin theo trạng thái (mặc định `pending`), kèm ảnh; thêm `pending_images=true` để lấy phòng có ảnh mới chờ duyệt |
| POST | /rooms/{id}/approve | Duyệt `pending` → `published`; với phòng `published` chỉ duyệt ảnh mới. Body `{"image_ids_ok":[...]}` tùy chọn: ảnh không có trong danh sách bị từ chối; không gửi body thì duyệt mọi ảnh chờ |
| POST | /rooms/{id}/reject | Body `{"reason":"..."}`; dùng cho phòng `pending`, hoặc gỡ phòng `published` |
| GET | /landlords | Danh sách chủ trọ để xác minh |
| POST | /landlords/{id}/verify, /unverify | Nhãn đã xác minh |
| GET | /reports | Danh sách báo cáo |
| POST | /reports/{id}/resolve | Body `{"action": "resolve", "hide_review": false}`; `action` là `resolve` hoặc `dismiss`; `hide_review: true` ẩn đánh giá bị báo cáo |
| GET | /system/status | Trạng thái (10.4) |
| POST | /sync/resync | Body `{"room_id": "..."}` hoặc `{}` = mọi phòng công khai |
| POST | /backup/run | Tạo dòng `job_runs(job='backup', status='queued')`, trả `202` kèm `job_run_id`; worker chạy `backup.sh` |
| POST | /backup/restore-test | Tạo dòng `job_runs(job='restore_test', status='queued')`, trả `202` kèm `job_run_id` |
| GET | /jobs/{id} | Kết quả một lần chạy |

**Hạ tầng**

| Method | Path | Mô tả |
|---|---|---|
| GET | /health | Không cần đăng nhập: `{"status":"ok","db":true,"minio":true}`; trả 503 nếu DB hỏng |

### 10.3 Tìm phòng – tham số và ví dụ

| Tham số | Kiểu | Ý nghĩa |
|---|---|---|
| `q` | chuỗi | Từ khóa (tiêu đề, mô tả, đường, phường, khu vực) |
| `price_min`, `price_max` | số nguyên | Giá phòng |
| `cost_max` | số nguyên | Chi phí ước tính tối đa (`est_monthly_cost`) |
| `area_min` | số | Diện tích tối thiểu |
| `area` | chuỗi, lặp được | Khu vực, vd `area=Cầu Giấy&area=Mai Dịch` |
| `amenities` | chuỗi, lặp được | Phải có **tất cả** |
| `no_curfew` | bool | Chỉ phòng giờ giấc tự do |
| `people` | số nguyên | `max_people ≥ people` |
| `school_id` + `max_distance_m` | uuid + số | Lọc theo khoảng cách tới trường |
| `verified_only` | bool | Chỉ chủ trọ đã xác minh |
| `sort` | `relevance`, `price_asc`, `price_desc`, `cost_asc`, `distance_asc`, `rating_desc`, `newest` | `distance_asc` cần `school_id` |
| `page`, `page_size` | số nguyên | Phân trang |

```
GET /api/v1/search/rooms?q=gác lửng&price_max=3500000&amenities=dieu_hoa&school_id=<uuid>&max_distance_m=2000&sort=distance_asc
```

```json
{
  "items": [
    {
      "id": "<uuid>",
      "title": "Phòng có gác lửng 22.5m² gần Xuân Thủy",
      "price_month": 3200000,
      "est_monthly_cost": 3930000,
      "area_m2": 22.5,
      "area": "Cầu Giấy",
      "ward": "Phường Dịch Vọng",
      "street": "Xuân Thủy",
      "lat": 21.0391, "lng": 105.7867,
      "distance_m": 512,
      "amenities": ["dieu_hoa", "gac_lung", "nong_lanh"],
      "curfew": false,
      "rating_avg": 4.5, "rating_count": 2,
      "landlord_verified": true,
      "thumbnail_url": "https://stphongtroxx.blob.core.windows.net/public-images/rooms/<id>/<image_id>.jpg"
    }
  ],
  "page": 1, "page_size": 20, "total": 7,
  "facets": { "area": [{"value": "Cầu Giấy", "count": 5}], "amenities": [{"value": "wifi", "count": 6}] }
}
```

Header trả về: `X-Search-Source: azure` hoặc `db`.

`thumbnail_url` là URL Blob khi ảnh đã đồng bộ; ảnh chưa đồng bộ thì là `/api/v1/images/{image_id}`.

### 10.4 Ví dụ các API khác

**Đăng ký, đăng nhập**

```json
POST /api/v1/auth/register
{ "email": "sv@example.com", "password": "≥8 ký tự", "full_name": "Nguyễn Văn A", "phone": "0000000999", "role": "student" }
→ 201 { "id": "...", "email": "sv@example.com", "role": "student" }

POST /api/v1/auth/login
{ "email": "sv@example.com", "password": "..." }
→ 200 { "access_token": "<JWT>", "token_type": "bearer", "expires_in": 43200, "user": { "id": "...", "role": "student", "full_name": "..." } }
```

**Chi phí thực tế**

```json
GET /api/v1/rooms/{id}/cost?kwh=120&m3=5&people=2&vehicles=1
→ 200 {
  "inputs": { "kwh": 120, "m3": 5, "people": 2, "vehicles": 1 },
  "lines": [
    { "code": "rent",        "label": "Tiền phòng",       "amount": 3400000 },
    { "code": "electricity", "label": "Điện (120 kWh × 3.500đ)", "amount": 420000 },
    { "code": "water",       "label": "Nước (2 người × 70.000đ)", "amount": 140000 },
    { "code": "internet",    "label": "Internet",         "amount": 50000 },
    { "code": "parking",     "label": "Gửi xe (1 xe)",     "amount": 150000 },
    { "code": "service",     "label": "Dịch vụ",          "amount": 50000 }
  ],
  "total": 4210000
}
```

**So sánh**

```json
POST /api/v1/rooms/compare
{ "ids": ["<a>", "<b>", "<c>"], "school_id": "<uuid>" }
→ 200 { "rooms": [ { "id": "<a>", "title": "...", "price_month": 3200000, "est_monthly_cost": 3930000,
                    "area_m2": 22.5, "distance_m": 512, "amenities": [...], "curfew": false,
                    "rating_avg": 4.5, "landlord_verified": true } , ... ],
        "best": { "price_month": "<a>", "est_monthly_cost": "<a>", "area_m2": "<c>", "distance_m": "<a>", "rating_avg": "<b>" } }
```

**Đặt lịch xem phòng**

```json
POST /api/v1/bookings
{ "room_id": "<uuid>", "slot_start": "2026-11-21T16:00:00+07:00", "student_note": "Em đi cùng bạn" }
→ 201 { "id": "...", "status": "requested", ... }
→ 409 { "error": { "code": "BOOKING_CONFLICT", ... } }
```

**Chủ trọ tạo phòng**

```json
POST /api/v1/landlord/rooms
{ "house_id": "<uuid>", "title": "Phòng khép kín 20m²", "description": "...", "price_month": 3000000,
  "deposit_amount": 3000000, "area_m2": 20, "floor": 3, "max_people": 2, "curfew_time": null,
  "available_from": "2026-12-01", "amenities": ["dieu_hoa", "nong_lanh", "ve_sinh_rieng"],
  "cost_rates": { "electricity_per_kwh": 3800, "water_mode": "per_m3", "water_per_m3": 30000,
                  "water_per_person": 0, "internet_per_month": 50000, "parking_per_vehicle": 100000,
                  "service_per_month": 30000 } }
→ 201 { "id": "...", "status": "draft", "version": 1, ... }
```

**Trạng thái hệ thống (quản trị)**

```json
GET /api/v1/admin/system/status
→ 200 {
  "db": true, "minio": true, "azure_search_reachable": true,
  "outbox": { "pending": 0, "failed": 1, "last_sent_at": "2026-11-20T09:15:02+07:00" },
  "queue": { "last_message_at": "2026-11-20T08:00:03+07:00" },
  "backup": { "last_success_at": "2026-11-20T02:00:41+07:00", "size_bytes": 30944, "duration_ms": 606 },
  "restore_test": { "last_at": "2026-11-20T09:30:00+07:00", "total_ms": 1018, "counts_match": true },
  "search_fallback_last_hour": 0,
  "outbox_failed_rows": [ { "id": 12, "room_id": "...", "op": "upsert", "attempts": 10, "last_error": "...", "created_at": "..." } ],
  "recent_jobs": [ "... 15 lần chạy gần nhất trong job_runs ..." ]
}
```

---

## 11. Tích hợp Azure

### 11.1 Function `ingest-room` (HTTP, Người 5)

- Route `POST /api/ingest-room`, xác thực bằng khóa hàm (header `x-functions-key`).
- Thân:

```json
{ "op": "upsert", "room": { "id": "...", "version": 7, "title": "...", "...": "chỉ các trường ở mục 4" } }
{ "op": "delete", "room": { "id": "...", "version": 8 } }
```

- Xử lý:
  1. Có trường ngoài danh sách cho phép → `400 FIELD_NOT_ALLOWED` kèm tên trường (không ghi gì).
  2. Đọc tài liệu hiện có theo `id`; nếu `version` hiện có ≥ `version` gửi đến → `200 {"status":"skipped"}` (idempotent).
  3. `upsert` → `merge_or_upload_documents`; `delete` → `delete_documents`.
  4. Trả `200 {"status":"ok"}`. Lỗi AI Search → `502`, worker sẽ thử lại.
- Phản hồi lỗi khác: JSON hỏng → `400 INVALID_JSON`; thiếu `op`, `room.id` hoặc `room.version` → `400 INVALID_BODY`; thiếu hoặc sai khóa hàm → `401`. Thân lỗi dạng `{"error": "FIELD_NOT_ALLOWED", "fields": ["phone"]}`.
- `location` gửi dạng GeoJSON: `{"type":"Point","coordinates":[lng, lat]}`.
- Khóa admin của AI Search lấy từ app setting tham chiếu Key Vault, không nằm trong code.

### 11.2 Chỉ mục `rooms-public`

Định nghĩa trong `azure-functions/search-index.json` (24 trường). Trường văn bản tiếng Việt dùng analyzer `vi.microsoft`. Tạo chỉ mục: khối 3 của `infra/azure/setup.sh`, hoặc

```
curl -X PUT "https://<search>.search.windows.net/indexes/rooms-public?api-version=2024-07-01" \
  -H "Content-Type: application/json" -H "api-key: <ADMIN_KEY>" --data-binary @azure-functions/search-index.json
```

Đổi kiểu một trường đã có phải xóa và tạo lại chỉ mục, rồi đồng bộ lại toàn bộ (`POST /admin/sync/resync {}`).

### 11.3 Dịch tham số tìm kiếm sang AI Search

| Tham số | Biểu thức |
|---|---|
| `q` | `search=<q>`, `searchFields=title,description,street,ward,area`; không có `q` → `search=*` |
| `price_min/max` | `price_month ge X and price_month le Y` |
| `cost_max` | `est_monthly_cost le X` |
| `area_min` | `area_m2 ge X` |
| `area` (nhiều) | `search.in(area, 'Cầu Giấy|Mai Dịch', '|')` |
| `amenities` (nhiều) | `amenities/any(a: a eq 'dieu_hoa') and amenities/any(a: a eq 'wifi')` |
| `no_curfew` | `curfew eq false` |
| `people` | `max_people ge N` |
| `school_id` + `max_distance_m` | `geo.distance(location, geography'POINT(<lng> <lat>)') le <km>` (đơn vị **km**) |
| `verified_only` | `landlord_verified eq true` |
| `sort=distance_asc` | `$orderby=geo.distance(location, geography'POINT(<lng> <lat>)') asc` |
| `sort=price_asc` / `cost_asc` / `rating_desc` / `newest` | `price_month asc` / `est_monthly_cost asc` / `rating_avg desc` / `updated_at desc` |
| facets | `facets=area,count:10&facets=amenities,count:20` |

Chú ý: trong `POINT(...)` kinh độ đứng trước vĩ độ. Chuỗi trong OData bao bằng dấu nháy đơn; nháy đơn trong giá trị phải nhân đôi.

**Tìm kiếm dự phòng** dùng cùng bộ lọc trên `v_rooms_public` (`ILIKE` cho `q`, `@>` cho tiện nghi, `distance_m()` cho khoảng cách) và trả cùng định dạng (không có `facets` thì trả mảng rỗng).

### 11.4 Function Timer `daily-ticks-*` và hàng đợi `ops-ticks`

Lịch NCRONTAB tính theo **UTC** (UTC+7 trừ 7 giờ):

| Hàm | Lịch | Giờ Việt Nam | Tin đưa vào hàng đợi |
|---|---|---|---|
| `daily-ticks-morning` | `0 0 1 * * *` | 08:00 | `viewing_reminder`, `invoice_due_check`, `contract_expiring` |
| `daily-ticks-backup` | `0 0 19 * * *` | 02:00 | `daily_backup` (dự phòng nếu cron trên vm-data hỏng) |

Mỗi hàm Timer chỉ khai báo được một lịch, nên hai lịch là hai hàm dùng chung một hàm phụ đưa tin. Function ghi hàng đợi bằng chuỗi kết nối `AzureWebJobsStorage` (cùng tài khoản `stphongtro<SUFFIX>`).

Định dạng tin (JSON thuần, ghi bằng `QueueClient` của SDK, không mã hóa base64):

```json
{ "id": "3f6c...-uuid", "type": "viewing_reminder", "at": "2026-11-21T01:00:00Z" }
```

Để demo không phải chờ đến 8 giờ: Function có thêm route HTTP `POST /api/tick-now?type=viewing_reminder` (khóa hàm) đưa ngay một tin vào hàng đợi. `type` chỉ nhận `viewing_reminder`, `invoice_due_check`, `contract_expiring`, `daily_backup`; sai thì `400 INVALID_TYPE`. Thành công trả `{"status": "queued", "type": "...", "id": "..."}`.

### 11.5 Azure Maps

- Web SDK hiển thị bản đồ, ghim phòng, vòng tròn bán kính quanh trường.
- Geocode địa chỉ khi chủ trọ nhập (Search Address API); thử sớm với địa chỉ ngõ, hẹp ở Việt Nam, nếu kém chính xác thì cho kéo ghim.
- Khóa Maps nằm trong trình duyệt nên dùng khóa riêng cho Maps, không dùng chung với dịch vụ khác. Nếu có thời gian, chuyển sang xác thực bằng token ngắn hạn do api cấp.

---

## 12. Worker

### 12.1 Vòng lặp

| Việc | Chu kỳ | Mô tả |
|---|---|---|
| Outbox | `OUTBOX_POLL_SECONDS` (5 s) | Gửi thay đổi sang Azure (12.2) |
| Hàng đợi | `QUEUE_POLL_SECONDS` (30 s) | Nhận tín hiệu hẹn giờ (12.3) |
| Telegram `getUpdates` | 30 s | Liên kết tài khoản (mục 3F) |
| Lệnh quản trị | 5 s | Lấy dòng `job_runs` có `status='queued'` (do `POST /admin/backup/*` tạo), chạy `backup.sh` hoặc `restore-test.sh` với `JOB_RUN_ID=<id>` để kết quả ghi đúng dòng đó |
| Heartbeat | 60 s | Số đo `worker_heartbeat` |

Mỗi việc bọc trong `try/except`, lỗi một việc không làm dừng việc khác.

- Khi `AZURE_FUNCTION_KEY` trống hoặc còn `CHANGE_ME`, vòng outbox tạm dừng và ghi một dòng cảnh báo, không tăng `attempts` của dòng nào.
- Tin `daily_backup` tạo dòng `job_runs(job='backup', status='queued')` để vòng lệnh quản trị chạy `backup.sh`. Ràng buộc `job_runs.job` không có giá trị `daily_backup`.
- Trong gói `worker`, file `queue.py` import dạng `from . import queue as ops_queue`, không `import queue` (trùng tên thư viện chuẩn).

### 12.2 Thuật toán outbox

```sql
-- Lấy tối đa 10 dòng đến hạn, khóa để không xử lý trùng nếu chạy nhiều worker
SELECT id, entity_id, op FROM sync_outbox
WHERE status = 'pending' AND next_attempt_at <= now()
ORDER BY id LIMIT 10
FOR UPDATE SKIP LOCKED;
```

Với mỗi dòng:

1. Nếu có dòng `pending` mới hơn cho cùng `entity_id` → đánh dấu dòng này `sent` (bị thay thế) và bỏ qua.
2. Đọc `v_rooms_public` theo `entity_id`. Không thấy hoặc `status <> 'published'` → `op = delete`.
3. `upsert`: với mỗi ảnh chưa có `public_url`, đọc từ MinIO `public-src`, tải lên Blob `public-images/rooms/<room_id>/<image_id>.jpg`, lưu `public_url`. Tính `est_monthly_cost`. Dựng tài liệu đúng danh sách trường mục 4.
4. `delete`: xóa blob tiền tố `rooms/<room_id>/`.
5. Gọi `ingest-room`. Thành công → `status='sent', sent_at=now()`.
6. Lỗi → `attempts += 1`, `last_error`, `next_attempt_at = now() + min(30 s × 2^attempts, 30 phút)`. Khi `attempts ≥ OUTBOX_MAX_ATTEMPTS` → `failed` (hiện ở trang trạng thái, nút đồng bộ lại đặt về `pending, attempts=0`).

| Lần thử | 1 | 2 | 3 | 4 | 5 | 6 trở đi |
|---|---|---|---|---|---|---|
| Chờ trước lần sau | 1 phút | 2 phút | 4 phút | 8 phút | 16 phút | 30 phút |

### 12.3 Xử lý hàng đợi

1. `receive_messages(max_messages=16, visibility_timeout=300)`.
2. Có `id` trong `processed_messages` → xóa tin, bỏ qua.
3. Chạy việc theo `type`, ghi `job_runs`.
4. Thành công → chèn `processed_messages`, xóa tin. Lỗi → không xóa; tin hiện lại sau 5 phút để thử lại.

### 12.4 Nội dung thông báo

| Việc | Gửi cho | Nội dung mẫu |
|---|---|---|
| `viewing_reminder` | Sinh viên và chủ trọ của lịch | "Nhắc lịch xem phòng: <tiêu đề phòng>, 16:00 ngày 21/11." |
| `invoice_due_check` | Chủ trọ | "Có 2 hóa đơn quá hạn: HD-202610-0003, HD-202610-0007." |
| `contract_expiring` | Chủ trọ | "Hợp đồng phòng <tiêu đề> hết hạn ngày 15/12/2026." |
| Liên kết Telegram | Người dùng | "Đã liên kết tài khoản phòng trọ." |

Không đưa số điện thoại, CCCD hay địa chỉ chi tiết vào tin nhắn. Người chưa liên kết Telegram thì bỏ qua (ghi nhật ký mức info, không kèm dữ liệu cá nhân).

---

## 13. Hạ tầng OpenStack (Người 2, tiếp nhận từ Người 4)

Script: `infra/openstack/setup.sh` (chạy lại được nhiều lần). Mặc định:

| Tài nguyên | Giá trị |
|---|---|
| Project | `phongtro` |
| Image | `ubuntu-24.04` (noble cloud image) |
| Flavor | `pt.small`: 2 vCPU, 3 GB RAM, 20 GB đĩa |
| Mạng | `net-phongtro`, subnet `10.20.0.0/24`, DNS 8.8.8.8, router `r-phongtro` ra mạng `public` |
| Security group | `sg-app`: vào 80, 443 mọi nơi; 22 và ICMP từ `ADMIN_CIDR`. `sg-data`: vào 5432, 9000, 22 **chỉ từ sg-app** |
| VM | `vm-app` (sg-app, có floating IP), `vm-data` (sg-data, không có floating IP) |
| Volume | `vol-data` 20 GB gắn vào `vm-data`, mount `/srv/data` |
| Snapshot | `openstack volume snapshot create --volume vol-data --force snap-vol-data-<ngày>` mỗi tối và trước mỗi lần demo |

**Máy host:** cần tối thiểu 16 GB RAM cho DevStack và 2 VM 3 GB. Chạy liên tục đến 30/11, tắt chế độ ngủ, sao lưu ảnh đĩa máy host sau khi dựng xong (DevStack không đảm bảo bền qua khởi động lại; ghi lại các bước khôi phục nếu phải `./stack.sh` lại). DevStack ban đầu chạy trong máy ảo VirtualBox `devstack` trên máy Người 4 (Ubuntu Server 24.04, nhánh `stable/2026.1`, mạng NAT, chuyển tiếp cổng 2222 cho SSH và 8080 cho Horizon). Người 2 ghi lại máy chạy DevStack mới vào đây khi chốt.

**Lỗi đã gặp (13/11):** cả hai VM hỏng ở bước cloud-init vì VM không ra được Internet nên không cài được gói. Trước khi tạo VM, kiểm tra NAT cho dải floating IP (MASQUERADE cho `172.24.4.0/24`) và thử `ping`/`apt update` từ một VM thử. Nếu máy host thiếu RAM, giảm `pt.small` xuống 2 GB. Phương án dự phòng (một VM chạy cả web và dữ liệu) quyết ở mốc 19/11.

**Truy cập cho cả nhóm:** floating IP của DevStack mặc định chỉ thấy từ máy host DevStack. Đã chốt dùng Tailscale (mục 23; ngày 14/11 chưa ai cài): cài Tailscale trên máy host chạy DevStack và quảng bá dải floating IP (subnet router), ví dụ `tailscale up --advertise-routes=172.24.4.0/24` rồi duyệt route trong trang quản trị Tailscale; các bạn khác cài Tailscale là vào được `http://<floating-ip>`. Kiểm tra lại cú pháp với tài liệu Tailscale hiện hành.

**Triển khai:**

```
# vm-data
git clone <repo> && cd phongtro && cp .env.example .env   # DATA_DIR=/srv/data
docker compose up -d db minio
# vm-app
git clone <repo> && cd phongtro && cp .env.example .env   # DB_HOST, MINIO_ENDPOINT = IP nội bộ vm-data
docker compose up -d --build api worker web
```

sg-app chỉ mở 80/443, không mở 8000: mọi request vào api phải đi qua nginx của web (mục 19). Dịch vụ `worker` trong `docker-compose.yml` do Người 6 bật khi xong khung worker.

Cron trên vm-data: `0 2 * * * cd /home/ubuntu/phongtro && set -a && . ./.env && set +a && scripts/backup.sh >> /var/log/phongtro-backup.log 2>&1`

---

## 14. Hạ tầng Azure (Người 5)

Script: `infra/azure/setup.sh` (chạy từng khối, kiểm tra trên portal). **Đặt Budget trên portal trước tiên.**

| Tài nguyên | Tên | Ghi chú |
|---|---|---|
| Resource group | `rg-phongtro` | Vùng `eastasia` cho mọi tài nguyên (đã chốt, mục 23), trừ Maps |
| Storage account | `stphongtro<SUFFIX>` | Container `public-images` (đọc công khai), `backups` (riêng tư); queue `ops-ticks` |
| AI Search | `srch-phongtro-<SUFFIX>` | Gói Free; chỉ mục `rooms-public` |
| Maps | `maps-phongtro-<SUFFIX>` | Gói G2, vùng `global` (Maps không tạo được ở `eastasia`) |
| Key Vault | `kv-phongtro-<SUFFIX>` | Phân quyền bằng **access policy** (không phải RBAC); cấp quyền bằng `az keyvault set-policy` |
| Application Insights | `appi-phongtro` | |
| Function App | `func-phongtro-<SUFFIX>` | Python 3.11, gói Flex Consumption (FC1); managed identity đã bật, có access policy `get` trên Key Vault |
| Logic App | `logic-phongtro-alerts` | Nhận cảnh báo, gửi Telegram nhóm quản trị |
| Budget | `budget-phongtro` | US$30/tháng, cảnh báo ở 50%, 80%, 100% |

### Bí mật trong Key Vault

| Tên bí mật | Dùng ở | Ghi chú |
|---|---|---|
| `backup-passphrase` | backup.sh, restore-test.sh | Chép một bản vào `.env` của vm-data |
| `search-admin-key` | Function `ingest-room` | Chỉ Function dùng; VM chỉ có khóa truy vấn |
| `function-key` | worker | Khóa của `ingest-room` |
| `telegram-bot-token` | worker, Logic App | |
| `azure-maps-key` | web (qua api `/config`) | Bản gốc của `AZURE_MAPS_KEY` |

Quyền trên Key Vault (access policy) ngày 14/11: người tạo vault (toàn quyền), nhóm trưởng (get, list, set), Function App (get). Thêm người: `az keyvault set-policy -n kv-phongtro-<SUFFIX> --object-id <object-id> --secret-permissions get list`. Gán role RBAC không có tác dụng trên vault này.

`infra/azure/setup.sh` (bản v0.4) đã khớp với tài nguyên thật: mặc định `LOC=eastasia`; tạo Key Vault với `--enable-rbac-authorization false` và cấp quyền bằng access policy; bật managed identity cho Function và cấp `get`; lưu `azure-maps-key`; in danh sách app settings để kiểm. Script dừng nếu `.env.azure` đã có nội dung (tránh sinh passphrase sao lưu mới), trừ khi đặt `FORCE=1`.

Giới hạn đã biết (ghi vào báo cáo): vm-data giữ một bản `BACKUP_PASSPHRASE` trong `.env`; hệ thống thật nên dùng danh tính được quản lý thay cho khóa chép tay.

**Dọn dẹp sau khi quay video:** `az group delete -n rg-phongtro` (sau khi đã chụp đủ hình cho báo cáo).

---

## 15. Biến môi trường

Mẫu đầy đủ trong `.env.example`. `.env` và `.env.*` bị `.gitignore` chặn.

| Biến | Dùng ở | Bí mật | Mô tả |
|---|---|:-:|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` | api, worker, scripts | | Kết nối PostgreSQL |
| `DB_PASSWORD` | db, api, worker, scripts | ✓ | |
| `MINIO_ENDPOINT`, `MINIO_BUCKET_*` | api, worker | | |
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | minio, api, worker | ✓ | |
| `MC_ALIAS` | backup.sh | | Alias MinIO Client |
| `JWT_SECRET`, `JWT_EXPIRE_MINUTES` | api | ✓ / | |
| `SEED_DEMO_PASSWORD` | api (seed_passwords) | ✓ | Mật khẩu tài khoản demo |
| `EST_KWH_PER_MONTH`, `EST_WATER_M3_PER_MONTH`, `EST_PEOPLE`, `EST_VEHICLES` | api, worker | | Giá trị mặc định cho chi phí |
| `SEARCH_TIMEOUT_MS` | api | | Quá giờ → tìm bằng DB |
| `CORS_ORIGINS` | api | | Để trống khi web và api cùng nguồn qua nginx; khi dev tách cổng ghi vd `http://localhost:5173` |
| `REVIEW_SKIP_BOOKING_CHECK` | api | | `true` cho đánh giá không cần lịch `done` (chỉ để demo, mục 9.4) |
| `FORWARDED_ALLOW_IPS` | api | | Dải mạng tin cậy gửi `X-Forwarded-For` (nginx); mặc định các dải nội bộ |
| `OUTBOX_POLL_SECONDS`, `QUEUE_POLL_SECONDS`, `OUTBOX_MAX_ATTEMPTS` | worker | | |
| `AZURE_FUNCTION_INGEST_URL` | worker | | `https://func-phongtro-<SUFFIX>.azurewebsites.net/api/ingest-room` |
| `AZURE_FUNCTION_KEY` | worker | ✓ | |
| `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_INDEX` | api | | |
| `AZURE_SEARCH_QUERY_KEY` | api | ✓ | Chỉ đọc |
| `AZURE_MAPS_KEY` | web (qua api `/config`) | ✓* | Lộ ra trình duyệt, chỉ cho Maps |
| `AZURE_STORAGE_CONNECTION_STRING` | worker | ✓ | Blob ảnh công khai, hàng đợi |
| `AZURE_QUEUE_NAME`, `AZURE_BLOB_PUBLIC_BASE_URL` | worker, api | | |
| `AZURE_BACKUP_CONTAINER_URL` | scripts | | |
| `AZURE_BACKUP_SAS_WRITE`, `AZURE_BACKUP_SAS_READ` | backup.sh / restore-test.sh | ✓ | Tách quyền ghi và đọc |
| `BACKUP_PASSPHRASE`, `BACKUP_DIR`, `KEEP_LOCAL` | scripts | ✓ / | |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | api, worker | ✓ | |
| `TELEGRAM_BOT_NAME` | api (qua `/config`), worker | | Tên đăng nhập của bot, không có `@`; giá trị `easyrent2006_bot` |
| `TELEGRAM_BOT_TOKEN` | worker | ✓ | |

`.env.example` bản v0.4 đã bỏ bốn biến `CONTENT_SAFETY_*`, `DOC_INTELLIGENCE_*` (F18–F22 đã bỏ), thêm `MINIO_SECURE`, ba biến của web ở trên, và điền sẵn `TELEGRAM_BOT_NAME=easyrent2006_bot`.

---

## 16. Sao lưu và khôi phục (F13)

| Mục | Giá trị |
|---|---|
| Lịch | 02:00 hằng ngày (cron trên vm-data); Function Timer gửi `daily_backup` làm dự phòng |
| Nội dung | `db.dump` (`pg_dump -Fc`), thư mục MinIO `private`, `public-src` (nếu cấu hình `mc`), `manifest.json` (số dòng 9 bảng chính, SHA-256) |
| Mã hóa | `openssl enc -aes-256-cbc -pbkdf2 -iter 200000`, khóa `BACKUP_PASSPHRASE` (gốc ở Key Vault) |
| Nơi lưu | Blob `backups/<YYYY>/<MM>/phongtro-<YYYYMMDDTHHMMSSZ>.tar.gz.enc`; 3 bản gần nhất ở `/var/backups/phongtro` |
| Quyền | Ghi bằng SAS `cw` (không đọc, không xóa); khôi phục bằng SAS `rl` |
| Giữ lại | 14 ngày (quy tắc vòng đời Blob, đặt trên portal) |
| RPO | Tối đa 24 giờ (một bản mỗi ngày); trước demo chạy thêm một bản |
| RTO | Đo bằng `restore-test.sh`, ghi `job_runs.details.total_ms`; đưa con số vào báo cáo |

Đã chạy thử ở chế độ `DRY_RUN=1` với dữ liệu mẫu: bản sao lưu khoảng 30 KB, khôi phục và đối chiếu 9 bảng khớp hoàn toàn trong khoảng 1 giây; sai khóa giải mã thì dừng với mã lỗi.

Kịch bản demo: (1) bấm "Sao lưu ngay" ở trang quản trị, (2) mở Azure portal thấy file mới trong `backups`, (3) bấm "Khôi phục thử", (4) trang hiện bảng đối chiếu số dòng và thời gian.

---

## 17. Giám sát và cảnh báo (F15)

| Số đo | Nguồn | Ý nghĩa |
|---|---|---|
| Thời gian phản hồi, số lỗi 5xx theo route | api (OpenTelemetry tự động) | Hiệu năng |
| `search_fallback_count` | api | Số lần tìm bằng DB vì Azure lỗi |
| `sync_sent`, `sync_failures`, `outbox_pending` | worker | Sức khỏe đồng bộ |
| `backup_success`, `backup_duration_ms`, `restore_test_ms` | worker | Sao lưu |
| `worker_heartbeat` | worker | Worker còn sống |

| Quy tắc cảnh báo | Điều kiện |
|---|---|
| Đồng bộ lỗi | `sync_failures` > 0 trong 15 phút |
| Worker chết | Không có `worker_heartbeat` trong 5 phút |
| Sao lưu trễ | Không có `backup_success` trong 26 giờ |
| api lỗi nhiều | Tỷ lệ 5xx > 5% trong 5 phút |
| Chi phí | Budget đạt 50%, 80%, 100% |

Tất cả gửi qua Action Group → Logic App → Telegram nhóm quản trị (hoặc email). Không đưa dữ liệu cá nhân vào số đo hay nhật ký.

---

## 18. Dữ liệu mẫu

- Sinh bằng `python3 seed/generate_seed.py --rooms 80 > seed/seed.sql` (tái lập được; đổi `--seed` để ra bộ khác). Docker Compose tự nạp khi CSDL trống.
- Kết quả mặc định: 2 trường, 11 tài khoản, 16 nhà, 80 phòng (65 công khai), 43 đánh giá, 8 lịch xem, 12 khách thuê, 36 chỉ số, 24 hóa đơn, 65 dòng outbox chờ đồng bộ lần đầu.
- Tài khoản demo: `admin@example.com`, `chutro1..4@example.com` (1, 2 đã xác minh), `sinhvien1..6@example.com`. Mật khẩu đặt bằng `python -m app.seed_passwords` từ `SEED_DEMO_PASSWORD`.
- Toàn bộ là dữ liệu giả: số điện thoại dạng `0000000xxx`, email `@example.com`, đường dẫn CCCD/hợp đồng trỏ tới file giả. Tọa độ trường là gần đúng (chốt danh sách trường ngày 13/11).
- Ảnh phòng: tự chụp, ảnh có giấy phép cho phép dùng lại, hoặc ảnh minh họa tự tạo; ghi nguồn trong `docs/`. Không lấy ảnh từ trang đăng tin khác.
- Người 1 bổ sung mô tả cho phong phú (giữ nguyên cấu trúc bảng).
- Seed không có ảnh phòng. `pytest` của backend tạo thêm dữ liệu thử mỗi lần chạy, nên trước khi demo hoặc quay video phải nạp lại dữ liệu sạch (`LUU-Y.md` mục 7).

---

## 19. Bảo mật

- Mật khẩu băm argon2/bcrypt; tối thiểu 8 ký tự. JWT hết hạn sau `JWT_EXPIRE_MINUTES`.
- Kiểm tra vai trò **và** quyền sở hữu ở mọi API (mục 7).
- Giới hạn tần suất `/auth/login`: 10 lần/phút/IP.
- Tải file: kiểm tra loại MIME và kích thước; tên đối tượng do server sinh (uuid), không dùng tên người dùng gửi.
- File trong bucket `private` chỉ truy cập qua link ký trước, hạn 5 phút, chỉ chủ trọ sở hữu xem được. api cấp link `/api/v1/files/signed?token=...` vì URL ký của MinIO trỏ vào IP nội bộ.
- CORS mặc định không mở (`CORS_ORIGINS` trống) vì web và api cùng nguồn qua nginx. Không bật `debug` trên VM.
- Trên VM, api chỉ nhận request qua nginx (sg-app không mở 8000). api tin header `X-Forwarded-For` từ dải `FORWARDED_ALLOW_IPS`; nếu api bị gọi thẳng, người dùng có thể giả IP để vượt giới hạn đăng nhập.
- Giới hạn đăng nhập lưu trong bộ nhớ của tiến trình, nên api chạy `--workers 1`.
- Trên VM thật tạo lại `JWT_SECRET` (`openssl rand -hex 32`), `DB_PASSWORD`, `MINIO_ROOT_PASSWORD`, `SEED_DEMO_PASSWORD`; không dùng lại giá trị ở máy cá nhân.
- Soát mã AI sinh ra: không mật khẩu cứng, không bỏ kiểm tra quyền, không SQL ghép chuỗi, không ghi dữ liệu cá nhân vào log.
- Che khóa, token, mật khẩu khi chụp màn hình và quay video.

---

## 20. Quy ước làm việc

- Git: `main` luôn chạy được; nhánh `feature/<mô-đun>-<việc>` (vd `feature/api-bookings`); commit nhỏ, mỗi ngày; gộp vào `main` qua pull request, một người khác xem nhanh.
- Thông điệp commit: `<mô-đun>: <việc>` (vd `api: thêm POST /bookings và kiểm tra trùng lịch`).
- Đặt tên: bảng, cột, trường JSON `snake_case`; biến môi trường IN HOA; component React `PascalCase`.
- Thời gian lưu UTC, hiển thị `Asia/Ho_Chi_Minh`. Tiền hiển thị dạng `3.200.000đ`.
- Không sửa mô-đun của người khác khi chưa báo trong nhóm chat.
- Thông tin tài khoản dùng chung (Azure, OpenStack, Telegram bot) lưu ở nơi an toàn của nhóm, không trong kho mã.

### Định nghĩa "xong"

1. Chạy được trên **VM OpenStack thật** hoặc dịch vụ Azure thật, không chỉ máy cá nhân.
2. Qua các kiểm thử liên quan ở mục 22.
3. Có ảnh chụp màn hình trong `docs/` cho báo cáo.
4. Không lộ khóa, không ghi dữ liệu cá nhân vào log.
5. Người viết giải thích được: luồng dữ liệu, vì sao dùng dịch vụ đó, lỗi xử lý thế nào.

---

## 21. Mô-đun và tiêu chí nghiệm thu

| Người | Mô-đun | Chức năng | Nghiệm thu (đạt khi) | Hạn |
|---|---|---|---|---|
| 1 (Đặng Thế Đạt) | Quản lý, SPEC, dữ liệu mẫu, kiểm thử | – | SPEC chốt 13/11; seed nạp được; danh sách TC chạy đủ và ghi kết quả | 13/11, 23/11 |
| 4 (Vũ Tuấn Anh) | Backend API (đã code) | F01-F04, F06-F09, F11, F14, F16, F17 | Mọi endpoint mục 10 chạy trên VM; TC01-TC12 đạt trên VM | 23/11 |
| 3 (Nguyễn Tiến Đạt) | Frontend (đã code) | Giao diện cho F01-F09, F14 | Đi hết kịch bản demo không lỗi trên VM; dùng được trên điện thoại | 23/11 |
| 2 (Dương Hoàng Anh) | OpenStack | Hạ tầng mục 13, cron sao lưu | 16/11: `setup.sh` chạy xong, VM ra được Internet. 19/11: cả nhóm vào được web qua Tailscale; snapshot có; TC19 đạt | 16/11, 19/11 |
| 5 (Trịnh Thị Vân) | Azure, Azure Functions | Mục 11, 14, 17 | 4 hàm deploy; TC15 đạt; Timer đưa tin vào hàng đợi đúng lịch; cảnh báo kích hoạt được | 15/11, 19/11 |
| 6 (Phạm Nguyễn Thu Giang) | Worker | F10, phần chạy việc nền của F12, F13 | Vòng outbox gửi được lên Azure (TC13, TC14, TC16); hàng đợi và lệnh quản trị chạy | 15/11 outbox, 19/11 |
| 6 (Phạm Nguyễn Thu Giang) | Tích hợp, kiểm thử hai cloud | F13, F15 | TC17-TC22 đạt; có số đo thời gian đồng bộ, RTO, chi phí cho báo cáo | 23/11 |
| 1 (Đặng Thế Đạt) | Thông báo Telegram, Logic App cảnh báo | F12, mục 3F, F15 (Logic App) | Nhận được Telegram khi chạy `tick-now`; cảnh báo hệ thống tới nhóm | 21/11 |

---

## 22. Kịch bản kiểm thử

| Mã | Kịch bản | Kết quả mong đợi |
|---|---|---|
| TC01 | Đăng ký sinh viên, đăng nhập, gọi `/me` | 201, 200, đúng vai trò |
| TC02 | Sinh viên gọi `/landlord/rooms` | 403 |
| TC03 | Chủ trọ A xem phòng của chủ trọ B qua `/landlord/rooms/{id}` | 404 |
| TC04 | Tạo phòng, gửi duyệt, quản trị duyệt | Trạng thái đúng mục 9.1; `version` tăng; có dòng outbox |
| TC05 | Tìm `price_max=3000000&amenities=dieu_hoa` | Mọi kết quả thỏa cả hai điều kiện |
| TC06 | Tìm theo `school_id` + `max_distance_m=1500`, `sort=distance_asc` | Kết quả trong 1,5 km, tăng dần |
| TC07 | `/rooms/{id}/cost` với số liệu tay | Khớp tính tay theo mục 9.5 |
| TC08 | So sánh 3 phòng | Bảng đủ trường, `best` đúng |
| TC09 | Hai sinh viên đặt cùng phòng, cùng giờ | Người thứ hai nhận 409 `BOOKING_CONFLICT` |
| TC10 | Đặt lịch quá khứ hoặc quá 14 ngày | 422 |
| TC11 | Đánh giá rồi ẩn đánh giá | `rating_avg` cập nhật, outbox có dòng mới |
| TC12 | Tạo hóa đơn tháng 10 hai lần | Lần hai 409 `INVOICE_EXISTS`; số điện = chênh lệch chỉ số |
| TC13 | Duyệt một phòng mới | Tìm thấy trên Azure (header `X-Search-Source: azure`) trong 15 giây |
| TC14 | Kiểm tra tài liệu trong AI Search | Không có tên, điện thoại, email, `address_private` |
| TC15 | Gửi thử tài liệu có trường `phone` thẳng vào `ingest-room` | 400 `FIELD_NOT_ALLOWED` |
| TC16 | Chặn mạng ra của vm-app (hoặc đổi sai `AZURE_FUNCTION_INGEST_URL`), sửa 3 phòng, mở lại | Outbox giữ `pending`, thử lại tăng dần, gửi bù đủ khi mạng trở lại |
| TC17 | Tạm sai `AZURE_SEARCH_ENDPOINT` rồi tìm | Vẫn có kết quả, header `db` |
| TC18 | `tick-now?type=viewing_reminder` | Telegram nhận nhắc lịch đúng một lần, chạy lại không gửi trùng |
| TC19 | Tắt rồi bật lại vm-app, vm-data | Dịch vụ tự chạy lại (restart policy), dữ liệu còn |
| TC20 | Chạy `backup.sh` | File mới trong Blob `backups`; không đọc được khi chưa giải mã |
| TC21 | Chạy `restore-test.sh` | Bảng đối chiếu khớp; ghi thời gian khôi phục |
| TC22 | Làm hỏng đồng bộ 15 phút | Cảnh báo tới Telegram nhóm quản trị |

---

## 23. Quyết định đã chốt

- [x] Xác nhận công nghệ mục 5: Giữ nguyên React 18 (Vite + Tailwind) + FastAPI + PostgreSQL 16 + MinIO.
- [x] Danh sách trường và tọa độ chính xác cho bảng `schools`: Giữ nguyên dữ liệu trường mặc định trong `seed/seed.sql`.
- [x] Vùng Azure dùng chung: Chốt dùng **`eastasia`** cho toàn bộ tài nguyên trong `rg-phongtro`.
- [x] Người phụ trách Thông báo và AI: **Người 1 (Nhóm trưởng)** phụ trách chính phần Thông báo Telegram (F12, mục 3F: xử lý liên kết tài khoản và nhắc lịch xem phòng) và cấu hình Logic App cảnh báo hệ thống (F15).
- [x] Làm F18-F22 hay không: **Không làm F18–F22** (bỏ toàn bộ các chức năng mức C để tập trung hoàn thành chức năng mức M và S).
- [x] Giá trị `EST_*` mặc định cho chi phí thực tế: `EST_KWH_PER_MONTH=100`, `EST_WATER_M3_PER_MONTH=4`, `EST_PEOPLE=1`, `EST_VEHICLES=1`.
- [x] Cách cả nhóm truy cập OpenStack: Dùng **Tailscale** (subnet router quảng bá dải floating IP từ máy host chạy DevStack).
- [x] Nơi lưu thông tin tài khoản dùng chung: Lưu trong tài liệu nội bộ riêng của nhóm (ngoài Git); bot Telegram dùng chung là `@easyrent2006_bot`.
- [x] (14/11) Lấy backend và web đã code (repo EasyRent) làm bản chuẩn; 9 điểm bổ sung trong `LUU-Y.md` mục 5 được duyệt và đã ghi vào SPEC.
- [x] (14/11) Key Vault giữ phân quyền bằng access policy.
- [x] (14/11) Azure Maps dùng vùng `global` (ngoại lệ duy nhất của quyết định `eastasia`).
- [x] (14/11) Hai lịch Timer thành hai hàm `daily-ticks-morning`, `daily-ticks-backup`.
- [x] (14/11) Người 2 chuyển sang OpenStack; worker do Người 6; Người 1 viết phần Telegram trong worker.

---

## 24. Mốc

| Ngày | Mốc |
|---|---|
| 12/11 | Đăng ký nhóm và tổ hợp; kho mã và SPEC sẵn sàng |
| 13/11 | Mục 23 đã chốt; OpenStack có VM; mọi người chạy được `docker compose up -d db minio` với dữ liệu mẫu |
| 14/11 | Hạ tầng Azure kiểm đạt; SPEC v0.4 lấy web đã code làm chuẩn |
| 15/11 | Azure Functions (4 hàm) chạy; worker gửi được outbox lên Azure |
| 16/11 | TC13–TC16 đạt trên `docker compose` ở máy cá nhân với Azure thật (web + worker + Function); OpenStack có VM chạy được, VM ra được Internet (Người 2) |
| 19/11 | **Mốc quyết định:** TC13 đạt thì làm tiếp; không thì thu hẹp theo phần rủi ro trong kế hoạch. OpenStack: web chạy trên VM và cả nhóm vào được qua Tailscale; chưa được thì dùng phương án dự phòng ở mục 13 |
| 23/11 | Đóng băng chức năng; TC01-TC22 đã chạy |
| 24-28/11 | Quay video, slide, ghép và duyệt báo cáo |
| 29/11 | Nộp (sớm một ngày so với hạn 30/11) |

---

## 25. Thuật ngữ

| Thuật ngữ | Nghĩa trong dự án |
|---|---|
| Outbox | Bảng `sync_outbox`: hàng chờ các thay đổi cần gửi sang Azure, ghi cùng transaction với dữ liệu |
| Idempotent | Gửi lại nhiều lần cho kết quả như một lần (nhờ `version` và `processed_messages`) |
| Tìm kiếm dự phòng | Tìm bằng PostgreSQL khi Azure AI Search không phản hồi |
| RPO | Lượng dữ liệu tối đa có thể mất (ở đây ≤ 24 giờ) |
| RTO | Thời gian khôi phục hệ thống từ bản sao lưu (đo bằng `restore-test.sh`) |
| SAS | Chữ ký truy cập có giới hạn quyền và thời hạn cho Azure Storage |
| Floating IP | IP của mạng ngoài OpenStack gắn vào VM để truy cập từ ngoài mạng riêng |
| Security group | Tường lửa cấp VM của OpenStack |
