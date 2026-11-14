"""Chủ trọ: khách thuê, hợp đồng (file GIẢ), chỉ số điện nước, hóa đơn (F16, F17)."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..errors import AppError, invalid_transition, not_found
from ..models import House, Invoice, MeterReading, Room, Tenant, User
from ..schemas import InvoiceGenerateIn, MeterReadingIn, TenantIn, TenantPatch, parse_month
from ..security import create_signed_token, require_landlord
from ..services import storage
from ..services.invoices import generate_for_landlord
from .common import Page, audit, iso, owned_room, paginate

log = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/landlord", tags=["landlord-ops"])


# ---------- Khách thuê ----------
def tenant_out(t: Tenant) -> dict:
    return {
        "id": str(t.id), "room_id": str(t.room_id), "room_title": t.room.title, "full_name": t.full_name,
        "phone": t.phone, "email": t.email, "start_date": t.start_date.isoformat(),
        "end_date": t.end_date.isoformat() if t.end_date else None, "deposit_amount": t.deposit_amount,
        "people_count": t.people_count, "vehicle_count": t.vehicle_count, "is_active": t.is_active,
        "has_id_card": bool(t.id_card_object_key), "has_contract": bool(t.contract_object_key),
        "created_at": iso(t.created_at),
    }


def _owned_tenant(db: Session, tenant_id: uuid.UUID, user: User) -> Tenant:
    t = db.scalars(
        select(Tenant).join(Room, Room.id == Tenant.room_id).join(House, House.id == Room.house_id)
        .where(Tenant.id == tenant_id, House.landlord_id == user.id)
    ).first()
    if t is None:
        raise not_found("Không tìm thấy khách thuê")
    return t


@router.get("/tenants")
def list_tenants(
    room_id: uuid.UUID | None = None,
    active: bool | None = None,
    page: Page = Depends(),
    user: User = Depends(require_landlord),
    db: Session = Depends(get_db),
):
    stmt = select(Tenant).join(Room, Room.id == Tenant.room_id).join(House, House.id == Room.house_id).where(House.landlord_id == user.id)
    if room_id:
        stmt = stmt.where(Tenant.room_id == room_id)
    if active is not None:
        stmt = stmt.where(Tenant.is_active.is_(active))
    rows, total = paginate(db, stmt.order_by(Tenant.is_active.desc(), Tenant.start_date.desc()), page)
    return page.wrap([tenant_out(t) for t in rows], total)


@router.post("/tenants", status_code=201)
def create_tenant(body: TenantIn, user: User = Depends(require_landlord), db: Session = Depends(get_db)):
    owned_room(db, body.room_id, user)
    if body.end_date and body.end_date < body.start_date:
        raise AppError(422, "VALIDATION_ERROR", "Ngày kết thúc phải sau ngày bắt đầu")
    t = Tenant(**body.model_dump())
    db.add(t)
    db.flush()
    audit(db, user, "tenant.create", "tenant", t.id)
    db.commit()
    db.refresh(t)
    return tenant_out(t)


@router.patch("/tenants/{tenant_id}")
def update_tenant(tenant_id: uuid.UUID, body: TenantPatch, user: User = Depends(require_landlord), db: Session = Depends(get_db)):
    t = _owned_tenant(db, tenant_id, user)
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is None and key not in ("phone", "email", "end_date"):
            continue
        setattr(t, key, value)
    if t.end_date and t.end_date < t.start_date:
        raise AppError(422, "VALIDATION_ERROR", "Ngày kết thúc phải sau ngày bắt đầu")
    db.commit()
    db.refresh(t)
    return tenant_out(t)


@router.post("/tenants/{tenant_id}/files")
async def upload_tenant_file(
    tenant_id: uuid.UUID,
    kind: Literal["id_card", "contract"] = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(require_landlord),
    db: Session = Depends(get_db),
):
    """Tải CCCD/hợp đồng GIẢ vào bucket private. Chỉ nhận JPEG, PNG, PDF ≤ 10 MB."""
    t = _owned_tenant(db, tenant_id, user)
    data = await file.read(storage.MAX_FILE_BYTES + 1)
    if len(data) > storage.MAX_FILE_BYTES:
        raise AppError(422, "VALIDATION_ERROR", "File tối đa 10 MB")
    sniff = storage.sniff_document(data)
    if sniff is None:
        raise AppError(422, "VALIDATION_ERROR", "Chỉ nhận JPEG, PNG hoặc PDF")
    ctype, ext = sniff
    key = f"tenants/{t.id}/{kind}-{uuid.uuid4()}.{ext}"
    try:
        storage.put(settings.minio_bucket_private, key, data, ctype)
    except Exception as exc:
        log.error("Tải file lên MinIO lỗi: %s", type(exc).__name__)
        raise AppError(503, "UPSTREAM_UNAVAILABLE", "Kho file tạm thời không phản hồi")
    old = t.id_card_object_key if kind == "id_card" else t.contract_object_key
    if kind == "id_card":
        t.id_card_object_key = key
    else:
        t.contract_object_key = key
    db.commit()
    if old and old != key:
        storage.remove(settings.minio_bucket_private, old)
    return tenant_out(t)


@router.get("/tenants/{tenant_id}/files/{kind}")
def tenant_file_url(
    tenant_id: uuid.UUID,
    kind: Literal["id_card", "contract"],
    user: User = Depends(require_landlord),
    db: Session = Depends(get_db),
):
    """Trả URL ký trước hạn 5 phút (SPEC 19). Chỉ chủ trọ sở hữu gọi được."""
    t = _owned_tenant(db, tenant_id, user)
    key = t.id_card_object_key if kind == "id_card" else t.contract_object_key
    if not key:
        raise not_found("Chưa có file")
    token = create_signed_token("private-file", {"key": key}, minutes=5)
    return {"url": f"/api/v1/files/signed?token={token}", "expires_in": 300}


# ---------- Chỉ số công tơ ----------
def reading_out(m: MeterReading) -> dict:
    return {
        "id": str(m.id), "room_id": str(m.room_id), "period": m.period.isoformat(), "month": m.period.strftime("%Y-%m"),
        "electricity_index": float(m.electricity_index), "water_index": float(m.water_index), "source": m.source,
    }


@router.get("/meter-readings")
def list_readings(room_id: uuid.UUID, user: User = Depends(require_landlord), db: Session = Depends(get_db)):
    """Đề xuất bổ sung SPEC: xem lại các chỉ số đã nhập của một phòng."""
    owned_room(db, room_id, user)
    rows = db.scalars(select(MeterReading).where(MeterReading.room_id == room_id).order_by(MeterReading.period.desc())).all()
    return [reading_out(m) for m in rows]


@router.post("/meter-readings", status_code=201)
def upsert_reading(body: MeterReadingIn, user: User = Depends(require_landlord), db: Session = Depends(get_db)):
    owned_room(db, body.room_id, user)
    period = parse_month(body.month)
    stmt = (
        pg_insert(MeterReading)
        .values(room_id=body.room_id, period=period, electricity_index=body.electricity_index,
                water_index=body.water_index, source="manual")
        .on_conflict_do_update(
            index_elements=["room_id", "period"],
            set_={"electricity_index": body.electricity_index, "water_index": body.water_index},
        )
        .returning(MeterReading.id)
    )
    rid = db.execute(stmt).scalar_one()
    db.commit()
    return reading_out(db.get(MeterReading, rid))


# ---------- Hóa đơn ----------
def invoice_out(i: Invoice) -> dict:
    return {
        "id": str(i.id), "code": i.code, "tenant_id": str(i.tenant_id), "tenant_name": i.tenant.full_name,
        "room_id": str(i.room_id), "room_title": i.tenant.room.title, "period": i.period.isoformat(),
        "month": i.period.strftime("%Y-%m"), "rent": i.rent, "electricity_used": float(i.electricity_used),
        "electricity_amount": i.electricity_amount, "water_used": float(i.water_used), "water_amount": i.water_amount,
        "internet_amount": i.internet_amount, "parking_amount": i.parking_amount, "service_amount": i.service_amount,
        "other_amount": i.other_amount, "total": i.total, "status": i.status, "due_date": i.due_date.isoformat(),
        "paid_at": iso(i.paid_at),
    }


@router.post("/invoices/generate", status_code=201)
def generate_invoices(body: InvoiceGenerateIn, user: User = Depends(require_landlord), db: Session = Depends(get_db)):
    period = parse_month(body.month)
    result = generate_for_landlord(db, user.id, period)
    if not result["created"] and result["existing"]:
        db.rollback()
        raise AppError(409, "INVOICE_EXISTS", f"Hóa đơn tháng {body.month} đã được tạo", {"existing": len(result["existing"])})
    audit(db, user, "invoice.generate", "invoice", None, month=body.month, created=len(result["created"]))
    db.commit()
    for inv in result["created"]:
        db.refresh(inv)
    return {
        "month": body.month,
        "created": [invoice_out(i) for i in result["created"]],
        "skipped": result["skipped"],
        "existing_count": len(result["existing"]),
    }


@router.get("/invoices")
def list_invoices(
    month: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    status: str | None = Query(None, pattern="^(unpaid|paid|overdue|void)$"),
    page: Page = Depends(),
    user: User = Depends(require_landlord),
    db: Session = Depends(get_db),
):
    stmt = select(Invoice).join(Room, Room.id == Invoice.room_id).join(House, House.id == Room.house_id).where(House.landlord_id == user.id)
    if month:
        stmt = stmt.where(Invoice.period == parse_month(month))
    if status:
        stmt = stmt.where(Invoice.status == status)
    rows, total = paginate(db, stmt.order_by(Invoice.period.desc(), Invoice.code), page)
    return page.wrap([invoice_out(i) for i in rows], total)


@router.post("/invoices/{invoice_id}/paid")
def mark_paid(invoice_id: uuid.UUID, user: User = Depends(require_landlord), db: Session = Depends(get_db)):
    inv = db.scalars(
        select(Invoice).join(Room, Room.id == Invoice.room_id).join(House, House.id == Room.house_id)
        .where(Invoice.id == invoice_id, House.landlord_id == user.id)
    ).first()
    if inv is None:
        raise not_found("Không tìm thấy hóa đơn")
    if inv.status not in ("unpaid", "overdue"):
        raise invalid_transition(f"Không thể đánh dấu đã trả cho hóa đơn {inv.status}")
    inv.status = "paid"
    inv.paid_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(inv)
    return invoice_out(inv)
