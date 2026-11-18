"""Gắn ảnh phòng tượng trưng (seed/room-photos) ngẫu nhiên cho các phòng trong dữ liệu mẫu.

Chạy: python -m app.seed_images [THƯ_MỤC_ẢNH] [--force]
      (mặc định /srv/seed-photos – docker-compose gắn ./seed/room-photos vào đây)

- Chỉ đụng phòng của dữ liệu mẫu (id uuid5 do seed/generate_seed.py sinh), không bao giờ gắn ảnh
  cho phòng chủ trọ tự tạo (uuid4), và bỏ qua phòng đã có ảnh.
- Mỗi CSDL chỉ chạy một lần (đánh dấu bằng audit_log action='seed.images'); --force để chạy lại.
- Ngẫu nhiên nhưng tái lập được: cùng phòng luôn nhận cùng bộ ảnh (random theo room id).
- Phòng published/hidden: ảnh moderation='ok'. Phòng chờ duyệt/nháp/bị từ chối: 'pending'
  (để demo quản trị duyệt ảnh). Phòng đang công khai mà chưa có dòng outbox chờ thì ghi outbox (SPEC 9.2).
"""
import random
import sys
import time
import uuid
from pathlib import Path

from sqlalchemy import exists, select

from .config import get_settings
from .db import SessionLocal
from .models import AuditLog, Room, RoomImage, SyncOutbox
from .seed_passwords import wait_for_db
from .services import storage
from .services.outbox import room_changed

MARK = "seed.images"
MIN_PER_ROOM, MAX_PER_ROOM = 2, 4


def _wait_for_minio(seconds: int = 60) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if storage.healthy():
            return True
        time.sleep(2)
    return False


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    photo_dir = Path(args[0] if args else "/srv/seed-photos")
    photos = sorted(p for p in photo_dir.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")) if photo_dir.is_dir() else []
    if not photos:
        print(f"Bỏ qua gắn ảnh mẫu: không có ảnh trong {photo_dir}")
        return

    settings = get_settings()
    wait_for_db()
    with SessionLocal() as db:
        if not force and db.scalar(select(exists().where(AuditLog.action == MARK))):
            print("Ảnh mẫu đã được gắn trước đó (dùng --force để chạy lại)")
            return
        if not _wait_for_minio():
            print("Bỏ qua gắn ảnh mẫu: MinIO chưa sẵn sàng")
            return
        storage.ensure_buckets()

        rooms = db.scalars(
            select(Room).where(~exists().where(RoomImage.room_id == Room.id)).order_by(Room.id)
        ).all()
        rooms = [r for r in rooms if r.id.version == 5]  # chỉ phòng của dữ liệu mẫu
        data = {p: p.read_bytes() for p in photos}
        added = enqueued = 0
        for room in rooms:
            rng = random.Random(str(room.id))
            picks = rng.sample(photos, k=min(len(photos), rng.randint(MIN_PER_ROOM, MAX_PER_ROOM)))
            moderation = "ok" if room.status in ("published", "hidden") else "pending"
            for pos, photo in enumerate(picks):
                content = data[photo]
                kind = storage.sniff_image(content)
                if kind is None:
                    continue
                ctype, ext = kind
                image_id = uuid.uuid4()
                key = f"rooms/{room.id}/{image_id}.{ext}"
                storage.put(settings.minio_bucket_public_src, key, content, ctype)
                db.add(RoomImage(id=image_id, room_id=room.id, object_key=key, position=pos, moderation=moderation))
                added += 1
            if room.status == "published":
                has_pending = db.scalar(
                    select(exists().where(SyncOutbox.entity_id == room.id, SyncOutbox.status == "pending"))
                )
                if not has_pending:
                    room_changed(db, room, was_published=True, reason="seed_images")
                    enqueued += 1
        db.add(AuditLog(action=MARK, entity="system", meta={"rooms": len(rooms), "images": added}))
        db.commit()
    print(f"Đã gắn {added} ảnh mẫu cho {len(rooms)} phòng ({enqueued} phòng ghi thêm outbox)")


if __name__ == "__main__":
    main()
