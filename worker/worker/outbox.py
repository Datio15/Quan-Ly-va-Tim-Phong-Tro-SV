import logging

logger = logging.getLogger(__name__)

def process_sync_outbox() -> None:
    """
    Đọc các bản ghi chưa xử lý từ bảng sync_outbox (chu kỳ 5s),
    đồng bộ sang dịch vụ đích và cập nhật trạng thái.
    """
    logger.debug("[Outbox] Đang kiểm tra bảng sync_outbox...")
    # TODO: Kết nối DB qua SQLAlchemy, truy vấn batch pending từ sync_outbox
    # TODO: Thực thi đồng bộ và cập nhật status / retry_count
