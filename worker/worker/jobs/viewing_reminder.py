"""Nhắc lịch xem phòng (SPEC §9.3): lịch confirmed trong 24 giờ tới, chưa có reminded_at.

Gửi cho cả sinh viên và chủ trọ. reminded_at chỉ được đặt khi không còn người nhận
nào gửi lỗi, để lần sau thử lại; bảng notifications chặn gửi trùng cho người đã nhận.
"""
import logging

from sqlalchemy import text

from worker import telegram
from worker.db import engine
from worker.jobs import VN, recorded

log = logging.getLogger('worker.jobs.viewing_reminder')
KIND = 'viewing_reminder'

DUE = text('''
SELECT b.id, b.slot_start, b.student_id, r.title, h.landlord_id
FROM bookings b
JOIN rooms r  ON r.id = b.room_id
JOIN houses h ON h.id = r.house_id
WHERE b.status = 'confirmed'
  AND b.reminded_at IS NULL
  AND b.slot_start > now()
  AND b.slot_start <= now() + interval '24 hours'
ORDER BY b.slot_start
''')


@recorded(KIND)
def run() -> int:
    with engine.connect() as conn:
        rows = conn.execute(DUE).mappings().all()
    sent = 0
    for b in rows:
        when = b['slot_start'].astimezone(VN).strftime('%H:%M ngày %d/%m')
        body = 'Nhắc lịch xem phòng: %s, %s.' % (b['title'], when)
        results = [telegram.deliver(uid, KIND, b['id'], body)
                   for uid in (b['student_id'], b['landlord_id'])]
        sent += results.count(telegram.SENT)
        if telegram.FAILED not in results:
            with engine.begin() as conn:
                conn.execute(text('UPDATE bookings SET reminded_at = now() WHERE id = :i'), {'i': b['id']})
    log.info('viewing_reminder: %d lich, %d tin da gui', len(rows), sent)
    return sent
