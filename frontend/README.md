# EasyRent – Frontend (Người 3, React 18 + Vite + TypeScript + Tailwind)

## Nhận diện thương hiệu

| Thành phần | Giá trị |
|---|---|
| Tên | **EasyRent** – "Quản Lý Phòng Trọ Dễ Dàng" |
| Logo | `public/brand/easyrent-banner.webp` (ảnh gốc), `easyrent-icon.png` (biểu tượng nền trong suốt), `favicon.png`; component `src/components/Logo.tsx` (biểu tượng + chữ Easy/Rent) |
| Màu | Xanh teal `#185a62` (`brand-700`, chữ "Easy", nút chính) · Cam `#f07a30` (`accent-500`, chữ "Rent", giá tiền) · Xanh lá `#78b858` (`leaf-500`) |
| Font | Montserrat (Google Fonts, có bộ ký tự tiếng Việt) – khai báo ở `index.html` và `tailwind.config.js` |

## Chạy

Cùng stack (nginx phục vụ bản build, `/api/*` chuyển sang api):

```bash
docker compose up -d --build        # http://localhost
```

Phát triển có hot reload (cần Node 20, api chạy ở localhost:8000):

```bash
cd frontend && npm ci && npm run dev          # http://localhost:5173, /api proxy sang :8000
npm run build                                  # tsc --noEmit + vite build
```

Bản đồ cần `AZURE_MAPS_KEY` trong `.env` (giao diện đọc qua `GET /api/v1/config`). Thiếu khóa thì bản đồ hiện thông báo, các chức năng khác vẫn chạy; chủ trọ nhập tọa độ tay.

## Trang

| Đường dẫn | Vai trò | Chức năng |
|---|---|---|
| `/` | Mọi người | Tìm phòng (F04): từ khóa, giá, chi phí ước tính, diện tích, khu vực, tiện nghi, giờ giấc, số người, trường + bán kính, xác minh, sắp xếp; danh sách + bản đồ Azure Maps (F05); huy hiệu nguồn `Azure AI Search` / `Dự phòng CSDL` |
| `/rooms/:id` | Mọi người | Ảnh, thông tin, bản đồ + khoảng cách tới trường, bảng chi phí chỉnh được (F07), đặt lịch, yêu thích, đánh giá, báo cáo (F08, F09) |
| `/compare` | Mọi người | So sánh 2-3 phòng, đánh dấu ô tốt nhất (F06) |
| `/favorites`, `/bookings` | Sinh viên | Yêu thích; lịch xem của tôi (hủy, viết đánh giá) |
| `/profile` | Đã đăng nhập | Sửa tên, số điện thoại; liên kết Telegram (mục 3F) |
| `/landlord/houses` | Chủ trọ | Nhà trọ: địa chỉ riêng tư/công khai, định vị bằng Azure Maps Geocoding + kéo ghim |
| `/landlord/rooms`, `/landlord/rooms/:id` | Chủ trọ | Phòng, bảng giá dịch vụ, tiện nghi, ảnh; gửi duyệt, ẩn/hiện |
| `/bookings` | Chủ trọ | Xác nhận, từ chối, hủy, đánh dấu đã xem |
| `/landlord/tenants`, `/landlord/invoices` | Chủ trọ | Khách thuê + file CCCD/hợp đồng GIẢ (F16); chỉ số công tơ, tạo hóa đơn, đã trả (F17) |
| `/admin/moderation`, `/admin/reports`, `/admin/landlords` | Quản trị | Duyệt tin/ảnh, gỡ tin; xử lý báo cáo, ẩn đánh giá; xác minh chủ trọ |
| `/admin/system` | Quản trị | Trạng thái (F14): DB, MinIO, Azure Search, outbox, hàng đợi, sao lưu/khôi phục thử, đồng bộ lại, việc nền gần đây |

## Quy ước

- Gọi API qua `src/api/client.ts` (JWT trong `localStorage`, lỗi theo định dạng `{"error": {...}}` của SPEC 10.1).
- Tiền hiển thị `3.200.000đ`, thời gian theo `Asia/Ho_Chi_Minh` (`src/lib/format.ts`). Giờ hẹn gửi lên dạng `2026-11-21T16:00:00+07:00`.
- Danh sách so sánh lưu tạm ở `localStorage` (không phải dữ liệu quan trọng).
- Giao diện dùng được trên điện thoại (bộ lọc dạng ngăn kéo, bảng cuộn ngang).
