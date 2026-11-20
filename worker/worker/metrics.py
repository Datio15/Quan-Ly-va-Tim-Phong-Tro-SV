"""Số đo của worker gửi Application Insights qua OpenTelemetry (SPEC §17).

| Số đo               | Loại      | Khi nào ghi                                                         |
|---------------------|-----------|---------------------------------------------------------------------|
| sync_sent           | counter   | gửi một dòng outbox sang Function thành công (nhãn op)              |
| sync_failures       | counter   | gửi lỗi, kể cả lần thử lại (nhãn op)                                |
| outbox_pending      | gauge     | số dòng sync_outbox đang chờ, mỗi lượt outbox                       |
| outbox_failed       | gauge     | số dòng đã thử đủ OUTBOX_MAX_ATTEMPTS lần (status 'failed')          |
| backup_success      | counter   | backup.sh chạy xong (nhãn uploaded = true/false)                    |
| backup_duration_ms  | histogram | thời gian sao lưu                                                   |
| restore_test_ms     | histogram | thời gian khôi phục thử                                             |
| worker_heartbeat    | counter   | mỗi phút một lần                                                    |

`outbox_failed` thêm so với SPEC: worker thử lại theo bậc thang tới 30 phút, nên `sync_failures` có thể im
lặng hơn 15 phút dù đồng bộ vẫn hỏng; cảnh báo "đồng bộ lỗi" dùng cả hai để không tự tắt giữa chừng.

Trong Application Insights, mỗi số đo thành các dòng của bảng `customMetrics` (cột name, value, valueSum,
valueCount), mỗi lần xuất (60 giây) một dòng. Truy vấn cảnh báo ở infra/azure/alerts.sh.

Chưa cấu hình APPLICATIONINSIGHTS_CONNECTION_STRING thì mọi lệnh ghi số đo không làm gì (API OpenTelemetry
mặc định là no-op). METRICS_CONSOLE=1: in số đo ra log 15 giây một lần, để thử trên máy cá nhân không cần Azure.
Không đưa dữ liệu cá nhân hay id vào số đo: chỉ có nhãn kỹ thuật (op, uploaded).
"""
import logging
import os

from opentelemetry import metrics

log = logging.getLogger("worker.metrics")

# Lấy meter và tạo instrument ngay khi import: OpenTelemetry trả "proxy" và tự nối vào MeterProvider thật
# khi setup() đặt provider, nên các module khác import và gọi count()/gauge() lúc nào cũng được.
_meter = metrics.get_meter("phongtro.worker")
_counters = {
    "sync_sent": _meter.create_counter("sync_sent", description="Số lần gửi sang Azure thành công"),
    "sync_failures": _meter.create_counter("sync_failures", description="Số lần gửi sang Azure lỗi (kể cả thử lại)"),
    "backup_success": _meter.create_counter("backup_success", description="Số lần sao lưu thành công"),
    "worker_heartbeat": _meter.create_counter("worker_heartbeat", description="Mỗi phút một lần khi worker còn chạy"),
}
_gauges = {
    "outbox_pending": _meter.create_gauge("outbox_pending", description="Số dòng sync_outbox đang chờ"),
    "outbox_failed": _meter.create_gauge("outbox_failed", description="Số dòng sync_outbox đã bỏ cuộc"),
}
_histograms = {
    "backup_duration_ms": _meter.create_histogram("backup_duration_ms", unit="ms", description="Thời gian sao lưu"),
    "restore_test_ms": _meter.create_histogram("restore_test_ms", unit="ms", description="Thời gian khôi phục thử"),
}


def _is_set(value: str) -> bool:
    return bool(value) and value != "CHANGE_ME" and "SUFFIX" not in value


def setup() -> str:
    """Gọi một lần lúc khởi động. Trả nơi xuất số đo: 'appinsights', 'console' hoặc 'none'."""
    conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip().strip('"')
    if _is_set(conn):
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            configure_azure_monitor(connection_string=conn)
            log.info("Số đo và nhật ký gửi Application Insights")
            return "appinsights"
        except Exception as exc:  # noqa: BLE001
            log.warning("Không bật được Application Insights: %s", type(exc).__name__)
    if os.getenv("METRICS_CONSOLE") == "1":
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader

        reader = PeriodicExportingMetricReader(ConsoleMetricExporter(), export_interval_millis=15000)
        metrics.set_meter_provider(MeterProvider(metric_readers=[reader]))
        log.info("Số đo in ra console 15 giây một lần (METRICS_CONSOLE=1)")
        return "console"
    return "none"


def count(name: str, value: int = 1, **attrs: str) -> None:
    try:
        _counters[name].add(value, attrs)
    except Exception:  # noqa: BLE001 - số đo hỏng không được làm hỏng việc chính
        log.debug("không ghi được số đo %s", name, exc_info=True)


def gauge(name: str, value: float, **attrs: str) -> None:
    try:
        _gauges[name].set(value, attrs)
    except Exception:  # noqa: BLE001
        log.debug("không ghi được số đo %s", name, exc_info=True)


def observe(name: str, value: float, **attrs: str) -> None:
    try:
        _histograms[name].record(value, attrs)
    except Exception:  # noqa: BLE001
        log.debug("không ghi được số đo %s", name, exc_info=True)
