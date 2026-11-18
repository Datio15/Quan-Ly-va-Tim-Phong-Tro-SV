"""Pydantic request schema. Phản hồi phần lớn dựng bằng dict theo đúng ví dụ ở SPEC 10.4."""
import re
import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")  # cùng điều kiện CHECK trong schema.sql
PHONE_RE = re.compile(r"^\+?[0-9]{9,12}$")
AMENITY_RE = re.compile(r"^[a-z_]+$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _check_phone(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    if not PHONE_RE.match(v):
        raise ValueError("Số điện thoại gồm 9-12 chữ số")
    return v


Phone = Annotated[str | None, AfterValidator(_check_phone)]

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
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=100)
    phone: Phone = None
    role: Literal["student", "landlord"]

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        if not EMAIL_RE.match(v):
            raise ValueError("Email không hợp lệ")
        return v.lower()


class LoginIn(StrictModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.lower()


class MePatch(StrictModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
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
    title: str = Field(min_length=5, max_length=120)
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
    title: str | None = Field(default=None, min_length=5, max_length=120)
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
    full_name: str = Field(min_length=2, max_length=100)
    phone: Phone = None
    email: str | None = None
    start_date: SafeDate
    end_date: SafeDate | None = None
    deposit_amount: Deposit = 0
    people_count: int = Field(default=1, ge=1, le=20)
    vehicle_count: int = Field(default=1, ge=0, le=20)


class TenantPatch(StrictModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    phone: Phone = None
    email: str | None = None
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
