"""Kết nối Azure Storage của worker: ưu tiên SAS giới hạn quyền, dự phòng bằng chuỗi kết nối.

Worker chỉ cần hai quyền (xem LUU-Y-SAS.md):
- Blob `public-images`: SAS `cwdl` (tạo, ghi, xóa, liệt kê; không đọc) trong AZURE_PUBLIC_IMAGES_SAS,
  URL container lấy từ AZURE_PUBLIC_IMAGES_URL, mặc định là AZURE_BLOB_PUBLIC_BASE_URL.
- Queue `ops-ticks`: SAS `p` (nhận và xóa tin) trong AZURE_QUEUE_SAS, URL hàng đợi trong AZURE_QUEUE_URL.

Thiếu SAS thì dùng AZURE_STORAGE_CONNECTION_STRING như trước. Chuỗi đó có toàn quyền trên tài khoản
(kể cả xóa container `backups`), nên chỉ giữ để chuyển tiếp; khi SAS chạy ổn thì xóa khỏi .env của VM.

URL có SAS là bí mật: không ghi log, không lưu vào CSDL hay chỉ mục. Dùng public_url() để bỏ phần query.
"""
import logging
import os
from urllib.parse import urlsplit, urlunsplit

from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.storage.queue import QueueClient

logger = logging.getLogger(__name__)

PUBLIC_CONTAINER = "public-images"
SAS, CONN = "sas", "connection_string"

_logged: set[str] = set()


def _env(name: str) -> str:
    """Đọc biến môi trường, bỏ khoảng trắng và dấu nháy bao ngoài (setup.sh ghi SAS trong ngoặc kép)."""
    return os.getenv(name, "").strip().strip('"').strip("'").strip()


def is_set(value: str) -> bool:
    """Cùng quy tắc với api (app/config.py): CHANGE_ME hoặc chứa SUFFIX là giá trị giữ chỗ."""
    return bool(value) and value != "CHANGE_ME" and "SUFFIX" not in value


def _with_sas(url: str, sas: str) -> str:
    return f"{url.split('?', 1)[0].rstrip('/')}?{sas.lstrip('?')}"


def _log_once(key: str, level: int, msg: str, *args) -> None:
    if key not in _logged:
        _logged.add(key)
        logger.log(level, msg, *args)


def _mode(what: str, sas_var: str, url: str, url_var: str) -> str | None:
    sas = _env(sas_var)
    if is_set(sas):
        if is_set(url):
            _log_once(what + SAS, logging.INFO, "[Storage] %s: dùng SAS giới hạn quyền", what)
            return SAS
        _log_once(what + "nourl", logging.WARNING, "[Storage] %s: có %s nhưng thiếu %s, không dùng được SAS",
                  what, sas_var, url_var)
    if is_set(_env("AZURE_STORAGE_CONNECTION_STRING")):
        _log_once(what + CONN, logging.WARNING,
                  "[Storage] %s: đang dùng AZURE_STORAGE_CONNECTION_STRING (toàn quyền tài khoản); nên chuyển sang %s",
                  what, sas_var)
        return CONN
    return None


def _images_url() -> str:
    return _env("AZURE_PUBLIC_IMAGES_URL") or _env("AZURE_BLOB_PUBLIC_BASE_URL")


def images_mode() -> str | None:
    """'sas', 'connection_string' hoặc None (chưa cấu hình: bỏ qua bước đẩy ảnh)."""
    return _mode(PUBLIC_CONTAINER, "AZURE_PUBLIC_IMAGES_SAS", _images_url(), "AZURE_PUBLIC_IMAGES_URL")


def images_container() -> ContainerClient | None:
    mode = images_mode()
    if mode == SAS:
        return ContainerClient.from_container_url(_with_sas(_images_url(), _env("AZURE_PUBLIC_IMAGES_SAS")))
    if mode == CONN:
        service = BlobServiceClient.from_connection_string(_env("AZURE_STORAGE_CONNECTION_STRING"))
        return service.get_container_client(PUBLIC_CONTAINER)
    return None


def queue_mode() -> str | None:
    return _mode("queue", "AZURE_QUEUE_SAS", _env("AZURE_QUEUE_URL"), "AZURE_QUEUE_URL")


def queue_client(queue_name: str) -> QueueClient | None:
    """Tin là JSON thuần nên không đặt message_encode_policy (SPEC §11.4)."""
    mode = queue_mode()
    if mode == SAS:
        return QueueClient.from_queue_url(_with_sas(_env("AZURE_QUEUE_URL"), _env("AZURE_QUEUE_SAS")))
    if mode == CONN:
        return QueueClient.from_connection_string(_env("AZURE_STORAGE_CONNECTION_STRING"), queue_name)
    return None


def public_url(url: str) -> str:
    """Bỏ query và fragment: blob_client.url của client tạo từ SAS có kèm chữ ký SAS."""
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path, "", ""))
