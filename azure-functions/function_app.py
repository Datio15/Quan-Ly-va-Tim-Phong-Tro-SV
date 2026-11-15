import json
import logging
import os
import uuid
from datetime import datetime, timezone

import azure.functions as func
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.search.documents import SearchClient
from azure.storage.queue import QueueClient

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# 24 trường của chỉ mục rooms-public = danh sách trường được phép (SPEC mục 4)
ALLOWED = {
    'id', 'title', 'description', 'price_month', 'est_monthly_cost', 'deposit_amount',
    'area_m2', 'max_people', 'floor', 'street', 'ward', 'area', 'city', 'location',
    'amenities', 'curfew', 'curfew_time', 'available_from', 'landlord_verified',
    'rating_avg', 'rating_count', 'image_urls', 'version', 'updated_at',
}
TICK_TYPES = {'viewing_reminder', 'invoice_due_check', 'contract_expiring', 'daily_backup'}


def _reply(body, status=200):
    return func.HttpResponse(json.dumps(body, ensure_ascii=False),
                             status_code=status, mimetype='application/json')


def _search():
    return SearchClient(
        endpoint=os.environ['AZURE_SEARCH_ENDPOINT'],
        index_name=os.environ.get('AZURE_SEARCH_INDEX', 'rooms-public'),
        credential=AzureKeyCredential(os.environ['AZURE_SEARCH_ADMIN_KEY']),
    )


def _queue():
    return QueueClient.from_connection_string(
        os.environ['AzureWebJobsStorage'], os.environ.get('OPS_QUEUE_NAME', 'ops-ticks'))


def _enqueue(types):
    queue = _queue()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    ids = []
    for t in types:
        msg = {'id': str(uuid.uuid4()), 'type': t, 'at': now}
        queue.send_message(json.dumps(msg))  # JSON thuần, không mã hóa base64
        ids.append(msg['id'])
    return ids


@app.function_name(name='ingest-room')
@app.route(route='ingest-room', methods=['POST'])
def ingest_room(req: func.HttpRequest) -> func.HttpResponse:
    try:
        data = req.get_json()
    except ValueError:
        return _reply({'error': 'INVALID_JSON'}, 400)
    op = data.get('op')
    room = data.get('room') or {}
    if op not in ('upsert', 'delete') or 'id' not in room or 'version' not in room:
        return _reply({'error': 'INVALID_BODY'}, 400)
    extra = sorted(set(room) - ALLOWED)
    if extra:
        return _reply({'error': 'FIELD_NOT_ALLOWED', 'fields': extra}, 400)
    try:
        client = _search()
        try:
            current = client.get_document(key=room['id'])
        except ResourceNotFoundError:
            current = None
        if current and (current.get('version') or 0) >= room['version']:
            return _reply({'status': 'skipped'})
        if op == 'upsert':
            results = client.merge_or_upload_documents(documents=[room])
        else:
            results = client.delete_documents(documents=[{'id': room['id']}])
        if not all(r.succeeded for r in results):
            return _reply({'error': 'SEARCH_FAILED'}, 502)
        return _reply({'status': 'ok'})
    except HttpResponseError as e:
        logging.exception('AI Search loi')
        return _reply({'error': 'SEARCH_ERROR', 'detail': str(e)[:200]}, 502)


# Timer chỉ nhận một lịch cho mỗi hàm, nên SPEC "daily-ticks" tách thành hai hàm.
@app.function_name(name='daily-ticks-morning')
@app.timer_trigger(schedule='0 0 1 * * *', arg_name='timer', run_on_startup=False)
def daily_ticks_morning(timer: func.TimerRequest) -> None:
    ids = _enqueue(['viewing_reminder', 'invoice_due_check', 'contract_expiring'])
    logging.info('daily-ticks 08:00 VN: da dua %d tin vao hang doi', len(ids))


@app.function_name(name='daily-ticks-backup')
@app.timer_trigger(schedule='0 0 19 * * *', arg_name='timer', run_on_startup=False)
def daily_ticks_backup(timer: func.TimerRequest) -> None:
    _enqueue(['daily_backup'])
    logging.info('daily-ticks 02:00 VN: da dua tin daily_backup vao hang doi')


@app.function_name(name='tick-now')
@app.route(route='tick-now', methods=['POST'])
def tick_now(req: func.HttpRequest) -> func.HttpResponse:
    t = req.params.get('type', 'viewing_reminder')
    if t not in TICK_TYPES:
        return _reply({'error': 'INVALID_TYPE', 'allowed': sorted(TICK_TYPES)}, 400)
    ids = _enqueue([t])
    return _reply({'status': 'queued', 'type': t, 'id': ids[0]})