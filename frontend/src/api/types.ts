export type Role = "student" | "landlord" | "admin";
export type RoomStatus = "draft" | "pending" | "published" | "hidden" | "rejected";
export type BookingStatus = "requested" | "confirmed" | "declined" | "cancelled" | "done";

export interface Paged<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface Me {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  role: Role;
  verified: boolean;
  telegram_linked: boolean;
}

export interface AppConfig {
  maps_key: string;
  telegram_bot: string;
  est_defaults: { kwh: number; m3: number; people: number; vehicles: number };
}

export interface School {
  id: string;
  name: string;
  short_name: string;
  lat: number;
  lng: number;
}

export interface Amenity {
  code: string;
  label: string;
}

export interface RoomCardData {
  id: string;
  title: string;
  description?: string;
  price_month: number;
  est_monthly_cost: number;
  deposit_amount?: number;
  area_m2: number;
  max_people?: number;
  floor?: number | null;
  area: string;
  ward: string;
  street: string;
  city?: string;
  lat: number | null;
  lng: number | null;
  distance_m: number | null;
  amenities: string[];
  curfew: boolean;
  curfew_time?: string | null;
  available_from?: string | null;
  rating_avg: number | null;
  rating_count: number;
  landlord_verified: boolean;
  thumbnail_url: string | null;
}

export interface Facet {
  value: string;
  count: number;
}

export interface SearchResult extends Paged<RoomCardData> {
  facets: { area: Facet[]; amenities: Facet[] };
}

export interface CostLine {
  code: string;
  label: string;
  amount: number;
}

export interface CostBreakdown {
  inputs: { kwh: number; m3: number; people: number; vehicles: number };
  lines: CostLine[];
  total: number;
}

export interface RoomDetail extends RoomCardData {
  images: { id: string; url: string }[];
  cost: CostBreakdown | null;
  is_favorite: boolean;
}

export interface Review {
  id: string;
  rating: number;
  comment: string;
  student_name: string;
  created_at: string;
  is_mine: boolean;
  is_hidden?: boolean;
}

export interface ReviewPage extends Paged<Review> {
  can_review: boolean;
  my_review: Review | null;
}

export interface Booking {
  id: string;
  status: BookingStatus;
  slot_start: string;
  student_note: string | null;
  landlord_note: string | null;
  created_at: string;
  room: { id: string; title: string; street: string; ward: string; area: string; address?: string };
  student?: { full_name: string; phone: string | null };
  landlord?: { full_name: string; phone: string | null };
  house_name?: string;
}

export interface House {
  id: string;
  name: string;
  address_private: string;
  street: string;
  ward: string;
  area: string;
  city: string;
  lat: number | null;
  lng: number | null;
  room_count?: number;
}

export interface CostRates {
  electricity_per_kwh: number;
  water_mode: "per_m3" | "per_person";
  water_per_m3: number;
  water_per_person: number;
  internet_per_month: number;
  parking_per_vehicle: number;
  service_per_month: number;
}

export interface RoomImage {
  id: string;
  url: string;
  position: number;
  moderation: "pending" | "ok" | "rejected";
  moderation_note: string | null;
  synced: boolean;
}

export interface LandlordRoom {
  id: string;
  house_id: string;
  house_name: string;
  title: string;
  price_month: number;
  area_m2: number;
  max_people: number;
  floor: number | null;
  status: RoomStatus;
  reject_reason: string | null;
  version: number;
  published_at: string | null;
  updated_at: string;
  thumbnail_url?: string | null;
}

export interface LandlordRoomFull extends LandlordRoom {
  description: string;
  deposit_amount: number;
  curfew_time: string | null;
  available_from: string | null;
  amenities: string[];
  cost_rates: CostRates;
  images: RoomImage[];
  house: { id: string; name: string; street: string; ward: string; area: string; city: string; lat: number | null; lng: number | null };
  landlord?: { id: string; full_name: string; verified: boolean };
}

export interface Tenant {
  id: string;
  room_id: string;
  room_title: string;
  full_name: string;
  phone: string | null;
  email: string | null;
  start_date: string;
  end_date: string | null;
  deposit_amount: number;
  people_count: number;
  vehicle_count: number;
  is_active: boolean;
  has_id_card: boolean;
  has_contract: boolean;
}

export interface MeterReading {
  id: string;
  room_id: string;
  month: string;
  electricity_index: number;
  water_index: number;
}

export interface Invoice {
  id: string;
  code: string;
  tenant_name: string;
  room_title: string;
  month: string;
  rent: number;
  electricity_used: number;
  electricity_amount: number;
  water_used: number;
  water_amount: number;
  internet_amount: number;
  parking_amount: number;
  service_amount: number;
  other_amount: number;
  total: number;
  status: "unpaid" | "paid" | "overdue" | "void";
  due_date: string;
  paid_at: string | null;
}

export interface JobRun {
  id: number;
  job: string;
  status: "queued" | "running" | "success" | "failed";
  started_at: string;
  finished_at: string | null;
  details: Record<string, unknown>;
}

export interface SystemStatus {
  db: boolean;
  minio: boolean;
  azure_search_reachable: boolean;
  outbox: { pending: number; failed: number; last_sent_at: string | null };
  queue: { last_message_at: string | null };
  backup: { last_success_at: string | null; size_bytes: number | null; duration_ms: number | null };
  restore_test: { last_at: string | null; total_ms: number | null; counts_match: boolean | null };
  search_fallback_last_hour: number;
  outbox_failed_rows: { id: number; room_id: string; op: string; attempts: number; last_error: string; created_at: string }[];
  recent_jobs: JobRun[];
}

export interface AdminReport {
  id: string;
  reason: string;
  status: "open" | "resolved" | "dismissed";
  created_at: string;
  target: {
    type: "room" | "review";
    id: string;
    title?: string;
    status?: string;
    rating?: number;
    comment?: string;
    is_hidden?: boolean;
    room_id?: string;
    student_name?: string;
  };
}

export interface AdminLandlord {
  id: string;
  full_name: string;
  email: string;
  phone: string | null;
  verified: boolean;
  room_count: number;
}
