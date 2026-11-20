"""Kiểm thử đơn vị số đo worker (SPEC §17), không cần Azure hay CSDL.

Chạy (image worker không chứa thư mục tests, nên gắn vào khi chạy):
    docker compose run --rm --no-deps -v ./worker/tests:/app/tests worker python -m unittest discover -s tests -v
"""
import unittest

from opentelemetry import metrics as otel_metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

READER = InMemoryMetricReader()
otel_metrics.set_meter_provider(MeterProvider(metric_readers=[READER]))

from worker import metrics  # noqa: E402  (phải import sau khi đặt MeterProvider của test)

# Tên số đo mà infra/azure/alerts.sh truy vấn: đổi tên ở đây thì phải sửa cả cảnh báo.
ALERT_METRICS = {"sync_failures", "outbox_failed", "worker_heartbeat", "backup_success"}


def collect() -> dict:
    """{tên: [(nhãn, giá trị), ...]} của lần thu gần nhất."""
    out: dict = {}
    data = READER.get_metrics_data()
    for rm in data.resource_metrics if data else []:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                for p in m.data.data_points:
                    value = getattr(p, "value", None)
                    if value is None:  # histogram
                        value = (p.count, p.sum)
                    out.setdefault(m.name, []).append((dict(p.attributes), value))
    return out


class MetricsTest(unittest.TestCase):
    def test_counters_gauges_histograms(self):
        metrics.count("sync_failures", op="upsert")
        metrics.count("sync_failures", op="upsert")
        metrics.count("sync_sent", op="delete")
        metrics.count("worker_heartbeat")
        metrics.count("backup_success", uploaded="true")
        metrics.gauge("outbox_pending", 7)
        metrics.gauge("outbox_failed", 2)
        metrics.observe("backup_duration_ms", 2100)
        metrics.observe("restore_test_ms", 12000)
        got = collect()

        self.assertIn(({"op": "upsert"}, 2), got["sync_failures"])
        self.assertIn(({"op": "delete"}, 1), got["sync_sent"])
        self.assertIn(({"uploaded": "true"}, 1), got["backup_success"])
        self.assertEqual(got["outbox_pending"][0][1], 7)
        self.assertEqual(got["outbox_failed"][0][1], 2)
        self.assertEqual(got["backup_duration_ms"][0][1], (1, 2100))
        self.assertEqual(got["restore_test_ms"][0][1], (1, 12000))
        self.assertTrue(ALERT_METRICS <= set(got), ALERT_METRICS - set(got))

    def test_bad_name_does_not_raise(self):
        # Số đo hỏng không được làm hỏng vòng worker.
        metrics.count("khong_co_so_do_nay")
        metrics.gauge("khong_co_so_do_nay", 1)
        metrics.observe("khong_co_so_do_nay", 1)

    def test_setup_without_config_is_noop(self):
        import os

        old = {k: os.environ.pop(k, None) for k in ("APPLICATIONINSIGHTS_CONNECTION_STRING", "METRICS_CONSOLE")}
        try:
            self.assertEqual(metrics.setup(), "none")
        finally:
            for k, v in old.items():
                if v is not None:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
