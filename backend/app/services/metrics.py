"""Số đo gửi Application Insights (SPEC 17). Không đưa dữ liệu cá nhân vào số đo."""
import logging
import threading
import time
from collections import deque

from ..config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

_fallback_times: deque[float] = deque()
_lock = threading.Lock()
_counter = None


def setup_telemetry(app) -> None:
    global _counter
    if settings.appinsights_enabled:
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            configure_azure_monitor(connection_string=settings.applicationinsights_connection_string)
            log.info("Đã bật Application Insights")
        except Exception as exc:
            log.warning("Không bật được Application Insights: %s", type(exc).__name__)
    try:
        from opentelemetry import metrics

        _counter = metrics.get_meter("phongtro.api").create_counter(
            "search_fallback_count", description="Số lần tìm bằng DB vì Azure AI Search lỗi"
        )
    except Exception:
        _counter = None


def record_search_fallback(reason: str) -> None:
    now = time.time()
    with _lock:
        _fallback_times.append(now)
        while _fallback_times and now - _fallback_times[0] > 3600:
            _fallback_times.popleft()
    if _counter is not None:
        _counter.add(1, {"reason": reason})


def fallback_last_hour() -> int:
    now = time.time()
    with _lock:
        while _fallback_times and now - _fallback_times[0] > 3600:
            _fallback_times.popleft()
        return len(_fallback_times)
