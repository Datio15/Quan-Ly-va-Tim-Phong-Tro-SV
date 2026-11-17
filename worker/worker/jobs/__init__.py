"""Các việc nhắc chạy theo tin trong hàng đợi ops-ticks (SPEC §6, §12.4).

Mỗi file trùng tên với `type` của tin (và cột `job_runs.job`), có hàm `run() -> int`
trả số tin Telegram đã gửi. queue.py gọi: `jobs.run_type(msg['type'])`.
`daily_backup` không thuộc thư mục này.
"""
import importlib
import json
import logging
from datetime import timedelta, timezone
from functools import wraps

from sqlalchemy import text

from worker.db import engine

log = logging.getLogger('worker.jobs')

TYPES = ('viewing_reminder', 'invoice_due_check', 'contract_expiring')
VN = timezone(timedelta(hours=7))  # Asia/Ho_Chi_Minh, không có giờ mùa hè
TODAY_VN = "(now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"


def recorded(job: str):
    """Ghi một dòng job_runs cho mỗi lần run(): running -> success/failed."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            with engine.begin() as conn:
                run_id = conn.execute(text(
                    "INSERT INTO job_runs (job, status) VALUES (:j, 'running') RETURNING id"
                ), {'j': job}).scalar()
            status, details = 'failed', {}
            try:
                sent = fn(*args, **kwargs)
                status, details = 'success', {'sent': sent}
                return sent
            except Exception as e:
                details = {'error': type(e).__name__}
                raise
            finally:
                with engine.begin() as conn:
                    conn.execute(text('''
                        UPDATE job_runs SET status = :s, finished_at = now(), details = CAST(:d AS jsonb)
                        WHERE id = :i
                    '''), {'s': status, 'd': json.dumps(details), 'i': run_id})
        return wrapper
    return deco


def run_type(kind: str) -> int:
    """Chạy việc theo `type` của tin. Loại lạ thì bỏ qua, trả 0."""
    if kind not in TYPES:
        log.warning('bo qua loai viec khong thuoc jobs/: %s', kind)
        return 0
    return importlib.import_module('worker.jobs.' + kind).run()
