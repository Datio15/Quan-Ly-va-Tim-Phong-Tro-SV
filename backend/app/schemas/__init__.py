"""Pydantic request schema. Phản hồi phần lớn dựng bằng dict theo đúng ví dụ ở SPEC 10.4."""
import re
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

# Chặt hơn CHECK trong schema.sql (CHECK chỉ là lưới an toàn cuối): phần tên miền phải có đuôi chữ ≥ 2 ký tự,
# không có hai dấu chấm liền nhau, không bắt đầu/kết thúc bằng dấu chấm (BE-07).
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[0-9]{9,12}$")
AMENITY_RE = re.compile(r"^[a-z_]+$")
VN = timezone(timedelta(hours=7))

# Lịch xem phòng: mốc 15 phút, trong khung 07:00-21:00 giờ Việt Nam (BE-08).
BOOKING_STEP_MIN = 15
BOOKING_FIRST_HOUR, BOOKING_LAST_HOUR = 7, 21


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _check_phone(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    if not PHONE_RE.match(v):
        raise ValueError("Số điện thoại gồm 9-12 chữ số")
    return v


Phone = Annotated[str | None, AfterValidator(_check_phone)]


def check_email(v: str) -> str:
    v = v.strip().lower()
    local = v.split("@", 1)[0]
    if not EMAIL_RE.match(v) or ".." in v or local.startswith(".") or local.endswith("."):
        raise ValueError("Email không hợp lệ")
    return v


def _optional_email(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    return check_email(v)


OptionalEmail = Annotated[str | None, Field(max_length=254), AfterValidator(_optional_email)]


def _no_markup(v: str | None) -> str | None:
    """Tên người, tiêu đề phòng không chứa < > (tránh chèn HTML khi dữ liệu đi sang kênh khác web)."""
    if v is not None and ("<" in v or ">" in v):
        raise ValueError("Không được chứa ký tự < hoặc >")
    return v


PersonName = Annotated[str, Field(min_length=2, max_length=100), AfterValidator(_no_markup)]
RoomTitle = Annotated[str, Field(min_length=5, max_length=120), AfterValidator(_no_markup)]


def _check_password(v: str) -> str:
    if not (any(c.isalpha() for c in v) and any(c.isdigit() for c in v)):
        raise ValueError("Mật khẩu cần có cả chữ và số")
    return v


# Mật khẩu KHÔNG bị cắt khoảng trắng (StrictModel cắt mọi chuỗi khác).
Password = Annotated[str, StringConstraints(strip_whitespace=False, min_length=8, max_length=128),
                     AfterValidator(_check_password)]
RawPassword = Annotated[str, StringConstraints(strip_whitespace=False, max_length=128)]

# ---------- Giới hạn giá trị (BE-01, BE-02 báo cáo QA 18/11) ----------
# Cột tiền là integer (int4) và room_monthly_cost cộng các khoản: giới hạn để không tràn số và không có
# giá trị phi thực tế. Diện tích numeric(6,1), chỉ số công tơ numeric(10,1): tối đa 1 chữ số thập phân.
MAX_RENT = 100_000_000            # giá thuê / tháng
MAX_DEPOSIT = 1_000_000_000       # tiền cọc
MAX_KWH_RATE = 100_000            # đ/kWh
MAX_M3_RATE = 1_000_000           # đ/m³
MAX_PERSON_RATE = 10_000_000      # nước đ/người
MAX_MONTHLY_FEE = 10_000_000      # internet, gửi xe/xe, dịch vụ
YEAR_MIN, YEAR_MAX = 2000, 2100


def _one_decimal(v: float) -> float:
    if abs(v * 10 - round(v * 10)) > 1e-6:
        raise ValueError("Tối đa 1 chữ số thập phân")
    return round(v, 1)


def _check_year(v: date) -> date:
    if not YEAR_MIN <= v.year <= YEAR_MAX:
        raise ValueError(f"Năm phải trong khoảng {YEAR_MIN}-{YEAR_MAX}")
    return v


Area = Annotated[float, Field(ge=1, le=9999, allow_inf_nan=False), AfterValidator(_one_decimal)]
MeterIndex = Annotated[float, Field(ge=0, le=99_999_999, allow_inf_nan=False), AfterValidator(_one_decimal)]
SafeDate = Annotated[date, AfterValidator(_check_year)]
Rent = Annotated[int, Field(gt=0, le=MAX_RENT)]
Deposit = Annotated[int, Field(ge=0, le=MAX_DEPOSIT)]


# ---------- Xác thực ----------
class RegisterIn(StrictModel):
    email: str = Field(max_length=254)
    password: Password
    full_name: PersonName
    phone: Phone = None
    role: Literal["student", "landlord"]

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return check_email(v)


class LoginIn(StrictModel):
    email: str = Field(max_length=254)
    password: RawPassword

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.lower()


class MePatch(StrictModel):
    full_name: PersonName | None = None
    phone: Phone = None


# ---------- Sinh viên ----------
class CompareIn(StrictModel):
    ids: list[uuid.UUID] = Field(min_length=2, max_length=3)
    school_id: uuid.UUID | None = None


class ReviewIn(StrictModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)


class ReportIn(StrictModel):
    target_type: Literal["room", "review"]
    target_id: uuid.UUID
    reason: str = Field(min_length=3, max_length=1000)


class BookingIn(StrictModel):
    room_id: uuid.UUID
    slot_start: datetime
    student_note: str | None = Field(default=None, max_length=500)

    @field_validator("slot_start")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Thời gian phải có múi giờ, vd 2026-11-21T16:00:00+07:00")
        if not YEAR_MIN <= v.year <= YEAR_MAX:
            raise ValueError(f"Năm phải trong khoảng {YEAR_MIN}-{YEAR_MAX}")
        local = v.astimezone(VN)
        if local.second or local.microsecond or local.minute % BOOKING_STEP_MIN:
            raise ValueError(f"Giờ hẹn phải rơi vào mốc {BOOKING_STEP_MIN} phút (:00, :15, :30, :45)")
        minutes = local.hour * 60 + local.minute
        if not BOOKING_FIRST_HOUR * 60 <= minutes <= BOOKING_LAST_HOUR * 60:
            raise ValueError(f"Giờ hẹn trong khoảng {BOOKING_FIRST_HOUR:02d}:00-{BOOKING_LAST_HOUR:02d}:00")
        return v


class BookingAction(StrictModel):
    note: str | None = Field(default=None, max_length=500)


# ---------- Chủ trọ ----------
class HouseIn(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    address_private: str = Field(min_length=1, max_length=255)
    street: str = Field(min_length=1, max_length=120)
    ward: str = Field(min_length=1, max_length=120)
    area: str = Field(min_length=1, max_length=120)
    city: str = Field(default="Hà Nội", min_length=1, max_length=120)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def _both_coords(self):
        if (self.lat is None) != (self.lng is None):
            raise ValueError("Cần nhập cả vĩ độ và kinh độ, hoặc để trống cả hai")  # BE-15
        return self


class HousePatch(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    address_private: str | None = Field(default=None, min_length=1, max_length=255)
    street: str | None = Field(default=None, min_length=1, max_length=120)
    ward: str | None = Field(default=None, min_length=1, max_length=120)
    area: str | None = Field(default=None, min_length=1, max_length=120)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


class CostRatesIn(StrictModel):
    electricity_per_kwh: int = Field(default=0, ge=0, le=MAX_KWH_RATE)
    water_mode: Literal["per_m3", "per_person"] = "per_m3"
    water_per_m3: int = Field(default=0, ge=0, le=MAX_M3_RATE)
    water_per_person: int = Field(default=0, ge=0, le=MAX_PERSON_RATE)
    internet_per_month: int = Field(default=0, ge=0, le=MAX_MONTHLY_FEE)
    parking_per_vehicle: int = Field(default=0, ge=0, le=MAX_MONTHLY_FEE)
    service_per_month: int = Field(default=0, ge=0, le=MAX_MONTHLY_FEE)


class RoomIn(StrictModel):
    house_id: uuid.UUID
    title: RoomTitle
    description: str = Field(default="", max_length=5000)
    price_month: Rent
    deposit_amount: Deposit = 0
    area_m2: Area
    floor: int | None = Field(default=None, ge=-5, le=200)
    max_people: int = Field(default=2, ge=1, le=20)
    curfew_time: time | None = None
    available_from: SafeDate | None = None
    amenities: list[str] = Field(default_factory=list)
    cost_rates: CostRatesIn = Field(default_factory=CostRatesIn)


class RoomPatch(StrictModel):
    house_id: uuid.UUID | None = None
    title: RoomTitle | None = None
    description: str | None = Field(default=None, max_length=5000)
    price_month: Rent | None = None
    deposit_amount: Deposit | None = None
    area_m2: Area | None = None
    floor: int | None = Field(default=None, ge=-5, le=200)
    max_people: int | None = Field(default=None, ge=1, le=20)
    curfew_time: time | None = None
    available_from: SafeDate | None = None
    amenities: list[str] | None = None
    cost_rates: CostRatesIn | None = None


class TenantIn(StrictModel):
    room_id: uuid.UUID
    full_name: PersonName
    phone: Phone = None
    email: OptionalEmail = None
    start_date: SafeDate
    end_date: SafeDate | None = None
    deposit_amount: Deposit = 0
    people_count: int = Field(default=1, ge=1, le=20)
    vehicle_count: int = Field(default=1, ge=0, le=20)


class TenantPatch(StrictModel):
    full_name: PersonName | None = None
    phone: Phone = None
    email: OptionalEmail = None
    start_date: SafeDate | None = None
    end_date: SafeDate | None = None
    deposit_amount: Deposit | None = None
    people_count: int | None = Field(default=None, ge=1, le=20)
    vehicle_count: int | None = Field(default=None, ge=0, le=20)
    is_active: bool | None = None


MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def parse_month(v: str) -> date:
    if not MONTH_RE.match(v):
        raise ValueError("Tháng có dạng YYYY-MM")
    y, m = v.split("-")
    if not YEAR_MIN <= int(y) <= YEAR_MAX:
        raise ValueError(f"Năm phải trong khoảng {YEAR_MIN}-{YEAR_MAX}")
    return date(int(y), int(m), 1)


class MeterReadingIn(StrictModel):
    room_id: uuid.UUID
    month: str  # "2026-10" -> period = 2026-10-01
    electricity_index: MeterIndex
    water_index: MeterIndex

    @field_validator("month")
    @classmethod
    def _month(cls, v: str) -> str:
        parse_month(v)
        return v


class InvoiceGenerateIn(StrictModel):
    month: str

    @field_validator("month")
    @classmethod
    def _month(cls, v: str) -> str:
        parse_month(v)
        return v


# ---------- Quản trị ----------
class ApproveIn(StrictModel):
    image_ids_ok: list[uuid.UUID] | None = None


class RejectIn(StrictModel):
    reason: str = Field(min_length=3, max_length=1000)


class ResolveReportIn(StrictModel):
    action: Literal["resolve", "dismiss"] = "resolve"
    hide_review: bool = False


class ResyncIn(StrictModel):
    room_id: uuid.UUID | None = None
