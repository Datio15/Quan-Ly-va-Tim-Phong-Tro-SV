# Đánh giá thành viên nhóm

Dự án: Quản lý và tìm phòng trọ cho sinh viên (Azure + OpenStack)

| Thành viên | Nhiệm vụ | Đánh giá |
|---|---|---|
| **Đặng Thế Đạt** (nhóm trưởng) | Quản lý nhóm, SPEC, dữ liệu mẫu, kiểm thử; Worker, Telegram; sửa lỗi | **Tốt.** Viết và cập nhật SPEC qua các bản v0.3 đến v0.5, quản lý repo và duyệt PR. Lập báo cáo kiểm thử QA 18/11 (32 lỗi) và sửa phần lớn số lỗi đó ở cả backend lẫn web. Làm phần Telegram (liên kết tài khoản, nhắc việc), đọc hàng đợi `ops-ticks`, sao lưu và khôi phục thử qua worker, heartbeat, số đo và quy tắc cảnh báo. Chuyển worker sang SAS giới hạn quyền và viết tài liệu hướng dẫn triển khai. |
| **Dương Hoàng Anh** | OpenStack (vm-app, vm-data) | **Tốt.** Nhận phần OpenStack từ 14/11, dựng hạ tầng DevStack với hai VM vm-app và vm-data. Đưa web và api lên chạy trên VM; cả nhóm truy cập được qua Tailscale. |
| **Nguyễn Tiến Đạt** | Frontend | **Tốt.** Dựng khung frontend ban đầu (React, Vite, TypeScript). Sửa lỗi tải ảnh phòng, làm giao diện dùng được trên điện thoại, đồng bộ dropdown ở trang quản lý phòng của chủ trọ. |
| **Vũ Tuấn Anh** | Backend | **Tốt.** Viết backend FastAPI và web gốc, được nhóm chọn làm mã chuẩn. Sửa lỗi kịp thời: chặn dữ liệu đầu vào gây lỗi 500, lỗi `/landlord/houses`, seed ảnh phòng, encoding seed, ép kiểu ở worker, cấu hình Application Insights. |
| **Trịnh Thị Vân** | Azure | **Tốt.** Dựng đủ tài nguyên Azure: Storage, AI Search, Key Vault, Maps, Application Insights, Function App, Budget. Viết 4 Azure Functions (`ingest-room`, `tick-now`, `daily-ticks-morning`, `daily-ticks-backup`) và chỉnh `setup.sh` cho tài khoản Azure for Students. |
| **Phạm Nguyễn Thu Giang** | Khung Worker | **Tốt.** Dựng khung worker đúng SPEC mục 6 và 12, hoàn thiện `db.py`, `outbox.py`, khung `queue.py` và `telegram.py`, làm nền cho các phần worker phát triển sau. |
