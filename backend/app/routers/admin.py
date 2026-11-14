"""Quản trị: duyệt tin, xác minh chủ trọ, báo cáo, trạng thái hệ thống, đồng bộ lại, sao lưu (F03, F14)."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import exists, func, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import AppError, invalid_transition, not_found
from ..models import House, JobRun, ProcessedMessage, Report, Review, Room, RoomImage, SyncOutbox, User
from ..schemas import ApproveIn, RejectIn, ResolveReportIn, ResyncIn
from ..security import require_admin
from ..services import storage
from ..services.metrics import fallback_last_hour
from ..services.outbox import landlord_rooms_changed, published_room_changed, room_changed
from ..services.search_service import azure_reachable
from .common import Page, audit, iso, paginate, short_name
from .landlord import image_out, room_full

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _room_for_update(db: Session, room_id: uuid.UUID) -> Room:
    room = db.scalars(select(Room).where(Room.id == room_id).with_for_update(of=Room)).first()
    if room is None:
        raise not_found("Không tìm thấy phòng")
    return room


def _admin_room(db: Session, room: Room) -> dict:
    landlord = room.house.landlord
    return room_full(db, room) | {
        "landlord": {"id": str(landlord.id), "full_name": landlord.full_name, "verified": landlord.verified},
    }


# ---------- Duyệt tin ----------
@router.get("/rooms")
def list_rooms(
    status: str = Query("pending", pattern="^(draft|pending|published|hidden|rejected)$"),
    pending_images: bool = False,
    page: Page = Depends(),
    db: Session = Depends(get_db),
):
    stmt = select(Room).where(Room.status == status)
    if pending_images:
        stmt = stmt.where(exists().where(RoomImage.room_id == Room.id, RoomImage.moderation == "pending"))
    rows, total = paginate(db, stmt.order_by(Room.updated_at.asc(), Room.id), page)
    return page.wrap([_admin_room(db, r) for r in rows], total)


@router.post("/rooms/{room_id}/approve")
def approve(
    room_id: uuid.UUID,
    body: ApproveIn | None = Body(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Duyệt phòng `pending` → `published`. Với phòng đang `published`, dùng để duyệt ảnh mới."""
    room = _room_for_update(db, room_id)
    if room.status not in ("pending", "published"):
        raise invalid_transition(f"Không thể duyệt phòng đang ở trạng thái {room.status}")
    pending_imgs = db.scalars(select(RoomImage).where(RoomImage.room_id == room.id, RoomImage.moderation == "pending")).all()
    ok_ids = set(body.image_ids_ok) if body and body.image_ids_ok is not None else None
    for img in pending_imgs:
        if ok_ids is None or img.id in ok_ids:
            img.moderation = "ok"
        else:
            img.moderation = "rejected"
            img.moderation_note = "Ảnh không đạt yêu cầu"
    was_published = room.status == "published"
    if not was_published:
        room.status = "published"
        room.published_at = datetime.now(timezone.utc)
        room.reject_reason = None
    room_changed(db, room, was_published=was_published, reason="approve")
    audit(db, admin, "room.approve", "room", room.id)
    db.commit()
    return _admin_room(db, room)


