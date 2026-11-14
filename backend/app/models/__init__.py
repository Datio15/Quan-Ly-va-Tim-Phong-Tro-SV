"""SQLAlchemy model ánh xạ đúng backend/db/schema.sql. KHÔNG tạo bảng từ đây (schema.sql là nguồn)."""
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Computed, Date, DateTime, Double, ForeignKey, Integer, Numeric, SmallInteger, Text, Time, func
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


def _enum(name: str, *values: str) -> ENUM:
    return ENUM(*values, name=name, create_type=False)


UserRole = _enum("user_role", "student", "landlord", "admin")
RoomStatus = _enum("room_status", "draft", "pending", "published", "hidden", "rejected")
ModerationStatus = _enum("moderation_status", "pending", "ok", "rejected")
BookingStatus = _enum("booking_status", "requested", "confirmed", "declined", "cancelled", "done")
InvoiceStatus = _enum("invoice_status", "unpaid", "paid", "overdue", "void")
ReportStatus = _enum("report_status", "open", "resolved", "dismissed")
ReadingSource = _enum("reading_source", "manual", "ocr")
WaterMode = _enum("water_mode", "per_m3", "per_person")
SyncOp = _enum("sync_op", "upsert", "delete")
SyncStatus = _enum("sync_status", "pending", "sent", "failed")
JobStatus = _enum("job_status", "queued", "running", "success", "failed")


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------- Người dùng ----------
class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(UserRole)
    verified: Mapped[bool] = mapped_column(Boolean, server_default="false")
    telegram_chat_id: Mapped[str | None] = mapped_column(Text)
    telegram_link_code: Mapped[str | None] = mapped_column(Text)
    telegram_link_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class School(Base):
    __tablename__ = "schools"
    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(Text)
    short_name: Mapped[str] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Double)
    lng: Mapped[float] = mapped_column(Double)


class Amenity(Base):
    __tablename__ = "amenities"
    code: Mapped[str] = mapped_column(Text, primary_key=True)
    label_vi: Mapped[str] = mapped_column(Text)


# ---------- Tin đăng ----------
class House(Base):
    __tablename__ = "houses"
    id: Mapped[uuid.UUID] = _pk()
    landlord_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(Text)
    address_private: Mapped[str] = mapped_column(Text)
    street: Mapped[str] = mapped_column(Text)
    ward: Mapped[str] = mapped_column(Text)
    area: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Double)
    lng: Mapped[float | None] = mapped_column(Double)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    landlord: Mapped[User] = relationship(lazy="joined")


class Room(Base):
    __tablename__ = "rooms"
    id: Mapped[uuid.UUID] = _pk()
    house_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("houses.id"))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    price_month: Mapped[int] = mapped_column(Integer)
    deposit_amount: Mapped[int] = mapped_column(Integer, server_default="0")
    area_m2: Mapped[Decimal] = mapped_column(Numeric(6, 1))
    floor: Mapped[int | None] = mapped_column(SmallInteger)
    max_people: Mapped[int] = mapped_column(SmallInteger, server_default="2")
    curfew_time: Mapped[time | None] = mapped_column(Time)
    available_from: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(RoomStatus, server_default="draft")
    reject_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    house: Mapped[House] = relationship(lazy="joined")


class RoomAmenity(Base):
    __tablename__ = "room_amenities"
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id"), primary_key=True)
    amenity_code: Mapped[str] = mapped_column(ForeignKey("amenities.code"), primary_key=True)


class RoomImage(Base):
    __tablename__ = "room_images"
    id: Mapped[uuid.UUID] = _pk()
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id"))
    object_key: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    moderation: Mapped[str] = mapped_column(ModerationStatus, server_default="pending")
    moderation_note: Mapped[str | None] = mapped_column(Text)
    public_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


