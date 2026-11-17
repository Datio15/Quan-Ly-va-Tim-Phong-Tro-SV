import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from azure.storage.blob import BlobServiceClient, ContentSettings
from minio import Minio
from sqlalchemy import text
from sqlalchemy.orm import Session

from worker.db import SessionLocal

logger = logging.getLogger(__name__)

#24 truong cho phep gui sang Azure AI Search
ALLOWED_FIELDS = {
"id", "title", "description", "price_month", "est_monthly_cost", "deposit_amount",
    "area_m2", "max_people", "floor", "street", "ward", "area", "city", "location",
    "amenities", "curfew", "curfew_time", "available_from", "landlord_verified",
    "rating_avg", "rating_count", "image_urls", "version", "updated_at",
}

_warned_missing_key = False

def _get_minio_client() -> Minio:
    endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
    secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
    return Minio(
        endpoint,
        access_key=os.getenv("MINIO_ROOT_USER", ""),
        secret_key=os.getenv("MINIO_ROOT_PASSWORD", ""),
        secure=secure,
    )

def _get_blob_container_client():
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    service = BlobServiceClient.from_connection_string(conn_str)
    return service.get_container_client("public-images")


def _sync_room_images(db: Session, room_id: str) -> list[str]:
    """Đẩy các ảnh đã duyệt (moderation='ok') chưa có public_url từ MinIO lên Azure Blob."""
    rows = db.execute(
        text("""
            SELECT id, object_key, public_url
            FROM room_images
            WHERE room_id = :room_id AND moderation = 'ok'
            ORDER BY position ASC, created_at ASC
        """),
        {"room_id": room_id},
    ).mappings().all()

    if not rows:
        return []

    need_upload = [r for r in rows if not r["public_url"]]
    minio_client = _get_minio_client() if need_upload else None
    container_client = _get_blob_container_client() if need_upload else None
    src_bucket = os.getenv("MINIO_BUCKET_PUBLIC_SRC", "public-src")
    public_base = os.getenv("AZURE_BLOB_PUBLIC_BASE_URL", "").rstrip("/")

    urls: list[str] = []
    for row in rows:
        if row["public_url"]:
            urls.append(row["public_url"])
            continue

        img_id = str(row["id"])
        obj_key = row["object_key"]
        ext = "png" if obj_key.lower().endswith(".png") else "jpg"
        content_type = "image/png" if ext == "png" else "image/jpeg"
        blob_name = f"rooms/{room_id}/{img_id}.{ext}"

        resp = minio_client.get_object(src_bucket, obj_key)
        try:
            data = resp.read()
        finally:
            resp.close()
            resp.release_conn()

        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )

        public_url = f"{public_base}/{blob_name}" if public_base else blob_client.url
        db.execute(
            text("UPDATE room_images SET public_url = :url WHERE id = :id"),
            {"url": public_url, "id": row["id"]},
        )
        urls.append(public_url)

    return urls


def _delete_room_blobs(room_id: str) -> None:
    """Xóa toàn bộ ảnh của phòng trên Azure Blob public-images khi phòng bị gỡ/ẩn."""
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    if not conn_str:
        return
    container_client = _get_blob_container_client()
    prefix = f"rooms/{room_id}/"
    for blob in container_client.list_blobs(name_starts_with=prefix):
        container_client.delete_blob(blob.name)


