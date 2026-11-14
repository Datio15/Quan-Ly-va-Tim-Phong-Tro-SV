import logging

logger = logging.getLogger(__name__)


def process_sync_outbox() -> None:
    """
    Đọc các bản ghi chưa xử lý từ bảng sync_outbox (chu kỳ OUTBOX_POLL_SECONDS),
    đồng bộ sang Azure AI Search & Blob, và cập nhật trạng thái.
    """
    logger.debug("[Outbox] Đang kiểm tra bảng sync_outbox...")
    # TODO (Mục 12.2): Truy vấn batch status='pending' AND next_attempt_at <= now() (FOR UPDATE SKIP LOCKED)
    # TODO (Mục 4): Đọc từ v_rooms_public, đẩy ảnh lên Blob public-images, lọc đúng 24 trường cho phép
    # TODO: Gọi Azure Function ingest-room; cập nhật status='sent', sent_at=now()
    #       hoặc tăng attempts, cập nhật last_error, next_attempt_at (backoff) / status='failed'
