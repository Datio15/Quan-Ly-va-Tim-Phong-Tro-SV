-- Migration 2026-11-19: sửa các lỗi còn lại trong báo cáo QA 18/11 (BE-03, BE-04, BE-12).
-- schema.sql đã có sẵn thay đổi này cho CSDL tạo mới. Với CSDL đang chạy, áp một lần:
--   docker compose exec -T db psql -U $DB_USER -d $DB_NAME -v ON_ERROR_STOP=1 < backend/db/migrations/2026-11-19-sua-loi-qa.sql
-- Chạy lại nhiều lần được. Cần quyền tạo extension (POSTGRES_USER của image postgres có quyền này).
BEGIN;

-- BE-12: tìm kiếm dự phòng không phân biệt dấu tiếng Việt ("cau giay" khớp "Cầu Giấy").
CREATE EXTENSION IF NOT EXISTS unaccent;

-- BE-04: hóa đơn hủy (void) không chặn tạo lại hóa đơn cùng tháng cho cùng khách.
ALTER TABLE invoices DROP CONSTRAINT IF EXISTS invoices_tenant_id_period_key;
CREATE UNIQUE INDEX IF NOT EXISTS invoices_tenant_period_uq ON invoices (tenant_id, period) WHERE status <> 'void';

-- BE-03: mỗi phòng tối đa một hợp đồng đang hiệu lực. api đã kiểm tra (khóa dòng phòng); index là lưới an toàn.
-- Nếu CSDL đã có phòng nhiều khách đang thuê thì bỏ qua index và in danh sách để chủ trọ xử lý tay.
DO $$
DECLARE dup int;
BEGIN
  SELECT count(*) INTO dup FROM (
    SELECT room_id FROM tenants WHERE is_active GROUP BY room_id HAVING count(*) > 1) d;
  IF dup = 0 THEN
    CREATE UNIQUE INDEX IF NOT EXISTS tenants_one_active_per_room ON tenants (room_id) WHERE is_active;
  ELSE
    RAISE NOTICE 'Bỏ qua index tenants_one_active_per_room: % phòng đang có nhiều khách thuê. Xem: SELECT room_id, count(*) FROM tenants WHERE is_active GROUP BY room_id HAVING count(*) > 1;', dup;
  END IF;
END $$;

COMMIT;
