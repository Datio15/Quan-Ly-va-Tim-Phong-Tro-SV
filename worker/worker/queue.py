"""Hàng đợi ops-ticks (SPEC §11.4, §12.1, §12.3).

Tin là JSON thuần: {"id": "<uuid>", "type": "viewing_reminder", "at": "..."}.
- viewing_reminder, invoice_due_check, contract_expiring: gọi jobs.run_type(type);
  job_runs do chính jobs/ ghi, ở đây không ghi thêm.
- daily_backup: tạo job_runs(job='backup', status='queued') để vòng lệnh quản trị chạy backup.sh.
Thành công thì chèn processed_messages và xóa tin; lỗi thì để tin hiện lại sau 5 phút.
"""
import json
import logging
import os

from azure.core.exceptions import AzureError
from sqlalchemy import text

from worker import jobs, storage
from worker.db import engine

logger = logging.getLogger(__name__)

VISIBILITY_TIMEOUT = 300  # giây; lỗi thì tin hiện lại sau 5 phút
MAX_DEQUEUE = 5           # quá số lần này thì bỏ tin, tránh lặp mãi một tin hỏng

_client = None
_warned = False

QUEUE_BACKUP = text('''
INSERT INTO job_runs (job, status, details)
SELECT 'backup', 'queued', CAST(:d AS jsonb)
WHERE NOT EXISTS (SELECT 1 FROM job_runs WHERE job = 'backup' AND status IN ('queued', 'running'))
''')


def _get_client():
    global _client, _warned
    if _client is not None:
        return _client
    _client = storage.queue_client(os.getenv('AZURE_QUEUE_NAME', 'ops-ticks'))
    if _client is None and not _warned:
        logger.warning('[Queue] chua cau hinh AZURE_QUEUE_SAS/AZURE_QUEUE_URL, tam dung doc hang doi')
        _warned = True
    return _client


def _already_processed(message_id: str) -> bool:
    with engine.connect() as conn:
        return conn.execute(text('SELECT 1 FROM processed_messages WHERE message_id = :m'),
                            {'m': message_id}).first() is not None


def _mark_processed(message_id: str) -> None:
    with engine.begin() as conn:
        conn.execute(text('INSERT INTO processed_messages (message_id) VALUES (:m) ON CONFLICT DO NOTHING'),
                     {'m': message_id})


def _run(kind: str) -> None:
    if kind == 'daily_backup':
        with engine.begin() as conn:
            n = conn.execute(QUEUE_BACKUP, {'d': json.dumps({'requested_by': 'timer'})}).rowcount
        logger.info('[Queue] daily_backup: %s', 'da xep backup' if n else 'da co backup dang cho, bo qua')
    elif kind in jobs.TYPES:
        sent = jobs.run_type(kind)
        logger.info('[Queue] %s: %d tin da gui', kind, sent)
    else:
        logger.warning('[Queue] bo qua tin loai la: %s', kind)


def handle_message(client, msg) -> None:
    """Xử lý một tin. Tách riêng để kiểm thử được mà không cần Azure."""
    try:
        body = json.loads(msg.content)
        kind = body['type']
        message_id = str(body.get('id') or msg.id)
    except (ValueError, TypeError, KeyError):
        logger.warning('[Queue] tin khong dung dinh dang, xoa')
        client.delete_message(msg)
        return

    if _already_processed(message_id):
        client.delete_message(msg)
        return

    if (msg.dequeue_count or 0) > MAX_DEQUEUE:
        logger.error('[Queue] tin %s loai %s loi qua %d lan, bo', message_id, kind, MAX_DEQUEUE)
        client.delete_message(msg)
        return

    try:
        _run(kind)
    except Exception as e:
        # Không xóa: tin hiện lại sau VISIBILITY_TIMEOUT để thử lại.
        logger.error('[Queue] chay %s loi: %s', kind, type(e).__name__)
        return

    _mark_processed(message_id)
    client.delete_message(msg)


def poll_ops_ticks_queue() -> None:
    client = _get_client()
    if client is None:
        return
    try:
        for msg in client.receive_messages(max_messages=16, visibility_timeout=VISIBILITY_TIMEOUT):
            handle_message(client, msg)
    except AzureError as e:
        logger.warning('[Queue] loi Azure Queue: %s', type(e).__name__)
