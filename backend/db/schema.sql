-- =====================================================================
-- schema.sql – CSDL của hệ thống tìm và quản lý phòng trọ
-- PostgreSQL 16. Chạy một lần trên CSDL trống:
--   psql -v ON_ERROR_STOP=1 -d phongtro -f backend/db/schema.sql
-- Mọi thay đổi về sau làm bằng migration (Alembic) và cập nhật SPEC.md.
-- Quy ước: khóa chính uuid; thời gian timestamptz (UTC); tiền là số nguyên VND.
-- =====================================================================

BEGIN;

-- ---------- Kiểu liệt kê ----------
CREATE TYPE user_role         AS ENUM ('student', 'landlord', 'admin');
CREATE TYPE room_status       AS ENUM ('draft', 'pending', 'published', 'hidden', 'rejected');
CREATE TYPE moderation_status AS ENUM ('pending', 'ok', 'rejected');
CREATE TYPE booking_status    AS ENUM ('requested', 'confirmed', 'declined', 'cancelled', 'done');
CREATE TYPE invoice_status    AS ENUM ('unpaid', 'paid', 'overdue', 'void');
CREATE TYPE report_status     AS ENUM ('open', 'resolved', 'dismissed');
CREATE TYPE reading_source    AS ENUM ('manual', 'ocr');
CREATE TYPE water_mode        AS ENUM ('per_m3', 'per_person');
CREATE TYPE sync_op           AS ENUM ('upsert', 'delete');
CREATE TYPE sync_status       AS ENUM ('pending', 'sent', 'failed');
CREATE TYPE job_status        AS ENUM ('queued', 'running', 'success', 'failed');  -- queued: quản trị yêu cầu, chờ worker chạy

-- ---------- Hàm dùng chung: tự cập nhật updated_at ----------
CREATE FUNCTION set_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

