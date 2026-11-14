"""Tạo hóa đơn tháng (F17, SPEC 9.8)."""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import CostRate, House, Invoice, MeterReading, Room, Tenant


def next_month(d: date) -> date:
    return date(d.year + (d.month == 12), 1 if d.month == 12 else d.month + 1, 1)


def month_end(d: date) -> date:
    from datetime import timedelta

    return next_month(d) - timedelta(days=1)


def generate_for_landlord(db: Session, landlord_id: uuid.UUID, period: date) -> dict:
    """Tạo hóa đơn tháng `period` (ngày 1) cho mọi khách đang thuê. Trả {created, skipped, existing}."""
    nxt = next_month(period)
    tenants = db.scalars(
        select(Tenant)
        .join(Room, Room.id == Tenant.room_id)
        .join(House, House.id == Room.house_id)
        .where(
            House.landlord_id == landlord_id,
            Tenant.is_active.is_(True),
            Tenant.start_date <= month_end(period),
        )
        .order_by(Tenant.created_at)
    ).unique().all()

    # Khóa số thứ tự theo tháng để hai yêu cầu đồng thời không sinh trùng mã.
    db.execute(select(func.pg_advisory_xact_lock(period.year * 100 + period.month)))
    prefix = f"HD-{period:%Y%m}-"
    last_code = db.scalar(select(func.max(Invoice.code)).where(Invoice.code.like(prefix + "%")))
    seq = int(last_code.rsplit("-", 1)[1]) if last_code else 0

    created, skipped, existing = [], [], []
    for t in tenants:
        if db.scalar(select(Invoice.id).where(Invoice.tenant_id == t.id, Invoice.period == period)):
            existing.append(str(t.id))
            continue
        cur = db.scalars(select(MeterReading).where(MeterReading.room_id == t.room_id, MeterReading.period == period)).first()
        nx = db.scalars(select(MeterReading).where(MeterReading.room_id == t.room_id, MeterReading.period == nxt)).first()
        if cur is None or nx is None:
            skipped.append({"tenant_id": str(t.id), "room_title": t.room.title,
                            "reason": f"Thiếu chỉ số ngày 1/{period.month} hoặc 1/{nxt.month}"})
            continue
        e_used = Decimal(nx.electricity_index) - Decimal(cur.electricity_index)
        w_used = Decimal(nx.water_index) - Decimal(cur.water_index)
        if e_used < 0 or w_used < 0:
            skipped.append({"tenant_id": str(t.id), "room_title": t.room.title, "reason": "Chỉ số tháng sau nhỏ hơn tháng trước"})
            continue
        cr = db.get(CostRate, t.room_id)
        e_rate = cr.electricity_per_kwh if cr else 0
        if cr and cr.water_mode == "per_person":
            water_amount = cr.water_per_person * t.people_count
        else:
            water_amount = int(round(w_used * (cr.water_per_m3 if cr else 0)))
        seq += 1
        inv = Invoice(
            code=f"{prefix}{seq:04d}",
            tenant_id=t.id,
            room_id=t.room_id,
            period=period,
            rent=t.room.price_month,
            electricity_used=e_used,
            electricity_amount=int(round(e_used * e_rate)),
            water_used=w_used,
            water_amount=water_amount,
            internet_amount=cr.internet_per_month if cr else 0,
            parking_amount=(cr.parking_per_vehicle if cr else 0) * t.vehicle_count,
            service_amount=cr.service_per_month if cr else 0,
            due_date=date(nxt.year, nxt.month, 10),  # hạn ngày 10 tháng M+1
        )
        db.add(inv)
        created.append(inv)
    db.flush()
    return {"created": created, "skipped": skipped, "existing": existing}
