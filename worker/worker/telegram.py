"""Telegram cho worker (SPEC §3F, §12.4): liên kết tài khoản và gửi tin nhắc.

Không ghi token, mã liên kết hay chat id vào log.
Chỉ một worker được gọi getUpdates tại một thời điểm (nếu không Telegram trả 409).
"""
import logging
import os
import re

import httpx
from sqlalchemy import text

from worker.db import engine

log = logging.getLogger('worker.telegram')
# httpx ghi URL ở mức INFO, mà URL Bot API chứa token: chỉ cho phép WARNING trở lên.
for _name in ('httpx', 'httpcore'):
    logging.getLogger(_name).setLevel(logging.WARNING)

API = 'https://api.telegram.org/bot%s/%s'
_CODE = re.compile(r'[A-Za-z0-9_-]{8,64}')
_offset = 0  # update_id + 1 của tin cuối đã xử lý

# Kết quả của deliver()
SENT, DUPLICATE, UNLINKED, FAILED = 'sent', 'duplicate', 'unlinked', 'failed'

LINK = text('''
UPDATE users
SET telegram_chat_id = :chat, telegram_link_code = NULL, telegram_link_expires = NULL
WHERE telegram_link_code = :code AND telegram_link_expires > now()
RETURNING id
''')


def _token() -> str:
    t = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    return '' if t in ('', 'CHANGE_ME') else t


def _call(method: str, _http_timeout: float = 20, **params) -> dict:
    # Tên _http_timeout để không trùng tham số `timeout` (long-poll) của getUpdates.
    """Gọi Bot API. Lỗi được đổi thành RuntimeError không chứa URL (URL có token)."""
    try:
        r = httpx.post(API % (_token(), method), json=params, timeout=_http_timeout)
    except httpx.HTTPError as e:
        raise RuntimeError('telegram %s: %s' % (method, type(e).__name__)) from None
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code != 200 or not data.get('ok'):
        raise RuntimeError('telegram %s: HTTP %s %s' % (method, r.status_code, data.get('description', '')))
    return data


# ---------- Gửi tin ----------

def send_message(chat_id, body: str) -> bool:
    if not _token():
        log.warning('chua cau hinh TELEGRAM_BOT_TOKEN, khong gui tin')
        return False
    try:
        _call('sendMessage', chat_id=chat_id, text=body)
        return True
    except RuntimeError as e:
        log.warning('gui tin that bai: %s', e)
        return False


def deliver(user_id, kind: str, ref_id, body: str) -> str:
    """Gửi một tin cho người dùng, chống gửi trùng qua bảng notifications.

    ref_id là một id hoặc danh sách id (ví dụ nhiều hóa đơn gộp một tin).
    Chỉ gửi nếu chèn được ít nhất một dòng notifications mới; gửi lỗi thì xóa
    các dòng vừa chèn để lần sau thử lại. Trả SENT / DUPLICATE / UNLINKED / FAILED.
    """
    refs = [str(r) for r in (ref_id if isinstance(ref_id, (list, tuple, set)) else [ref_id])]
    with engine.begin() as conn:
        chat = conn.execute(text('SELECT telegram_chat_id FROM users WHERE id = :u'),
                            {'u': user_id}).scalar()
        if not chat:
            log.info('bo qua %s: nguoi nhan chua lien ket Telegram', kind)
            return UNLINKED
        new_ids = []
        for ref in refs:
            nid = conn.execute(text('''
                INSERT INTO notifications (user_id, channel, kind, ref_id)
                VALUES (:u, 'telegram', :k, :r)
                ON CONFLICT DO NOTHING
                RETURNING id
            '''), {'u': user_id, 'k': kind, 'r': ref}).scalar()
            if nid:
                new_ids.append(nid)
    if not new_ids:
        return DUPLICATE
    if send_message(chat, body):
        return SENT
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM notifications WHERE id = ANY(:ids)'), {'ids': new_ids})
    return FAILED


def notify(user_id, kind: str, ref_id, body: str) -> bool:
    """True nếu vừa gửi được tin mới."""
    return deliver(user_id, kind, ref_id, body) == SENT


# ---------- Liên kết tài khoản (SPEC §3F) ----------

def _handle_start(chat_id: str, code: str) -> int:
    if not _CODE.fullmatch(code):
        send_message(chat_id, 'Hãy mở liên kết trong trang Hồ sơ của phòng trọ để liên kết tài khoản.')
        return 0
    with engine.begin() as conn:
        linked = conn.execute(LINK, {'chat': chat_id, 'code': code}).first()
    if linked:
        log.info('lien ket Telegram thanh cong cho mot tai khoan')
        send_message(chat_id, 'Đã liên kết tài khoản phòng trọ.')
        return 1
    log.info('ma lien ket Telegram khong hop le hoac het han')
    send_message(chat_id, 'Mã liên kết không hợp lệ hoặc đã hết hạn. Hãy tạo mã mới trong trang Hồ sơ.')
    return 0


def poll_updates() -> int:
    """Đọc getUpdates, xử lý /start <mã>. Trả số tài khoản vừa liên kết."""
    global _offset
    if not _token():
        return 0
    data = _call('getUpdates', offset=_offset, timeout=0, allowed_updates=['message'])
    linked = 0
    for upd in data.get('result', []):
        _offset = upd['update_id'] + 1
        msg = upd.get('message') or {}
        chat = msg.get('chat') or {}
        body = (msg.get('text') or '').strip()
        if chat.get('type') != 'private' or not body.startswith('/start'):
            continue
        parts = body.split(maxsplit=1)
        if parts[0] not in ('/start', '/start@' + os.environ.get('TELEGRAM_BOT_NAME', '')):
            continue
        try:
            linked += _handle_start(str(chat['id']), parts[1].strip() if len(parts) > 1 else '')
        except Exception as e:
            # Không để một tin lỗi chặn cả lô; offset đã tăng nên không đọc lại tin này.
            # Chỉ ghi tên lỗi: thông báo lỗi SQL có thể chứa mã liên kết và chat id.
            log.error('loi khi xu ly /start: %s', type(e).__name__)
    return linked