@router.post("/rooms/{room_id}/reject")
def reject(room_id: uuid.UUID, body: RejectIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Từ chối tin chờ duyệt, hoặc gỡ tin đang công khai vi phạm (ghi outbox delete)."""
    room = _room_for_update(db, room_id)
    if room.status not in ("pending", "published"):
        raise invalid_transition(f"Không thể từ chối phòng đang ở trạng thái {room.status}")
    was_published = room.status == "published"
    room.status = "rejected"
    room.reject_reason = body.reason
    room_changed(db, room, was_published=was_published, reason="reject")
    audit(db, admin, "room.reject", "room", room.id)
    db.commit()
    return _admin_room(db, room)


# ---------- Chủ trọ ----------
@router.get("/landlords")
def list_landlords(db: Session = Depends(get_db)):
    """Đề xuất bổ sung SPEC: danh sách chủ trọ để quản trị xác minh."""
    rows = db.execute(
        select(User, func.count(Room.id))
        .outerjoin(House, House.landlord_id == User.id)
        .outerjoin(Room, Room.house_id == House.id)
        .where(User.role == "landlord")
        .group_by(User.id)
        .order_by(User.created_at)
    ).all()
    return [
        {"id": str(u.id), "full_name": u.full_name, "email": u.email, "phone": u.phone, "verified": u.verified,
         "room_count": n, "created_at": iso(u.created_at)}
        for u, n in rows
    ]


def _set_verified(db: Session, landlord_id: uuid.UUID, admin: User, value: bool) -> dict:
    landlord = db.get(User, landlord_id)
    if landlord is None or landlord.role != "landlord":
        raise not_found("Không tìm thấy chủ trọ")
    changed = 0
    if landlord.verified != value:
        landlord.verified = value
        changed = landlord_rooms_changed(db, landlord.id, "landlord_verify")  # mọi phòng công khai (SPEC 9.2)
        audit(db, admin, "landlord.verify" if value else "landlord.unverify", "user", landlord.id)
    db.commit()
    return {"id": str(landlord.id), "verified": landlord.verified, "rooms_resynced": changed}


@router.post("/landlords/{landlord_id}/verify")
def verify(landlord_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return _set_verified(db, landlord_id, admin, True)


@router.post("/landlords/{landlord_id}/unverify")
def unverify(landlord_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return _set_verified(db, landlord_id, admin, False)


# ---------- Báo cáo ----------
def _report_out(db: Session, r: Report) -> dict:
    target: dict = {"type": r.target_type, "id": str(r.target_id)}
    if r.target_type == "review":
        rv = db.get(Review, r.target_id)
        if rv:
            target |= {"rating": rv.rating, "comment": rv.comment, "is_hidden": rv.is_hidden,
                       "room_id": str(rv.room_id), "student_name": short_name(rv.student.full_name)}
    else:
        room = db.get(Room, r.target_id)
        if room:
            target |= {"title": room.title, "status": room.status}
    return {
        "id": str(r.id), "reason": r.reason, "status": r.status, "created_at": iso(r.created_at),
        "resolved_at": iso(r.resolved_at), "target": target,
    }


@router.get("/reports")
def list_reports(
    status: str | None = Query("open", pattern="^(open|resolved|dismissed)$"),
    page: Page = Depends(),
    db: Session = Depends(get_db),
):
    stmt = select(Report)
    if status:
        stmt = stmt.where(Report.status == status)
    rows, total = paginate(db, stmt.order_by(Report.created_at.desc()), page)
    return page.wrap([_report_out(db, r) for r in rows], total)


@router.post("/reports/{report_id}/resolve")
def resolve_report(
    report_id: uuid.UUID,
    body: ResolveReportIn | None = Body(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    body = body or ResolveReportIn()
    report = db.get(Report, report_id)
    if report is None:
        raise not_found("Không tìm thấy báo cáo")
    if report.status != "open":
        raise invalid_transition("Báo cáo đã được xử lý")
    if body.hide_review:
        if report.target_type != "review":
            raise AppError(422, "VALIDATION_ERROR", "Báo cáo này không nhắm vào đánh giá")
        review = db.get(Review, report.target_id)
        if review and not review.is_hidden:
            review.is_hidden = True
            room = _room_for_update(db, review.room_id)
            published_room_changed(db, room, "review_hidden")  # rating_avg đổi (TC11)
    report.status = "dismissed" if body.action == "dismiss" else "resolved"
    report.resolved_by = admin.id
    report.resolved_at = datetime.now(timezone.utc)
    audit(db, admin, f"report.{report.status}", "report", report.id, hide_review=body.hide_review)
    db.commit()
    return _report_out(db, report)


# ---------- Trạng thái hệ thống ----------
def _db_ok(db: Session) -> bool:
    try:
        db.execute(select(1))
        return True
    except Exception:
        return False


def _job_out(j: JobRun | None) -> dict | None:
    if j is None:
        return None
    return {"id": j.id, "job": j.job, "status": j.status, "started_at": iso(j.started_at),
            "finished_at": iso(j.finished_at), "details": j.details}


@router.get("/system/status")
def system_status(db: Session = Depends(get_db)):
    pending = db.scalar(select(func.count()).where(SyncOutbox.status == "pending")) or 0
    failed = db.scalar(select(func.count()).where(SyncOutbox.status == "failed")) or 0
    last_sent = db.scalar(select(func.max(SyncOutbox.sent_at)))
    last_msg = db.scalar(select(func.max(ProcessedMessage.processed_at)))
    backup = db.scalars(select(JobRun).where(JobRun.job == "backup", JobRun.status == "success").order_by(JobRun.finished_at.desc()).limit(1)).first()
    restore = db.scalars(select(JobRun).where(JobRun.job == "restore_test", JobRun.status.in_(["success", "failed"])).order_by(JobRun.finished_at.desc()).limit(1)).first()
    failed_rows = db.scalars(select(SyncOutbox).where(SyncOutbox.status == "failed").order_by(SyncOutbox.id.desc()).limit(20)).all()
    recent_jobs = db.scalars(select(JobRun).order_by(JobRun.id.desc()).limit(15)).all()
    return {
        "db": _db_ok(db),
        "minio": storage.healthy(),
        "azure_search_reachable": azure_reachable(),
        "outbox": {"pending": pending, "failed": failed, "last_sent_at": iso(last_sent)},
        "queue": {"last_message_at": iso(last_msg)},
        "backup": {
            "last_success_at": iso(backup.finished_at) if backup else None,
            "size_bytes": backup.details.get("size_bytes") if backup else None,
            "duration_ms": backup.details.get("duration_ms") if backup else None,
        },
        "restore_test": {
            "last_at": iso(restore.finished_at) if restore else None,
            "total_ms": restore.details.get("total_ms") if restore else None,
            "counts_match": restore.details.get("counts_match") if restore else None,
        },
        "search_fallback_last_hour": fallback_last_hour(),
        # Thông tin thêm cho trang trạng thái (không có trong ví dụ SPEC, không chứa dữ liệu cá nhân)
        "outbox_failed_rows": [
            {"id": o.id, "room_id": str(o.entity_id), "op": o.op, "attempts": o.attempts,
             "last_error": (o.last_error or "")[:300], "created_at": iso(o.created_at)}
            for o in failed_rows
        ],
        "recent_jobs": [_job_out(j) for j in recent_jobs],
    }


@router.post("/sync/resync")
def resync(body: ResyncIn | None = Body(None), admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Đặt lại dòng lỗi về pending và xếp lại tài liệu cho một phòng hoặc mọi phòng công khai."""
    room_id = body.room_id if body else None
    job = JobRun(job="sync_resync", status="running", details={"room_id": str(room_id) if room_id else None})
    db.add(job)
    reset_q = update(SyncOutbox).where(SyncOutbox.status == "failed")
    if room_id:
        reset_q = reset_q.where(SyncOutbox.entity_id == room_id)
    reset = db.execute(
        reset_q.values(status="pending", attempts=0, next_attempt_at=func.now(), last_error=None)
    ).rowcount
    if room_id:
        room = db.get(Room, room_id)
        if room is None:
            raise not_found("Không tìm thấy phòng")
        rooms = [room]
    else:
        rooms = db.scalars(select(Room).where(Room.status == "published")).all()
    for room in rooms:
        db.add(SyncOutbox(entity_type="room", entity_id=room.id, entity_version=room.version,
                          op="upsert" if room.status == "published" else "delete", payload={"reason": "resync"}))
    job.status = "success"
    job.finished_at = datetime.now(timezone.utc)
    job.details = job.details | {"reset_failed": reset, "enqueued": len(rooms)}
    audit(db, admin, "sync.resync", "room", room_id, enqueued=len(rooms))
    db.commit()
    return {"job_run_id": job.id, "reset_failed": reset, "enqueued": len(rooms)}


def _queue_job(db: Session, job: str, admin: User) -> dict:
    running = db.scalar(select(JobRun.id).where(JobRun.job == job, JobRun.status.in_(["queued", "running"])))
    if running:
        return {"job_run_id": running, "status": "already_queued"}
    jr = JobRun(job=job, status="queued", details={"requested_by": "admin"})
    db.add(jr)
    audit(db, admin, f"{job}.request", "job_run", None)
    db.commit()
    return {"job_run_id": jr.id, "status": "queued"}


@router.post("/backup/run", status_code=202)
def backup_run(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return _queue_job(db, "backup", admin)


@router.post("/backup/restore-test", status_code=202)
def restore_test(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return _queue_job(db, "restore_test", admin)


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(JobRun, job_id)
    if job is None:
        raise not_found("Không tìm thấy lần chạy")
    return _job_out(job)
