<p align="center"><img src="frontend/public/brand/easyrent-banner.webp" alt="EasyRent – Quản Lý Phòng Trọ Dễ Dàng" width="640" /></p>

# EasyRent – Quản lý và tìm phòng trọ cho sinh viên (Azure + OpenStack)

Bài tập lớn môn Điện toán đám mây. Hệ thống hai phía (sinh viên, chủ trọ) chạy trên hai đám mây: dữ liệu cá nhân ở OpenStack (private cloud); tìm kiếm, bản đồ, hẹn giờ, giám sát và sao lưu ở Azure (public cloud).

**Đọc [SPEC.md](SPEC.md) trước khi làm bất cứ việc gì.** Kiến trúc, dữ liệu, API, luồng đồng bộ, quy ước, tiêu chí nghiệm thu và kịch bản kiểm thử đều nằm ở đó.

## Bắt đầu trong 5 phút (máy cá nhân)

```bash
cp .env.example .env              # điền DB_PASSWORD, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD, JWT_SECRET, SEED_DEMO_PASSWORD (≥ 8 ký tự)
docker compose up -d --build      # db + minio + api + web; lần đầu tự nạp schema + 80 phòng dữ liệu giả
docker compose exec api pytest -q # kiểm thử TC01-TC12
```

Web: http://localhost · API docs: http://localhost:8000/api/docs · MinIO console: http://localhost:9001 · PostgreSQL: localhost:5432.
Tài khoản demo: `admin@example.com`, `chutro1..4@example.com`, `sinhvien1..6@example.com`, mật khẩu là `SEED_DEMO_PASSWORD`.
Chưa cấu hình Azure thì tìm kiếm tự dùng CSDL (header `X-Search-Source: db`) và bản đồ hiện thông báo thiếu khóa.

## Có gì trong kho

| Đường dẫn | Nội dung | Người phụ trách |
|---|---|---|
| `SPEC.md` | Đặc tả chung | Người 1 |
| `backend/db/schema.sql` | CSDL: 21 bảng, view `v_rooms_public`, hàm chi phí và khoảng cách | Người 2 |
| `seed/` | `generate_seed.py` sinh dữ liệu giả tái lập được; `seed.sql` là kết quả | Người 1 |
| `backend/` | API FastAPI – xem [backend/README.md](backend/README.md) (kèm danh sách đề xuất bổ sung SPEC) | Người 2 |
| `worker/` | Worker (sẽ viết) | Người 2, 6 |
| `frontend/` | React + Vite + Tailwind – xem [frontend/README.md](frontend/README.md) | Người 3 |
| `azure-functions/` | `search-index.json`; Function `ingest-room`, `daily-ticks` (sẽ viết) | Người 5 |
| `infra/openstack/` | `setup.sh` dựng project, mạng, VM, volume; `cloud-init.yaml` | Người 4 |
| `infra/azure/` | `setup.sh` dựng Storage, AI Search, Maps, Key Vault, App Insights, Function App | Người 5 |
| `scripts/` | `backup.sh` (mã hóa, tải lên Blob), `restore-test.sh` (khôi phục thử, đối chiếu) | Người 4, 6 |
| `docs/` | Ảnh chụp, số đo, ghi chú cho báo cáo | Cả nhóm |

## Lệnh hay dùng

```bash
# Sinh lại dữ liệu giả (đổi số phòng hoặc seed)
python3 seed/generate_seed.py --rooms 80 > seed/seed.sql
docker compose down -v && docker compose up -d db          # nạp lại từ đầu

# Sao lưu thử không tải lên Azure, rồi khôi phục thử
set -a; . ./.env; set +a
DB_HOST=localhost DRY_RUN=1 BACKUP_DIR=./data/backups scripts/backup.sh
DB_HOST=localhost scripts/restore-test.sh ./data/backups/phongtro-*.tar.gz.enc
```

## Quy tắc ngắn

- `.env` và `.env.*` không bao giờ đưa lên git. Không dán khóa, mật khẩu, token vào khung chat với AI.
- Đổi tên bảng, API, luồng dữ liệu thì sửa `SPEC.md` trước và báo cả nhóm.
- Nhánh `feature/<mô-đun>-<việc>`, commit mỗi ngày, pull request vào `main`, một người khác xem nhanh.
- Toàn bộ dữ liệu là dữ liệu giả. Một chức năng chỉ "xong" khi chạy được trên VM OpenStack hoặc Azure thật.
