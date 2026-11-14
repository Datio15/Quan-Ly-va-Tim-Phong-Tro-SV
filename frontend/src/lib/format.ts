// Quy ước hiển thị (SPEC 20): tiền dạng 3.200.000đ, thời gian theo Asia/Ho_Chi_Minh.
const TZ = "Asia/Ho_Chi_Minh";

export function vnd(n: number | null | undefined): string {
  if (n === null || n === undefined) return "–";
  return `${Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".")}đ`;
}

export function shortVnd(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} tr`;
  if (n >= 1000) return `${Math.round(n / 1000)}k`;
  return String(n);
}

export function distance(m: number | null | undefined): string {
  if (m === null || m === undefined) return "";
  return m < 1000 ? `${m} m` : `${(m / 1000).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} km`;
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "–";
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: TZ, hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit", year: "numeric",
  }).format(new Date(iso));
}

export function date(iso: string | null | undefined): string {
  if (!iso) return "–";
  // ngày thuần (YYYY-MM-DD) không đổi múi giờ
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
    const [y, m, d] = iso.split("-");
    return `${d}/${m}/${y}`;
  }
  return new Intl.DateTimeFormat("vi-VN", { timeZone: TZ, day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(iso));
}

/** Giá trị input datetime-local (giờ Việt Nam) -> ISO 8601 có múi giờ +07:00. */
export function localInputToIso(value: string): string {
  return `${value.length === 16 ? `${value}:00` : value}+07:00`;
}

/** Thời điểm hiện tại + offset giờ, dạng giá trị cho input datetime-local theo giờ Việt Nam. */
export function vnInputValue(offsetHours: number): string {
  const d = new Date(Date.now() + offsetHours * 3600_000);
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
  }).formatToParts(d);
  const get = (t: string) => parts.find((p) => p.type === t)?.value || "00";
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour") === "24" ? "00" : get("hour")}:${get("minute")}`;
}

export function currentMonth(offset = 0): string {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() + offset);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export const ROOM_STATUS_LABEL: Record<string, string> = {
  draft: "Nháp",
  pending: "Chờ duyệt",
  published: "Đang hiển thị",
  hidden: "Đã ẩn",
  rejected: "Bị từ chối",
};

export const BOOKING_STATUS_LABEL: Record<string, string> = {
  requested: "Chờ xác nhận",
  confirmed: "Đã xác nhận",
  declined: "Bị từ chối",
  cancelled: "Đã hủy",
  done: "Đã xem",
};

export const INVOICE_STATUS_LABEL: Record<string, string> = {
  unpaid: "Chưa trả",
  paid: "Đã trả",
  overdue: "Quá hạn",
  void: "Đã hủy",
};
