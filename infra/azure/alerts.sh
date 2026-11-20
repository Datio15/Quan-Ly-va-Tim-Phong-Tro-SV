#!/usr/bin/env bash
# =====================================================================
# alerts.sh – Tạo 4 quy tắc cảnh báo của SPEC §17 (TC22), gửi qua Action Group → Logic App → Telegram.
#
# Chạy trong Azure Cloud Shell (Bash) hoặc máy có Azure CLI đã `az login`:
#   bash infra/azure/alerts.sh                 # tạo hoặc cập nhật cả 4 quy tắc
#   ONLY=dong-bo-loi bash infra/azure/alerts.sh   # chỉ một quy tắc
#
# Cần có sẵn: Application Insights `appi-phongtro`, Action Group `ag-phongtro-alerts` (đã nối Logic App).
# Quy tắc là "log search alert" (bảng customMetrics, requests của Application Insights), vì số đo
# OpenTelemetry nằm trong customMetrics. Chạy lại nhiều lần được: cùng tên thì cập nhật.
# Cảnh báo Budget (50/80/100 %) gắn trên portal, không nằm trong script này (SPEC §14).
# =====================================================================
set -euo pipefail

RG="${RG:-rg-phongtro}"
APPI="${APPI:-appi-phongtro}"
AG="${AG:-ag-phongtro-alerts}"
LOC="${LOC:-eastasia}"
ONLY="${ONLY:-}"

step() { printf '\n==> %s\n' "$*"; }

az config set extension.use_dynamic_install=yes_without_prompt -o none 2>/dev/null || true

step "Tìm Application Insights và Action Group"
APPI_ID="$(az monitor app-insights component show -g "$RG" -a "$APPI" --query id -o tsv)"
AG_ID="$(az monitor action-group show -g "$RG" -n "$AG" --query id -o tsv)"
echo "   appi: ${APPI_ID##*/}   action group: ${AG_ID##*/}"

# rule <tên> <mức 0-4> <tần suất> <cửa sổ> <điều kiện> <truy vấn> <mô tả>
rule() {
  local name="alert-$1"
  [[ -z "$ONLY" || "$ONLY" == "$1" ]] || return 0
  step "Quy tắc $name"
  az monitor scheduled-query create -g "$RG" -n "$name" -l "$LOC" \
    --scopes "$APPI_ID" --action-groups "$AG_ID" \
    --severity "$2" --evaluation-frequency "$3" --window-size "$4" \
    --condition "$5" --condition-query Q="$6" \
    --description "$7" --auto-mitigate true -o none
  echo "   đã tạo/cập nhật"
}

# 1. Đồng bộ lỗi (TC22): có lần gửi lỗi trong cửa sổ, HOẶC còn dòng outbox đã bỏ cuộc.
#    SPEC ghi 15 phút. Worker thử lại sau 1, 2, 4, 8, 16, 30 phút nên chỉ dựa vào sync_failures thì cảnh báo
#    tự tắt giữa chừng; outbox_failed giữ cảnh báo cho tới khi quản trị bấm "Đồng bộ lại".
rule dong-bo-loi 2 5m 15m "count 'Q' > 0" \
  "customMetrics | where (name == 'sync_failures' and valueSum > 0) or (name == 'outbox_failed' and value > 0)" \
  "Đồng bộ OpenStack -> Azure lỗi (sync_failures > 0 hoặc outbox_failed > 0). Xem trang Hệ thống."

# 2. Worker chết: không có worker_heartbeat. SPEC ghi 5 phút; dùng cửa sổ 10 phút vì số đo xuất 60 giây
#    một lần và Application Insights nhận trễ 1-3 phút, cửa sổ 5 phút dễ báo nhầm.
rule worker-chet 1 5m 10m "total n from 'Q' < 1" \
  "print n = toscalar(customMetrics | where name == 'worker_heartbeat' | count)" \
  "Không thấy worker_heartbeat trong 10 phút: worker trên vm-app có thể đã dừng."

# 3. Sao lưu trễ: không có backup_success (bản đã tải lên Blob) trong 26 giờ. Cửa sổ dài nhất của log alert là
#    2 ngày nên lọc 26 giờ trong truy vấn. Chỉ tính bản do worker chạy (tin daily_backup 02:00 hoặc nút bấm);
#    nếu nhóm chỉ dùng cron trên vm-data thì quy tắc này sẽ báo nhầm.
rule sao-luu-tre 2 1h 2d "total n from 'Q' < 1" \
  "print n = toscalar(customMetrics | where timestamp > ago(26h) and name == 'backup_success' and tostring(customDimensions['uploaded']) == 'true' | count)" \
  "Không có bản sao lưu nào được tải lên Blob trong 26 giờ."

# 4. api lỗi nhiều: tỷ lệ 5xx > 5 % trong 5 phút (số đo request do OpenTelemetry của api tự gửi).
rule api-loi-5xx 2 5m 5m "total rate from 'Q' > 5" \
  "requests | summarize total = count(), bad = countif(toint(resultCode) >= 500) | extend rate = iff(total == 0, 0.0, 100.0 * bad / total) | project rate" \
  "Tỷ lệ lỗi 5xx của api vượt 5% trong 5 phút."

step "Các quy tắc hiện có"
az monitor scheduled-query list -g "$RG" --query "[?starts_with(name, 'alert-')].{ten:name, bat:enabled, muc:severity, cua_so:windowSize}" -o table
