#!/usr/bin/env bash
# =====================================================================
# backup.sh – Sao lưu CSDL (+ MinIO nếu có) → mã hóa → tải lên Azure Blob.
# Chạy trên vm-data (cron 02:00 hằng ngày) hoặc khi worker nhận tín hiệu daily_backup.
#
# Biến môi trường (đọc từ .env):
#   DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD   kết nối PostgreSQL
#   BACKUP_PASSPHRASE                             khóa mã hóa (bản gốc ở Key Vault: backup-passphrase)
#   AZURE_BACKUP_CONTAINER_URL                    vd https://stphongtroxx.blob.core.windows.net/backups
#   AZURE_BACKUP_SAS_WRITE                        SAS chỉ có quyền create+write (không read/delete)
#   MC_ALIAS        (tùy chọn) alias của MinIO Client đã cấu hình, vd "local"
#   BACKUP_DIR      (tùy chọn) nơi giữ bản cục bộ, mặc định /var/backups/phongtro
#   KEEP_LOCAL      (tùy chọn) số bản cục bộ giữ lại, mặc định 3
#   DRY_RUN=1       (tùy chọn) không tải lên Azure, chỉ tạo file cục bộ
#   JOB_RUN_ID      (tùy chọn) id dòng job_runs có sẵn (status='queued', do trang quản trị tạo);
#                   worker truyền vào để kết quả ghi đúng dòng đó. Không có thì script tự tạo dòng mới.
#
# Kết quả: in ra đường dẫn file .enc; ghi một dòng vào bảng job_runs (job = 'backup').
# =====================================================================
set -euo pipefail

: "${DB_HOST:?}" "${DB_PORT:?}" "${DB_NAME:?}" "${DB_USER:?}" "${BACKUP_PASSPHRASE:?}"
export PGPASSWORD="${DB_PASSWORD:-}" BACKUP_PASSPHRASE
BACKUP_DIR="${BACKUP_DIR:-/var/backups/phongtro}"
KEEP_LOCAL="${KEEP_LOCAL:-3}"
DRY_RUN="${DRY_RUN:-0}"
TABLES="users houses rooms room_images bookings reviews tenants meter_readings invoices"

psql_q() { psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -Atq "$@"; }

ts="$(date -u +%Y%m%dT%H%M%SZ)"
name="phongtro-${ts}.tar.gz.enc"
start_ms="$(date +%s%3N)"
if [[ -n "${JOB_RUN_ID:-}" ]]; then
  job_id="$JOB_RUN_ID"
  psql_q -c "UPDATE job_runs SET status='running', started_at=now() WHERE id=${job_id}"
else
  job_id="$(psql_q -c "INSERT INTO job_runs (job) VALUES ('backup') RETURNING id")"
fi

work="$(mktemp -d)"
cleanup() { rm -rf "$work"; }
fail() {
  psql_q -c "UPDATE job_runs SET status='failed', finished_at=now(),
             details = jsonb_build_object('error', '$1') WHERE id=${job_id}" || true
  echo "BACKUP FAILED: $1" >&2
  exit 1
}
trap cleanup EXIT
trap 'fail "line $LINENO"' ERR

mkdir -p "$BACKUP_DIR" "$work/bundle"

# 1. CSDL (định dạng custom của pg_dump, nén sẵn)
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -Fc -f "$work/bundle/db.dump"

# 2. File trong MinIO (nếu đã cấu hình mc)
minio_included=false
if [[ -n "${MC_ALIAS:-}" ]] && command -v mc >/dev/null 2>&1; then
  for b in private public-src; do
    mc mirror --quiet "${MC_ALIAS}/${b}" "$work/bundle/minio/${b}" || true
  done
  minio_included=true
fi

# 3. Manifest: số dòng các bảng chính + mã băm, để khôi phục thử đối chiếu
counts="{"
for t in $TABLES; do
  counts+="\"$t\": $(psql_q -c "SELECT count(*) FROM $t"),"
done
counts="${counts%,}}"
db_sha="$(sha256sum "$work/bundle/db.dump" | cut -d' ' -f1)"
cat > "$work/bundle/manifest.json" <<EOF
{
  "created_at": "${ts}",
  "db_name": "${DB_NAME}",
  "db_dump_sha256": "${db_sha}",
  "minio_included": ${minio_included},
  "row_counts": ${counts}
}
EOF

# 4. Đóng gói và mã hóa (AES-256, khóa dẫn xuất PBKDF2)
tar -C "$work/bundle" -czf "$work/bundle.tar.gz" .
openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
  -pass env:BACKUP_PASSPHRASE -in "$work/bundle.tar.gz" -out "$BACKUP_DIR/$name"
size_bytes="$(stat -c %s "$BACKUP_DIR/$name")"

# 5. Tải lên Azure Blob bằng SAS chỉ-ghi (REST Put Blob, không cần cài Azure CLI)
blob_path="${ts:0:4}/${ts:4:2}/${name}"
uploaded=false
if [[ "$DRY_RUN" != "1" ]]; then
  : "${AZURE_BACKUP_CONTAINER_URL:?}" "${AZURE_BACKUP_SAS_WRITE:?}"
  curl -sS --fail -X PUT \
    -H "x-ms-blob-type: BlockBlob" -H "x-ms-version: 2021-08-06" \
    --data-binary "@$BACKUP_DIR/$name" \
    "${AZURE_BACKUP_CONTAINER_URL}/${blob_path}?${AZURE_BACKUP_SAS_WRITE}"
  uploaded=true
fi

# 6. Chỉ giữ KEEP_LOCAL bản mới nhất ở máy
ls -1t "$BACKUP_DIR"/phongtro-*.tar.gz.enc | tail -n +"$((KEEP_LOCAL + 1))" | xargs -r rm -f

duration_ms="$(( $(date +%s%3N) - start_ms ))"
psql_q -c "UPDATE job_runs SET status='success', finished_at=now(), details = jsonb_build_object(
  'file', '${name}', 'blob_path', '${blob_path}', 'size_bytes', ${size_bytes},
  'db_dump_sha256', '${db_sha}', 'uploaded', ${uploaded}, 'minio_included', ${minio_included},
  'duration_ms', ${duration_ms}) WHERE id=${job_id}"

echo "$BACKUP_DIR/$name"
