"""Hóa đơn quá hạn (SPEC §9.8): chuyển unpaid quá hạn sang overdue, gom theo chủ trọ thành một tin.

kind trong notifications là 'invoice_overdue', ref_id là id hóa đơn: mỗi hóa đơn chỉ nhắc một lần.
"""
import logging

from sqlalchemy import text

from worker import telegram
from worker.db import engine
from worker.jobs import TODAY_VN, recorded

log = logging.getLogger('worker.jobs.invoice_due_check')
KIND = 'invoice_overdue'

MARK_OVERDUE = text(f'''
UPDATE invoices SET status = 'overdue'
WHERE status = 'unpaid' AND due_date < {TODAY_VN}
''')

# Hóa đơn overdue chưa nhắc chủ trọ qua Telegram.
PENDING = text('''
SELECT i.id, i.code, h.landlord_id
FROM invoices i
JOIN rooms r  ON r.id = i.room_id
JOIN houses h ON h.id = r.house_id
WHERE i.status = 'overdue'
  AND NOT EXISTS (
    SELECT 1 FROM notifications n
    WHERE n.user_id = h.landlord_id AND n.channel = 'telegram'
      AND n.kind = 'invoice_overdue' AND n.ref_id = i.id)
ORDER BY h.landlord_id, i.code
''')


@recorded('invoice_due_check')
def run() -> int:
    with engine.begin() as conn:
        marked = conn.execute(MARK_OVERDUE).rowcount
        rows = conn.execute(PENDING).mappings().all()
    by_landlord = {}
    for r in rows:
        by_landlord.setdefault(r['landlord_id'], []).append(r)
    sent = 0
    for landlord_id, items in by_landlord.items():
        body = 'Có %d hóa đơn quá hạn: %s.' % (len(items), ', '.join(i['code'] for i in items))
        if telegram.notify(landlord_id, KIND, [i['id'] for i in items], body):
            sent += 1
    log.info('invoice_due_check: %d hoa don chuyen overdue, %d tin da gui', marked, sent)
    return sent
