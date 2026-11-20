import logging
import os
import signal
import time
from worker.job_runs import process_job_runs
from worker.outbox import process_sync_outbox
from worker.queue import poll_ops_ticks_queue
from worker import telegram

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker.main")
# Thư viện Azure ghi từng request/response HTTP (kèm header) ở mức INFO: chỉ giữ cảnh báo trở lên.
for _name in ("azure", "azure.core.pipeline.policies.http_logging_policy", "azure.monitor.opentelemetry.exporter"):
    logging.getLogger(_name).setLevel(logging.WARNING)

RUNNING = True


def _handle_shutdown(signum, frame):
    global RUNNING
    logger.info("Nhận tín hiệu dừng (%s), đang thoát vòng lặp...", signum)
    RUNNING = False


_heartbeat = None


def _setup_telemetry() -> None:
    """SPEC §17: số đo worker_heartbeat lên Application Insights (bỏ qua nếu chưa cấu hình)."""
    global _heartbeat
    conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip().strip('"')
    if not conn or conn == "CHANGE_ME":
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        from opentelemetry import metrics

        configure_azure_monitor(connection_string=conn)
        _heartbeat = metrics.get_meter("phongtro.worker").create_counter(
            "worker_heartbeat", description="Mỗi phút một lần khi worker còn chạy")
        logger.info("Đã bật Application Insights cho worker")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Không bật được Application Insights: %s", type(exc).__name__)


def emit_heartbeat() -> None:
    if _heartbeat is not None:
        _heartbeat.add(1)
    logger.info("[Heartbeat] Worker hoạt động bình thường.")


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
        "telegram": telegram.poll_updates,
        "job_runs": process_job_runs,
        "heartbeat": emit_heartbeat,
    }

    _setup_telemetry()
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
