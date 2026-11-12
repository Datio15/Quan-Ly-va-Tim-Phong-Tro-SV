import logging
import os
import signal
import time
from worker.outbox import process_sync_outbox
from worker.queue import poll_ops_ticks_queue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker.main")

RUNNING = True


def _handle_shutdown(signum, frame):
    global RUNNING
    logger.info("Nhận tín hiệu dừng (%s), đang thoát vòng lặp...", signum)
    RUNNING = False


def poll_telegram_updates() -> None:
    logger.debug("[Telegram] Đang gọi getUpdates kiểm tra liên kết tài khoản...")
    # TODO (Mục 3F): Gọi Telegram Bot API getUpdates, khớp mã /start <code_16_ky_tu>
    # với users.telegram_link_code (còn hạn telegram_link_expires) để lưu telegram_chat_id


def process_job_runs() -> None:
    logger.debug("[JobRuns] Đang kiểm tra các tác vụ nền trong bảng job_runs...")
    # TODO (Mục 12.1, 16): Lấy dòng job_runs có status='queued' (backup / restore_test)
    # và gọi backup.sh hoặc restore-test.sh với biến môi trường JOB_RUN_ID=<id>


def emit_heartbeat() -> None:
    logger.info("[Heartbeat] Worker hoạt động bình thường.")
    # TODO (Mục 17): Đẩy custom metric 'worker_heartbeat' lên Application Insights


def main() -> None:
    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    intervals = {
        "outbox": float(os.getenv("OUTBOX_POLL_SECONDS", "5")),
        "queue": float(os.getenv("QUEUE_POLL_SECONDS", "30")),
        "telegram": 30.0,
        "job_runs": 5.0,
        "heartbeat": 60.0,
    }
    last_run = {name: 0.0 for name in intervals}

    tasks = {
        "outbox": process_sync_outbox,
        "queue": poll_ops_ticks_queue,
        "telegram": poll_telegram_updates,
        "job_runs": process_job_runs,
        "heartbeat": emit_heartbeat,
    }

    logger.info("Khởi động Worker service...")
    while RUNNING:
        now = time.monotonic()
        for name, interval in intervals.items():
            if now - last_run[name] >= interval:
                last_run[name] = now
                try:
                    tasks[name]()
                except Exception as exc:
                    logger.exception("Lỗi trong tác vụ [%s]: %s", name, exc)
        time.sleep(1.0)


if __name__ == "__main__":
    main()
