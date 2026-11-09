#!/usr/bin/env bash
# =====================================================================
# restore-test.sh – Khôi phục THỬ bản sao lưu vào một CSDL riêng và đối chiếu.
# Không đụng vào CSDL đang chạy. Dùng để đo thời gian khôi phục (RTO) cho báo cáo và demo.
#
#   scripts/restore-test.sh                 # tải bản MỚI NHẤT từ Azure Blob
#   scripts/restore-test.sh <file.enc>      # dùng file cục bộ
#
# Biến môi trường:
#   DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD   CSDL chính (để ghi job_runs)
#   BACKUP_PASSPHRASE                             khóa giải mã
#   AZURE_BACKUP_CONTAINER_URL, AZURE_BACKUP_SAS_READ   SAS chỉ có quyền read+list
#   RESTORE_DB      (tùy chọn) tên CSDL thử, mặc định ${DB_NAME}_restore_test
#   JOB_RUN_ID      (tùy chọn) id dòng job_runs có sẵn (status='queued') do trang quản trị tạo
#
# Kết quả: bảng so sánh số dòng; mã thoát 0 nếu khớp hoàn toàn, 2 nếu lệch.
# =====================================================================
set -euo pipefail

: "${DB_HOST:?}" "${DB_PORT:?}" "${DB_NAME:?}" "${DB_USER:?}" "${BACKUP_PASSPHRASE:?}"
export PGPASSWORD="${DB_PASSWORD:-}" BACKUP_PASSPHRASE
RESTORE_DB="${RESTORE_DB:-${DB_NAME}_restore_test}"

psql_main() { psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -Atq "$@"; }
psql_test() { psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$RESTORE_DB" -v ON_ERROR_STOP=1 -Atq "$@"; }

start_ms="$(date +%s%3N)"
if [[ -n "${JOB_RUN_ID:-}" ]]; then
  job_id="$JOB_RUN_ID"
  psql_main -c "UPDATE job_runs SET status='running', started_at=now() WHERE id=${job_id}"
else
  job_id="$(psql_main -c "INSERT INTO job_runs (job) VALUES ('restore_test') RETURNING id")"
fi
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
trap 'psql_main -c "UPDATE job_runs SET status='"'"'failed'"'"', finished_at=now() WHERE id=${job_id}" || true' ERR

# 1. Lấy file sao lưu
if [[ $# -ge 1 ]]; then
  src="$1"
  cp "$src" "$work/backup.enc"
else
  : "${AZURE_BACKUP_CONTAINER_URL:?}" "${AZURE_BACKUP_SAS_READ:?}"
  # Liệt kê blob; tên có dấu thời gian nên bản mới nhất là tên lớn nhất
  curl -sS --fail -H "x-ms-version: 2021-08-06" \
    "${AZURE_BACKUP_CONTAINER_URL}?restype=container&comp=list&${AZURE_BACKUP_SAS_READ}" -o "$work/list.xml"
  src="$(python3 -I -c '
import sys, xml.etree.ElementTree as ET
names = [e.text for e in ET.parse(sys.argv[1]).iter("Name") if e.text and e.text.endswith(".tar.gz.enc")]
print(max(names) if names else "")' "$work/list.xml")"
  [[ -n "$src" ]] || { echo "Không có bản sao lưu nào trên Azure" >&2; exit 1; }
  curl -sS --fail -H "x-ms-version: 2021-08-06" \
    "${AZURE_BACKUP_CONTAINER_URL}/${src}?${AZURE_BACKUP_SAS_READ}" -o "$work/backup.enc"
fi
download_ms="$(( $(date +%s%3N) - start_ms ))"

# 2. Giải mã, giải nén, kiểm tra mã băm
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:BACKUP_PASSPHRASE \
  -in "$work/backup.enc" -out "$work/bundle.tar.gz"
mkdir "$work/bundle" && tar -C "$work/bundle" -xzf "$work/bundle.tar.gz"
manifest="$work/bundle/manifest.json"
want_sha="$(python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["db_dump_sha256"])' "$manifest")"
have_sha="$(sha256sum "$work/bundle/db.dump" | cut -d' ' -f1)"
[[ "$want_sha" == "$have_sha" ]] || { echo "Sai mã băm db.dump" >&2; exit 1; }

# 3. Nạp vào CSDL thử (xóa bản thử cũ nếu có)
psql_main -c "DROP DATABASE IF EXISTS \"${RESTORE_DB}\""
psql_main -c "CREATE DATABASE \"${RESTORE_DB}\""
pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$RESTORE_DB" --no-owner --exit-on-error "$work/bundle/db.dump"
restore_ms="$(( $(date +%s%3N) - start_ms ))"

# 4. Đối chiếu số dòng với manifest
ok=true
printf '%-16s %10s %10s\n' "Bảng" "Sao lưu" "Khôi phục"
for t in $(python3 -I -c 'import json,sys; print(" ".join(json.load(open(sys.argv[1]))["row_counts"]))' "$manifest"); do
  want="$(python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["row_counts"][sys.argv[2]])' "$manifest" "$t")"
  have="$(psql_test -c "SELECT count(*) FROM $t")"
  mark=""; [[ "$want" == "$have" ]] || { mark="  <-- LỆCH"; ok=false; }
  printf '%-16s %10s %10s%s\n' "$t" "$want" "$have" "$mark"
done

total_ms="$(( $(date +%s%3N) - start_ms ))"
status="success"; $ok || status="failed"
psql_main -c "UPDATE job_runs SET status='${status}', finished_at=now(), details = jsonb_build_object(
  'source', '$(basename "$src")', 'counts_match', ${ok}, 'download_ms', ${download_ms},
  'restore_ms', ${restore_ms}, 'total_ms', ${total_ms}) WHERE id=${job_id}"

echo "Nguồn: $(basename "$src") · tổng thời gian: ${total_ms} ms · khớp: ${ok}"
$ok || exit 2
