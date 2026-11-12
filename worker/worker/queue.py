import logging

logger = logging.getLogger(__name__)


def poll_ops_ticks_queue() -> None:
    """
    Đọc message từ Azure Storage Queue 'ops-ticks' (chu kỳ QUEUE_POLL_SECONDS),
    kiểm tra idempotency qua bảng processed_messages trước khi thực thi.
    """
    logger.debug("[Queue] Đang đọc hàng đợi ops-ticks...")
    # TODO (Mục 11.4, 12.3): Dùng QueueClient nhận messages (JSON thuần, không base64) từ 'ops-ticks'
    # TODO: Kiểm tra message_id trong bảng processed_messages để tránh xử lý trùng
    # TODO: Thực thi job theo type (viewing_reminder, invoice_due_check, contract_expiring, daily_backup)
    # TODO: Chèn processed_messages, ghi job_runs và xóa message khỏi queue