def _build_public_document(db: Session, room_row: Any, image_urls: list[str]) -> dict[str, Any]:
    """Dựng payload đúng 24 trường cho phép từ v_rooms_public."""
    room_id = str(room_row["id"])
    kwh = float(os.getenv("EST_KWH_PER_MONTH", "100"))
    m3 = float(os.getenv("EST_WATER_M3_PER_MONTH", "4"))
    people = int(os.getenv("EST_PEOPLE", "1"))
    vehicles = int(os.getenv("EST_VEHICLES", "1"))

    cost_res = db.execute(
        text("SELECT total FROM room_monthly_cost(:rid, :kwh, :m3, :people, :vehicles)"),
        {"rid": room_id, "kwh": kwh, "m3": m3, "people": people, "vehicles": vehicles},
    ).scalar()

    location = None
    if room_row["lat"] is not None and room_row["lng"] is not None:
        location = {
            "type": "Point",
            "coordinates": [float(room_row["lng"]), float(room_row["lat"])],
        }

    raw_doc = {
        "id": room_id,
        "title": room_row["title"],
        "description": room_row["description"] or "",
        "price_month": int(room_row["price_month"]),
        "est_monthly_cost": int(cost_res or room_row["price_month"]),
        "deposit_amount": int(room_row["deposit_amount"]),
        "area_m2": float(room_row["area_m2"]),
        "max_people": int(room_row["max_people"]),
        "floor": room_row["floor"],
        "street": room_row["street"],
        "ward": room_row["ward"],
        "area": room_row["area"],
        "city": room_row["city"],
        "location": location,
        "amenities": list(room_row["amenities"] or []),
        "curfew": bool(room_row["curfew"]),
        "curfew_time": room_row["curfew_time"].isoformat() if room_row["curfew_time"] else None,
        "available_from": room_row["available_from"].isoformat() if room_row["available_from"] else None,
        "landlord_verified": bool(room_row["landlord_verified"]),
        "rating_avg": float(room_row["rating_avg"]) if room_row["rating_avg"] is not None else None,
        "rating_count": int(room_row["rating_count"] or 0),
        "image_urls": image_urls,
        "version": int(room_row["version"]),
        "updated_at": room_row["updated_at"].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return {k: v for k, v in raw_doc.items() if k in ALLOWED_FIELDS}


def process_sync_outbox() -> None:
    """Xử lý batch tối đa 10 bản ghi đến hạn trong sync_outbox."""
    global _warned_missing_key

    func_url = os.getenv("AZURE_FUNCTION_INGEST_URL", "").strip()
    func_key = os.getenv("AZURE_FUNCTION_KEY", "").strip()
    max_attempts = int(os.getenv("OUTBOX_MAX_ATTEMPTS", "10"))

    # SPEC mục 12.1: Tạm dừng nếu chưa có khóa hàm thật, không tăng attempts
    if not func_url or not func_key or func_key == "CHANGE_ME":
        if not _warned_missing_key:
            logger.warning("[Outbox] Tạm dừng đồng bộ vì chưa cấu hình AZURE_FUNCTION_URL/KEY.")
            _warned_missing_key = True
        return
    _warned_missing_key = False

    with SessionLocal() as db:
        rows = db.execute(
            text("""
                SELECT id, entity_id, entity_version, op, attempts
                FROM sync_outbox
                WHERE status = 'pending' AND next_attempt_at <= now()
                ORDER BY id ASC
                LIMIT 10
                FOR UPDATE SKIP LOCKED
            """)
        ).mappings().all()

        if not rows:
            return

        for item in rows:
            outbox_id = item["id"]
            room_id = str(item["entity_id"])
            op = item["op"]
            version = int(item["entity_version"])

            try:
                # 1. Bỏ qua nếu đã có dòng pending mới hơn cho cùng phòng
                newer = db.execute(
                    text("""
                        SELECT 1 FROM sync_outbox
                        WHERE entity_id = :rid AND status = 'pending' AND id > :oid
                        LIMIT 1
                    """),
                    {"rid": room_id, "oid": outbox_id},
                ).first()

                if newer:
                    db.execute(
                        text("UPDATE sync_outbox SET status = 'sent', sent_at = now() WHERE id = :oid"),
                        {"oid": outbox_id},
                    )
                    db.commit()
                    continue

                # 2. Đọc trạng thái hiện tại từ v_rooms_public
                room_row = db.execute(
                    text("SELECT * FROM v_rooms_public WHERE id = :rid"),
                    {"rid": room_id},
                ).mappings().first()

                if not room_row or room_row["status"] != "published":
                    op = "delete"
                else:
                    version = max(version, int(room_row["version"]))

                # 3. Chuẩn bị payload gửi sang Function ingest-room
                if op == "upsert":
                    image_urls = _sync_room_images(db, room_id)
                    doc = _build_public_document(db, room_row, image_urls)
                    payload = {"op": "upsert", "room": doc}
                else:
                    _delete_room_blobs(room_id)
                    payload = {"op": "delete", "room": {"id": room_id, "version": version}}

                # 4. Gọi Azure Function ingest-room
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post(
                        func_url,
                        json=payload,
                        headers={"x-functions-key": func_key},
                    )
                    resp.raise_for_status()

                # 5. Đánh dấu đã gửi thành công
                db.execute(
                    text("UPDATE sync_outbox SET status = 'sent', sent_at = now(), last_error = NULL WHERE id = :oid"),
                    {"oid": outbox_id},
                )
                db.commit()
                logger.info("[Outbox] Đồng bộ thành công room=%s op=%s (id=%s)", room_id, op, outbox_id)

            except Exception as exc:
                db.rollback()
                new_attempts = int(item["attempts"]) + 1
                err_msg = str(exc)[:500]
                if new_attempts >= max_attempts:
                    db.execute(
                        text("""
                            UPDATE sync_outbox
                            SET status = 'failed', attempts = :att, last_error = :err
                            WHERE id = :oid
                        """),
                        {"att": new_attempts, "err": err_msg, "oid": outbox_id},
                    )
                else:
                    delay_sec = min(30 * (2 ** new_attempts), 1800)
                    next_at = datetime.now(timezone.utc) + timedelta(seconds=delay_sec)
                    db.execute(
                        text("""
                            UPDATE sync_outbox
                            SET attempts = :att, last_error = :err, next_attempt_at = :next_at
                            WHERE id = :oid
                        """),
                        {"att": new_attempts, "err": err_msg, "next_at": next_at, "oid": outbox_id},
                    )
                db.commit()
                logger.warning("[Outbox] Lỗi đồng bộ id=%s (lần %s): %s", outbox_id, new_attempts, err_msg)
