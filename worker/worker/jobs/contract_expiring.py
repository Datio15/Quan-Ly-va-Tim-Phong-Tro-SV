"""Hợp đồng sắp hết hạn (SPEC §9.9): khách thuê đang hiệu lực có end_date trong 30 ngày tới.

Nhắc chủ trọ một lần mỗi khách (notifications: kind 'contract_expiring', ref_id = tenants.id).
Tin chỉ có tiêu đề phòng và ngày, không có tên/điện thoại khách.
"""
import logging

from sqlalchemy import text

from worker import telegram
from worker.db import engine
from worker.jobs import TODAY_VN, recorded

log = logging.getLogger('worker.jobs.contract_expiring')
KIND = 'contract_expiring'
DAYS_AHEAD = 30

DUE = text(f'''
SELECT t.id, t.end_date, r.title, h.landlord_id
FROM tenants t
JOIN rooms r  ON r.id = t.room_id
JOIN houses h ON h.id = r.house_id
WHERE t.is_active
  AND t.end_date BETWEEN {TODAY_VN} AND {TODAY_VN} + :days
ORDER BY t.end_date
''')


@recorded(KIND)
def run() -> int:
    with engine.connect() as conn:
        rows = conn.execute(DUE, {'days': DAYS_AHEAD}).mappings().all()
    sent = 0
    for t in rows:
        body = 'Hợp đồng phòng %s hết hạn ngày %s.' % (t['title'], t['end_date'].strftime('%d/%m/%Y'))
        if telegram.notify(t['landlord_id'], KIND, t['id'], body):
            sent += 1
    log.info('contract_expiring: %d hop dong, %d tin da gui', len(rows), sent)
    return sent
