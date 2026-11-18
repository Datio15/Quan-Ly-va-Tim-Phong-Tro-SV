-- Migration 2026-11-18: chống tràn số trong room_monthly_cost và giới hạn tiền (BE-01, BE-02 báo cáo QA).
-- schema.sql đã có sẵn thay đổi này cho CSDL tạo mới. Với CSDL đang chạy, áp một lần:
--   docker compose exec -T db psql -U $DB_USER -d $DB_NAME -v ON_ERROR_STOP=1 < backend/db/migrations/2026-11-18-gioi-han-tien.sql
-- Chạy lại nhiều lần được. CHECK dùng NOT VALID: chặn dữ liệu mới, không kiểm tra dòng cũ
-- (dòng cũ vượt ngưỡng vẫn được room_monthly_cost kẹp lại nên không làm hỏng tìm kiếm).
BEGIN;

CREATE OR REPLACE FUNCTION room_monthly_cost(
  p_room_id  uuid,
  p_kwh      numeric,
  p_water_m3 numeric,
  p_people   integer,
  p_vehicles integer
) RETURNS TABLE (
  rent integer, electricity integer, water integer, internet integer,
  parking integer, service integer, total integer
) LANGUAGE sql STABLE AS $$
  WITH c AS (
    -- Tính bằng bigint rồi kẹp về giới hạn integer: một phòng có bảng giá bất thường không được làm
    -- hỏng truy vấn tìm kiếm của mọi người (BE-01, báo cáo QA 18/11).
    SELECT
      r.price_month::bigint                                                   AS rent,
      round(COALESCE(cr.electricity_per_kwh, 0)::numeric * p_kwh)::bigint     AS electricity,
      CASE COALESCE(cr.water_mode, 'per_m3')
        WHEN 'per_m3'     THEN round(COALESCE(cr.water_per_m3, 0)::numeric * p_water_m3)::bigint
        WHEN 'per_person' THEN COALESCE(cr.water_per_person, 0)::bigint * p_people
      END                                                                     AS water,
      COALESCE(cr.internet_per_month, 0)::bigint                              AS internet,
      COALESCE(cr.parking_per_vehicle, 0)::bigint * p_vehicles                AS parking,
      COALESCE(cr.service_per_month, 0)::bigint                               AS service
    FROM rooms r LEFT JOIN cost_rates cr ON cr.room_id = r.id
    WHERE r.id = p_room_id
  )
  SELECT LEAST(rent, 2147483647)::int, LEAST(electricity, 2147483647)::int, LEAST(water, 2147483647)::int,
         LEAST(internet, 2147483647)::int, LEAST(parking, 2147483647)::int, LEAST(service, 2147483647)::int,
         LEAST(rent + electricity + water + internet + parking + service, 2147483647)::int
  FROM c;
$$;

ALTER TABLE rooms DROP CONSTRAINT IF EXISTS rooms_money_limits;
ALTER TABLE rooms ADD CONSTRAINT rooms_money_limits CHECK (price_month <= 100000000 AND deposit_amount <= 1000000000) NOT VALID;
ALTER TABLE cost_rates DROP CONSTRAINT IF EXISTS cost_rates_limits;
ALTER TABLE cost_rates ADD CONSTRAINT cost_rates_limits CHECK (electricity_per_kwh <= 100000 AND water_per_m3 <= 1000000 AND water_per_person <= 10000000 AND internet_per_month <= 10000000 AND parking_per_vehicle <= 10000000 AND service_per_month <= 10000000) NOT VALID;
ALTER TABLE tenants DROP CONSTRAINT IF EXISTS tenants_money_limits;
ALTER TABLE tenants ADD CONSTRAINT tenants_money_limits CHECK (deposit_amount <= 1000000000) NOT VALID;

COMMIT;
