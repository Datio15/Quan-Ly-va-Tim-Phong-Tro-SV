"""Lệnh quản trị (SPEC §12.1, §16): chạy backup.sh / restore-test.sh cho các dòng job_runs 'queued'.

Dòng 'queued' do trang quản trị tạo (POST /admin/backup/run, /admin/backup/restore-test) hoặc do tin
`daily_backup` trong hàng đợi. Worker nhận một dòng (khóa SKIP LOCKED, đổi sang 'running'), chạy script
với JOB_RUN_ID=<id>; script tự ghi kết quả vào đúng dòng đó. Script chết sớm (thiếu biến, lỗi trước khi
cập nhật) thì worker đánh dấu 'failed' để dòng không treo ở 'running'.

Mỗi lần chỉ chạy một việc, trong luồng riêng, để vòng outbox/hàng đợi/Telegram không bị chặn.
Không ghi biến môi trường hay URL có SAS vào log/job_runs.
"""
import glob
import json
import logging
import os
import re
import subprocess
import threading

from sqlalchemy import text

from worker.db import engine

log = logging.getLogger("worker.job_runs")

SCRIPTS_DIR = os.getenv("SCRIPTS_DIR", "/app/scripts")
SCRIPTS = {"backup": "backup.sh", "restore_test": "restore-test.sh"}
TIMEOUT_S = int(os.getenv("JOB_TIMEOUT_SECONDS", "1800"))

CLAIM = text("""
UPDATE job_runs SET status = 'running', started_at = now()
WHERE id = (
  SELECT id FROM job_runs
  WHERE status = 'queued' AND job IN ('backup', 'restore_test')
  ORDER BY id LIMIT 1
  FOR UPDATE SKIP LOCKED)
RETURNING id, job
""")

# Cũng bổ sung lý do khi script đã tự đánh 'failed' mà không ghi 'error' (restore-test.sh làm vậy khi giải mã
# sai khóa), để trang Hệ thống không hiện "failed" trống. Không ghi đè dòng đã thành công hay đã có lý do.
MARK_FAILED = text("""
UPDATE job_runs SET status = 'failed', finished_at = coalesce(finished_at, now()),
  details = details || CAST(:d AS jsonb)
WHERE id = :id AND (status IN ('queued', 'running') OR (status = 'failed' AND NOT details ? 'error'))
""")

_busy = threading.Lock()


def _is_set(value: str | None) -> bool:
    """Cùng quy tắc với api: CHANGE_ME hoặc chứa SUFFIX là giá trị giữ chỗ."""
    return bool(value) and value != "CHANGE_ME" and "SUFFIX" not in value


def _scrub(s: str) -> str:
    """Bỏ chữ ký SAS và chuỗi kết nối có thể lẫn trong thông báo lỗi."""
    s = re.sub(r"(sig|se|sp|sv|sr|spr)=[^&\s\"']+", r"\1=***", s)
    return re.sub(r"(AccountKey|PGPASSWORD|BACKUP_PASSPHRASE)=\S+", r"\1=***", s)


def _script_env(job_id: int) -> tuple[dict, list[str]]:
    """Biến môi trường và tham số cho script. Chưa cấu hình Azure Blob thì chạy DRY_RUN (không tải lên),
    và khôi phục thử dùng bản cục bộ mới nhất thay vì tải từ Azure."""
    env = dict(os.environ, JOB_RUN_ID=str(job_id))
    azure_ok = (_is_set(env.get("AZURE_BACKUP_CONTAINER_URL"))
                and _is_set(env.get("AZURE_BACKUP_SAS_WRITE")) and _is_set(env.get("AZURE_BACKUP_SAS_READ")))
    if not azure_ok:
        env["DRY_RUN"] = "1"
    args: list[str] = []
    if env.get("DRY_RUN") == "1":
        local = sorted(glob.glob(os.path.join(env.get("BACKUP_DIR", "/var/backups/phongtro"), "phongtro-*.tar.gz.enc")))
        if local:
            args = [local[-1]]
    return env, args


def _run(job_id: int, job: str) -> None:
    script = os.path.join(SCRIPTS_DIR, SCRIPTS[job])
    try:
        env, args = _script_env(job_id)
        if job == "backup":
            args = []  # backup.sh không nhận tham số
        log.info("[JobRuns] bắt đầu %s #%s%s", job, job_id, " (DRY_RUN)" if env.get("DRY_RUN") == "1" else "")
        proc = subprocess.run(["bash", script, *args], env=env, capture_output=True, text=True, timeout=TIMEOUT_S)
        if proc.returncode == 0:
            log.info("[JobRuns] xong %s #%s", job, job_id)
            return
        lines = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = _scrub(lines[-1]) if lines else ""
        log.warning("[JobRuns] %s #%s thoát mã %s: %s", job, job_id, proc.returncode, tail[:200])
        # restore-test thoát 2 khi số dòng lệch: script đã tự ghi 'failed' kèm bảng đối chiếu.
        _mark_failed(job_id, {"exit_code": proc.returncode, "error": tail[:300]})
    except subprocess.TimeoutExpired:
        log.error("[JobRuns] %s #%s quá %s giây", job, job_id, TIMEOUT_S)
        _mark_failed(job_id, {"error": f"timeout {TIMEOUT_S}s"})
    except Exception as exc:  # noqa: BLE001
        log.exception("[JobRuns] %s #%s lỗi", job, job_id)
        _mark_failed(job_id, {"error": type(exc).__name__})
    finally:
        _busy.release()


def _mark_failed(job_id: int, details: dict) -> None:
    with engine.begin() as conn:
        conn.execute(MARK_FAILED, {"id": job_id, "d": json.dumps(details, ensure_ascii=False)})


def process_job_runs() -> None:
    """Gọi từ vòng lặp chính (5 giây/lần). Đang có việc chạy thì bỏ qua lượt này."""
    if not _busy.acquire(blocking=False):
        return
    try:
        with engine.begin() as conn:
            row = conn.execute(CLAIM).mappings().first()
    except Exception:
        _busy.release()
        raise
    if row is None:
        _busy.release()
        return
    threading.Thread(target=_run, args=(row["id"], row["job"]), name=f"job-{row['id']}", daemon=True).start()
