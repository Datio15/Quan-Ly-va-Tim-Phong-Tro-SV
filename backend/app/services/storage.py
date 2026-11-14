"""MinIO (API S3): bucket `public-src` cho ảnh phòng gốc, `private` cho CCCD/hợp đồng GIẢ (SPEC mục 4)."""
import io
import logging
from functools import lru_cache

from minio import Minio
from minio.error import S3Error

from ..config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_FILE_BYTES = 10 * 1024 * 1024


@lru_cache
def client() -> Minio:
    endpoint = settings.minio_endpoint.replace("http://", "").replace("https://", "")
    return Minio(
        endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=settings.minio_secure,
    )


def ensure_buckets() -> None:
    for bucket in (settings.minio_bucket_public_src, settings.minio_bucket_private):
        try:
            if not client().bucket_exists(bucket):
                client().make_bucket(bucket)
                log.info("Đã tạo bucket %s", bucket)
        except Exception as exc:  # MinIO chưa sẵn sàng thì để lần gọi sau thử lại
            log.warning("Không kiểm tra được bucket %s: %s", bucket, type(exc).__name__)


def healthy() -> bool:
    try:
        client().bucket_exists(settings.minio_bucket_public_src)
        return True
    except Exception:
        return False


def put(bucket: str, key: str, data: bytes, content_type: str) -> None:
    client().put_object(bucket, key, io.BytesIO(data), length=len(data), content_type=content_type)


def get(bucket: str, key: str) -> tuple[bytes, str]:
    resp = client().get_object(bucket, key)
    try:
        return resp.read(), resp.headers.get("Content-Type", "application/octet-stream")
    finally:
        resp.close()
        resp.release_conn()


def remove(bucket: str, key: str) -> None:
    try:
        client().remove_object(bucket, key)
    except S3Error as exc:
        log.warning("Không xóa được đối tượng: %s", exc.code)


def sniff_image(data: bytes) -> tuple[str, str] | None:
    """Kiểm tra loại file bằng chữ ký đầu file (không tin Content-Type do trình duyệt gửi)."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg", "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", "png"
    return None


def sniff_document(data: bytes) -> tuple[str, str] | None:
    if data[:5] == b"%PDF-":
        return "application/pdf", "pdf"
    return sniff_image(data)