class CostRate(Base):
    __tablename__ = "cost_rates"
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id"), primary_key=True)
    electricity_per_kwh: Mapped[int] = mapped_column(Integer, server_default="0")
    water_mode: Mapped[str] = mapped_column(WaterMode, server_default="per_m3")
    water_per_m3: Mapped[int] = mapped_column(Integer, server_default="0")
    water_per_person: Mapped[int] = mapped_column(Integer, server_default="0")
    internet_per_month: Mapped[int] = mapped_column(Integer, server_default="0")
    parking_per_vehicle: Mapped[int] = mapped_column(Integer, server_default="0")
    service_per_month: Mapped[int] = mapped_column(Integer, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------- Sinh viên ----------
class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id"), primary_key=True)
    created_at: Mapped[datetime] = _created()


class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[uuid.UUID] = _pk()
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id"))
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(BookingStatus, server_default="requested")
    student_note: Mapped[str | None] = mapped_column(Text)
    landlord_note: Mapped[str | None] = mapped_column(Text)
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    room: Mapped[Room] = relationship(lazy="joined")
    student: Mapped[User] = relationship(lazy="joined")


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[uuid.UUID] = _pk()
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id"))
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    rating: Mapped[int] = mapped_column(SmallInteger)
    comment: Mapped[str] = mapped_column(Text, server_default="")
    is_hidden: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = _created()

    student: Mapped[User] = relationship(lazy="joined")


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[uuid.UUID] = _pk()
    target_type: Mapped[str] = mapped_column(Text)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    reporter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(ReportStatus, server_default="open")
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = _created()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------- Chủ trọ ----------
class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[uuid.UUID] = _pk()
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id"))
    full_name: Mapped[str] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    id_card_object_key: Mapped[str | None] = mapped_column(Text)
    contract_object_key: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    deposit_amount: Mapped[int] = mapped_column(Integer, server_default="0")
    people_count: Mapped[int] = mapped_column(SmallInteger, server_default="1")
    vehicle_count: Mapped[int] = mapped_column(SmallInteger, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = _created()

    room: Mapped[Room] = relationship(lazy="joined")


class MeterReading(Base):
    __tablename__ = "meter_readings"
    id: Mapped[uuid.UUID] = _pk()
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id"))
    period: Mapped[date] = mapped_column(Date)
    electricity_index: Mapped[Decimal] = mapped_column(Numeric(10, 1))
    water_index: Mapped[Decimal] = mapped_column(Numeric(10, 1))
    photo_object_key: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(ReadingSource, server_default="manual")
    created_at: Mapped[datetime] = _created()


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[uuid.UUID] = _pk()
    code: Mapped[str] = mapped_column(Text)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id"))
    period: Mapped[date] = mapped_column(Date)
    rent: Mapped[int] = mapped_column(Integer)
    electricity_used: Mapped[Decimal] = mapped_column(Numeric(10, 1), server_default="0")
    electricity_amount: Mapped[int] = mapped_column(Integer, server_default="0")
    water_used: Mapped[Decimal] = mapped_column(Numeric(10, 1), server_default="0")
    water_amount: Mapped[int] = mapped_column(Integer, server_default="0")
    internet_amount: Mapped[int] = mapped_column(Integer, server_default="0")
    parking_amount: Mapped[int] = mapped_column(Integer, server_default="0")
    service_amount: Mapped[int] = mapped_column(Integer, server_default="0")
    other_amount: Mapped[int] = mapped_column(Integer, server_default="0")
    total: Mapped[int] = mapped_column(
        Integer,
        Computed("rent + electricity_amount + water_amount + internet_amount + parking_amount + service_amount + other_amount"),
    )
    status: Mapped[str] = mapped_column(InvoiceStatus, server_default="unpaid")
    due_date: Mapped[date] = mapped_column(Date)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pdf_object_key: Mapped[str | None] = mapped_column(Text)
    qr_payload: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()

    tenant: Mapped[Tenant] = relationship(lazy="joined")


# ---------- Kỹ thuật ----------
class SyncOutbox(Base):
    __tablename__ = "sync_outbox"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    entity_version: Mapped[int] = mapped_column(Integer)
    op: Mapped[str] = mapped_column(SyncOp)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(SyncStatus, server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = _created()
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobRun(Base):
    __tablename__ = "job_runs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(JobStatus, server_default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict] = mapped_column(JSONB, server_default="{}")


class ProcessedMessage(Base):
    __tablename__ = "processed_messages"
    message_id: Mapped[str] = mapped_column(Text, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    channel: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    ref_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(Text)
    entity: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    meta: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    created_at: Mapped[datetime] = _created()