-- ---------- Người dùng ----------
CREATE TABLE users (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email            text NOT NULL CHECK (email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
  password_hash    text NOT NULL,
  full_name        text NOT NULL CHECK (length(full_name) BETWEEN 2 AND 100),
  phone            text CHECK (phone ~ '^\+?[0-9]{9,12}$'),
  role             user_role NOT NULL,
  verified         boolean NOT NULL DEFAULT false,      -- chủ trọ đã được xác minh
  telegram_chat_id text,                                -- để nhận nhắc lịch, nhắc hạn
  telegram_link_code    text UNIQUE,                    -- mã một lần trong link t.me/<bot>?start=<mã>
  telegram_link_expires timestamptz,
  is_active        boolean NOT NULL DEFAULT true,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX users_email_lower_uq ON users (lower(email));
CREATE TRIGGER users_updated_at BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------- Trường học (điểm tính khoảng cách) ----------
CREATE TABLE schools (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name       text NOT NULL UNIQUE,
  short_name text NOT NULL,
  lat        double precision NOT NULL CHECK (lat BETWEEN -90 AND 90),
  lng        double precision NOT NULL CHECK (lng BETWEEN -180 AND 180)
);

-- ---------- Tiện nghi (danh mục cố định) ----------
CREATE TABLE amenities (
  code     text PRIMARY KEY CHECK (code ~ '^[a-z_]+$'),
  label_vi text NOT NULL
);
INSERT INTO amenities (code, label_vi) VALUES
  ('gac_lung',      'Gác lửng'),
  ('dieu_hoa',      'Điều hòa'),
  ('nong_lanh',     'Bình nóng lạnh'),
  ('ve_sinh_rieng', 'Vệ sinh khép kín'),
  ('cho_de_xe',     'Chỗ để xe'),
  ('may_giat',      'Máy giặt'),
  ('tu_lanh',       'Tủ lạnh'),
  ('bep_rieng',     'Bếp riêng'),
  ('ban_cong',      'Ban công'),
  ('cua_so',        'Cửa sổ'),
  ('wifi',          'Wifi'),
  ('thang_may',     'Thang máy'),
  ('camera',        'Camera an ninh'),
  ('noi_that',      'Có nội thất'),
  ('khong_chung_chu','Không chung chủ');

-- ---------- Nhà trọ (một chủ trọ có nhiều nhà) ----------
CREATE TABLE houses (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  landlord_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name            text NOT NULL,
  address_private text NOT NULL,   -- số nhà, ngõ: KHÔNG bao giờ gửi sang Azure
  street          text NOT NULL,   -- tên đường: công khai
  ward            text NOT NULL,   -- phường/xã: công khai
  area            text NOT NULL,   -- khu vực quen gọi (vd "Cầu Giấy"): công khai, dùng để lọc
  city            text NOT NULL,
  lat             double precision CHECK (lat BETWEEN -90 AND 90),
  lng             double precision CHECK (lng BETWEEN -180 AND 180),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX houses_landlord_idx ON houses (landlord_id);
CREATE TRIGGER houses_updated_at BEFORE UPDATE ON houses
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------- Phòng ----------
CREATE TABLE rooms (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  house_id       uuid NOT NULL REFERENCES houses(id) ON DELETE CASCADE,
  title          text NOT NULL CHECK (length(title) BETWEEN 5 AND 120),
  description    text NOT NULL DEFAULT '',
  price_month    integer NOT NULL CHECK (price_month > 0),
  deposit_amount integer NOT NULL DEFAULT 0 CHECK (deposit_amount >= 0),
  area_m2        numeric(6,1) NOT NULL CHECK (area_m2 > 0),
  floor          smallint,
  max_people     smallint NOT NULL DEFAULT 2 CHECK (max_people >= 1),
  curfew_time    time,             -- NULL = giờ giấc tự do
  available_from date,
  status         room_status NOT NULL DEFAULT 'draft',
  reject_reason  text,
  version        integer NOT NULL DEFAULT 1,  -- tăng mỗi lần sửa (dùng cho đồng bộ)
  published_at   timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX rooms_house_idx  ON rooms (house_id);
CREATE INDEX rooms_status_idx ON rooms (status);
CREATE INDEX rooms_price_published_idx ON rooms (price_month) WHERE status = 'published';
CREATE TRIGGER rooms_updated_at BEFORE UPDATE ON rooms
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE room_amenities (
  room_id      uuid NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
  amenity_code text NOT NULL REFERENCES amenities(code),
  PRIMARY KEY (room_id, amenity_code)
);

CREATE TABLE room_images (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  room_id         uuid NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
  object_key      text NOT NULL,     -- khóa trong MinIO bucket public-src
  position        smallint NOT NULL DEFAULT 0,
  moderation      moderation_status NOT NULL DEFAULT 'pending',
  moderation_note text,
  public_url      text,              -- URL CDN sau khi đồng bộ sang Azure
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX room_images_room_idx ON room_images (room_id, position);

-- ---------- Bảng giá dịch vụ của phòng ----------
CREATE TABLE cost_rates (
  room_id             uuid PRIMARY KEY REFERENCES rooms(id) ON DELETE CASCADE,
  electricity_per_kwh integer NOT NULL DEFAULT 0 CHECK (electricity_per_kwh >= 0),
  water_mode          water_mode NOT NULL DEFAULT 'per_m3',
  water_per_m3        integer NOT NULL DEFAULT 0 CHECK (water_per_m3 >= 0),
  water_per_person    integer NOT NULL DEFAULT 0 CHECK (water_per_person >= 0),
  internet_per_month  integer NOT NULL DEFAULT 0 CHECK (internet_per_month >= 0),
  parking_per_vehicle integer NOT NULL DEFAULT 0 CHECK (parking_per_vehicle >= 0),
  service_per_month   integer NOT NULL DEFAULT 0 CHECK (service_per_month >= 0), -- vệ sinh, rác...
  updated_at          timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER cost_rates_updated_at BEFORE UPDATE ON cost_rates
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------- Sinh viên: yêu thích, tìm kiếm đã lưu, lịch xem, đánh giá ----------
CREATE TABLE favorites (
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  room_id    uuid NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, room_id)
);

CREATE TABLE saved_searches (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name             text NOT NULL,
  criteria         jsonb NOT NULL,   -- cùng tham số với GET /search/rooms
  notify           boolean NOT NULL DEFAULT false,
  last_notified_at timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE bookings (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  room_id       uuid NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
  student_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  slot_start    timestamptz NOT NULL,
  status        booking_status NOT NULL DEFAULT 'requested',
  student_note  text,
  landlord_note text,
  reminded_at   timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
-- Không cho hai lịch đang hiệu lực trùng cùng phòng, cùng giờ.
CREATE UNIQUE INDEX bookings_active_slot_uq ON bookings (room_id, slot_start)
  WHERE status IN ('requested', 'confirmed');
CREATE INDEX bookings_student_idx ON bookings (student_id);
CREATE TRIGGER bookings_updated_at BEFORE UPDATE ON bookings
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE reviews (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  room_id    uuid NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
  student_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  rating     smallint NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment    text NOT NULL DEFAULT '',
  is_hidden  boolean NOT NULL DEFAULT false,   -- quản trị ẩn khi vi phạm
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (room_id, student_id)
);

CREATE TABLE reports (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  target_type text NOT NULL CHECK (target_type IN ('room', 'review')),
  target_id   uuid NOT NULL,
  reporter_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  reason      text NOT NULL,
  status      report_status NOT NULL DEFAULT 'open',
  resolved_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz
);

-- ---------- Chủ trọ: khách thuê, chỉ số, hóa đơn ----------
CREATE TABLE tenants (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  room_id             uuid NOT NULL REFERENCES rooms(id) ON DELETE RESTRICT,
  full_name           text NOT NULL,
  phone               text,
  email               text,
  id_card_object_key  text,   -- ảnh CCCD (GIẢ) trong MinIO bucket private
  contract_object_key text,   -- hợp đồng (GIẢ) trong MinIO bucket private
  start_date          date NOT NULL,
  end_date            date,
  deposit_amount      integer NOT NULL DEFAULT 0 CHECK (deposit_amount >= 0),
  people_count        smallint NOT NULL DEFAULT 1 CHECK (people_count >= 1),
  vehicle_count       smallint NOT NULL DEFAULT 1 CHECK (vehicle_count >= 0),
  is_active           boolean NOT NULL DEFAULT true,
  created_at          timestamptz NOT NULL DEFAULT now(),
  CHECK (end_date IS NULL OR end_date >= start_date)
);
CREATE INDEX tenants_room_idx ON tenants (room_id) WHERE is_active;

-- Chỉ số công tơ là số CỘNG DỒN; lượng dùng = kỳ này - kỳ trước.
CREATE TABLE meter_readings (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  room_id            uuid NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
  period             date NOT NULL CHECK (extract(day FROM period) = 1),  -- ngày 1 của tháng
  electricity_index  numeric(10,1) NOT NULL CHECK (electricity_index >= 0),
  water_index        numeric(10,1) NOT NULL CHECK (water_index >= 0),
  photo_object_key   text,
  source             reading_source NOT NULL DEFAULT 'manual',
  created_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (room_id, period)
);

CREATE TABLE invoices (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code               text NOT NULL UNIQUE,      -- vd HD-202611-0001, in trên PDF và QR
  tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  room_id            uuid NOT NULL REFERENCES rooms(id) ON DELETE RESTRICT,
  period             date NOT NULL CHECK (extract(day FROM period) = 1),
  rent               integer NOT NULL CHECK (rent >= 0),
  electricity_used   numeric(10,1) NOT NULL DEFAULT 0,
  electricity_amount integer NOT NULL DEFAULT 0,
  water_used         numeric(10,1) NOT NULL DEFAULT 0,
  water_amount       integer NOT NULL DEFAULT 0,
  internet_amount    integer NOT NULL DEFAULT 0,
  parking_amount     integer NOT NULL DEFAULT 0,
  service_amount     integer NOT NULL DEFAULT 0,
  other_amount       integer NOT NULL DEFAULT 0,
  total              integer GENERATED ALWAYS AS (
                       rent + electricity_amount + water_amount + internet_amount
                       + parking_amount + service_amount + other_amount) STORED,
  status             invoice_status NOT NULL DEFAULT 'unpaid',
  due_date           date NOT NULL,
  paid_at            timestamptz,
  pdf_object_key     text,
  qr_payload         text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, period)
);
CREATE INDEX invoices_status_due_idx ON invoices (status, due_date);

-- ---------- Đồng bộ, việc nền, thông báo, nhật ký ----------
-- Hộp thư đi: api ghi CÙNG transaction với thay đổi phòng; worker đọc và gửi sang Azure.
CREATE TABLE sync_outbox (
  id              bigserial PRIMARY KEY,
  entity_type     text NOT NULL CHECK (entity_type IN ('room')),
  entity_id       uuid NOT NULL,
  entity_version  integer NOT NULL,
  op              sync_op NOT NULL,
  payload         jsonb,             -- ảnh chụp để gỡ lỗi; worker luôn dựng lại từ v_rooms_public
  status          sync_status NOT NULL DEFAULT 'pending',
  attempts        integer NOT NULL DEFAULT 0,
  last_error      text,
  next_attempt_at timestamptz NOT NULL DEFAULT now(),
  created_at      timestamptz NOT NULL DEFAULT now(),
  sent_at         timestamptz
);
CREATE INDEX sync_outbox_due_idx ON sync_outbox (next_attempt_at) WHERE status = 'pending';
CREATE INDEX sync_outbox_entity_idx ON sync_outbox (entity_type, entity_id);

-- Mỗi lần chạy việc nền (sao lưu, khôi phục thử, nhắc lịch...) ghi một dòng: trang trạng thái và số đo RTO lấy từ đây.
CREATE TABLE job_runs (
  id          bigserial PRIMARY KEY,
  job         text NOT NULL CHECK (job IN ('backup', 'restore_test', 'sync_resync',
                    'viewing_reminder', 'invoice_due_check', 'contract_expiring')),
  status      job_status NOT NULL DEFAULT 'running',
  started_at  timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  details     jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX job_runs_job_idx ON job_runs (job, started_at DESC);

-- Chống xử lý trùng tin nhắn từ hàng đợi Azure.
CREATE TABLE processed_messages (
  message_id   text PRIMARY KEY,
  processed_at timestamptz NOT NULL DEFAULT now()
);

-- Chống gửi trùng một thông báo.
CREATE TABLE notifications (
  id       bigserial PRIMARY KEY,
  user_id  uuid REFERENCES users(id) ON DELETE CASCADE,
  channel  text NOT NULL CHECK (channel IN ('telegram', 'email', 'in_app')),
  kind     text NOT NULL,   -- viewing_reminder, invoice_overdue, contract_expiring, new_room_match
  ref_id   uuid NOT NULL,   -- id của booking / invoice / tenant / room
  sent_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, channel, kind, ref_id)
);

CREATE TABLE audit_log (
  id         bigserial PRIMARY KEY,
  user_id    uuid REFERENCES users(id) ON DELETE SET NULL,
  action     text NOT NULL,     -- vd room.approve, room.publish, invoice.generate
  entity     text NOT NULL,
  entity_id  uuid,
  meta       jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ---------- Bản công khai của phòng ----------
-- Nguồn DUY NHẤT để dựng tài liệu gửi sang Azure AI Search và để tìm kiếm dự phòng.
-- Chỉ chứa trường công khai: không tên/điện thoại chủ trọ, không số nhà, không khách thuê.
CREATE VIEW v_rooms_public AS
SELECT
  r.id,
  r.title,
  r.description,
  r.price_month,
  r.deposit_amount,
  r.area_m2::double precision AS area_m2,
  r.max_people,
  r.floor,
  (r.curfew_time IS NOT NULL)  AS curfew,
  r.curfew_time,
  r.available_from,
  h.street, h.ward, h.area, h.city, h.lat, h.lng,
  COALESCE((SELECT array_agg(ra.amenity_code ORDER BY ra.amenity_code)
              FROM room_amenities ra WHERE ra.room_id = r.id), '{}')        AS amenities,
  (SELECT round(avg(rv.rating)::numeric, 1)::double precision
     FROM reviews rv WHERE rv.room_id = r.id AND NOT rv.is_hidden)          AS rating_avg,
  (SELECT count(*)::int
     FROM reviews rv WHERE rv.room_id = r.id AND NOT rv.is_hidden)          AS rating_count,
  COALESCE((SELECT array_agg(ri.object_key ORDER BY ri.position)
              FROM room_images ri WHERE ri.room_id = r.id AND ri.moderation = 'ok'), '{}') AS image_keys,
  u.verified AS landlord_verified,
  r.status,
  r.version,
  r.updated_at
FROM rooms r
JOIN houses h ON h.id = r.house_id
JOIN users  u ON u.id = h.landlord_id;

-- ---------- Chi phí thực tế mỗi tháng ----------
-- Dùng chung cho API /rooms/{id}/cost, bảng so sánh, và trường est_monthly_cost trong chỉ mục.
CREATE FUNCTION room_monthly_cost(
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
    SELECT
      r.price_month                                                           AS rent,
      round(COALESCE(cr.electricity_per_kwh, 0) * p_kwh)::int                 AS electricity,
      CASE COALESCE(cr.water_mode, 'per_m3')
        WHEN 'per_m3'     THEN round(COALESCE(cr.water_per_m3, 0) * p_water_m3)::int
        WHEN 'per_person' THEN COALESCE(cr.water_per_person, 0) * p_people
      END                                                                     AS water,
      COALESCE(cr.internet_per_month, 0)                                      AS internet,
      COALESCE(cr.parking_per_vehicle, 0) * p_vehicles                        AS parking,
      COALESCE(cr.service_per_month, 0)                                       AS service
    FROM rooms r LEFT JOIN cost_rates cr ON cr.room_id = r.id
    WHERE r.id = p_room_id
  )
  SELECT rent, electricity, water, internet, parking, service,
         rent + electricity + water + internet + parking + service
  FROM c;
$$;

-- ---------- Khoảng cách (mét) theo công thức haversine ----------
CREATE FUNCTION distance_m(lat1 double precision, lng1 double precision,
                           lat2 double precision, lng2 double precision)
RETURNS integer LANGUAGE sql IMMUTABLE AS $$
  SELECT round(2 * 6371000 * asin(sqrt(
           power(sin(radians(lat2 - lat1) / 2), 2) +
           cos(radians(lat1)) * cos(radians(lat2)) * power(sin(radians(lng2 - lng1) / 2), 2)
         )))::int;
$$;

COMMIT;
