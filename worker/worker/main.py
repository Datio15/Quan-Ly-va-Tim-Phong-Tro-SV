import logging
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

def process_telegram() -> None:
    logger.debug("[Telegram] Đang kiểm tra hàng đợi gửi thông báo Telegram...")
    # TODO: Gửi thông báo qua Telegram Bot API bằng httpx

def process_job_runs() -> None:
    logger.debug("[JobRuns] Đang kiểm tra các tác vụ nền trong bảng job_runs...")
    # TODO: Đọc và thực thi các job đang chờ trong bảng job_runs

def emit_heartbeat() -> None:
    logger.info("[Heartbeat] Worker hoạt động bình thường.")
    # TODO: Cập nhật trạng thái heartbeat của worker

def main() -> None:
    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    intervals = {
        "outbox": 5.0,
        "queue": 30.0,
        "telegram": 30.0,
        "job_runs": 5.0,
        "heartbeat": 60.0,
    }
    last_run = {name: 0.0 for name in intervals}

    tasks = {
        "outbox": process_sync_outbox,
        "queue": poll_ops_ticks_queue,
        "telegram": process_telegram,
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
