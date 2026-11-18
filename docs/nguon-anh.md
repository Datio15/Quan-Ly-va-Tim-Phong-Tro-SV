# Nguồn ảnh phòng tượng trưng

SPEC mục 18 yêu cầu ghi nguồn ảnh phòng dùng cho demo.

| Mục | Nội dung |
|---|---|
| Thư mục | `seed/room-photos/phong-01.jpg` … `phong-28.jpg` (28 ảnh) |
| Nguồn | Thư mục Google Drive do nhóm cung cấp ngày 16/11/2026 (30 ảnh; bỏ 2 ảnh dưới 400 px) |
| Xử lý | Xoay đúng chiều, thu về cạnh dài 1280 px, JPEG chất lượng 80, **đã xóa toàn bộ EXIF/metadata** (kể cả GPS nếu có) |
| Cách dùng | `backend/app/seed_images.py` gắn ngẫu nhiên 2-4 ảnh cho mỗi phòng của dữ liệu mẫu, chạy một lần khi api khởi động |
| Tính chất | Ảnh **tượng trưng**, không phải ảnh thật của các phòng giả trong seed |

> ⚠️ Cần nhóm xác nhận ảnh được phép dùng lại (tự chụp, có giấy phép, hoặc được chủ ảnh đồng ý).
> SPEC 18 không cho lấy ảnh từ trang đăng tin khác. Nếu chưa chắc chắn, thay bằng ảnh tự chụp
> với cùng tên file rồi chạy `docker compose exec api python -m app.seed_images --force` trên CSDL mới.
