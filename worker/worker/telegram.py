import logging

logger = logging.getLogger(__name__)

def send_telegram_alert(message: str) -> None:
    """Hàm khung rỗng - Người phụ trách Telegram sẽ bổ sung phần ruột."""
    logger.debug("[Telegram] Stub alert: %s", message)
