#!/usr/bin/env bash
# =====================================================================
# setup.sh – Dựng tài nguyên Azure cho hệ thống phòng trọ (Người 5).
#     az login
#     SUFFIX=<3-6 chữ thường/số riêng của nhóm> bash infra/azure/setup.sh
#
# Lưu ý:
#   * Chạy TỪNG KHỐI và kiểm tra trên portal. Tên lệnh và tùy chọn của Azure CLI thay đổi theo
#     phiên bản: nếu một lệnh báo lỗi tham số, xem `az <lệnh> --help` hoặc làm khối đó trên portal.
#   * Đặt NGÂN SÁCH (Budget) trên portal TRƯỚC khi chạy: Cost Management → Budgets.
#   * Giá và điều kiện miễn phí (AI Search Free, Maps, Functions) cần kiểm tra trên trang chính thức.
#   * Script KHÔNG in khóa ra màn hình; khóa được ghi vào file .env.azure (quyền 600, bị .gitignore
#     chặn qua mẫu .env.*) và Key Vault. Chép các dòng cần thiết sang .env trên VM.
# =====================================================================
set -euo pipefail

SUFFIX="${SUFFIX:?Đặt SUFFIX, vd SUFFIX=nhom8}"
LOC="${LOC:-southeastasia}"
RG="rg-phongtro"
ST="stphongtro${SUFFIX}"            # tên storage: 3-24 ký tự thường/số, duy nhất toàn cầu
SEARCH="srch-phongtro-${SUFFIX}"
MAPS="maps-phongtro-${SUFFIX}"
KV="kv-phongtro-${SUFFIX}"
APPI="appi-phongtro"
FUNC="func-phongtro-${SUFFIX}"
OUT="${OUT:-.env.azure}"            # nơi ghi các giá trị để dán vào .env trên VM
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"

step() { printf '\n==> %s\n' "$*"; }
az config set extension.use_dynamic_install=yes_without_prompt >/dev/null 2>&1 || true
umask 077; : > "$OUT"
put() { printf '%s=%s\n' "$1" "$2" >> "$OUT"; }

step "1. Resource group ${RG} (${LOC})"
az group create -n "$RG" -l "$LOC" -o none

step "2. Storage: container public-images (đọc công khai), backups (riêng tư), queue ops-ticks"
az storage account create -n "$ST" -g "$RG" -l "$LOC" --sku Standard_LRS --kind StorageV2 \
  --min-tls-version TLS1_2 --allow-blob-public-access true -o none
CONN="$(az storage account show-connection-string -n "$ST" -g "$RG" -o tsv)"
az storage container create -n public-images --public-access blob --connection-string "$CONN" -o none
az storage container create -n backups --public-access off --connection-string "$CONN" -o none
az storage queue create -n ops-ticks --connection-string "$CONN" -o none
EXPIRY="$(date -u -d '+45 days' +%Y-%m-%dT%H:%MZ)"
put AZURE_STORAGE_CONNECTION_STRING "\"$CONN\""
put AZURE_BACKUP_CONTAINER_URL "https://${ST}.blob.core.windows.net/backups"
put AZURE_BACKUP_SAS_WRITE "\"$(az storage container generate-sas -n backups --permissions cw \
  --expiry "$EXPIRY" --https-only --connection-string "$CONN" -o tsv)\""
put AZURE_BACKUP_SAS_READ "\"$(az storage container generate-sas -n backups --permissions rl \
  --expiry "$EXPIRY" --https-only --connection-string "$CONN" -o tsv)\""
put AZURE_BLOB_PUBLIC_BASE_URL "https://${ST}.blob.core.windows.net/public-images"

step "3. AI Search (gói free) và chỉ mục rooms-public"
az search service create -n "$SEARCH" -g "$RG" -l "$LOC" --sku free -o none
ADMIN_KEY="$(az search admin-key show --service-name "$SEARCH" -g "$RG" --query primaryKey -o tsv)"
curl -sS --fail -X PUT "https://${SEARCH}.search.windows.net/indexes/rooms-public?api-version=2024-07-01" \
  -H "Content-Type: application/json" -H "api-key: ${ADMIN_KEY}" \
  --data-binary "@${ROOT}/azure-functions/search-index.json" -o /dev/null
put AZURE_SEARCH_ENDPOINT "https://${SEARCH}.search.windows.net"
put AZURE_SEARCH_INDEX rooms-public
put AZURE_SEARCH_QUERY_KEY "$(az search query-key list --service-name "$SEARCH" -g "$RG" --query '[0].key' -o tsv)"
# Khóa admin chỉ dành cho Function (ghi chỉ mục): lưu vào Key Vault ở bước 5, không đưa lên VM.

step "4. Azure Maps"
az maps account create -n "$MAPS" -g "$RG" --sku G2 --kind Gen2 --accept-tos -o none
put AZURE_MAPS_KEY "$(az maps account keys list -n "$MAPS" -g "$RG" --query primaryKey -o tsv)"

step "5. Key Vault và các bí mật"
az keyvault create -n "$KV" -g "$RG" -l "$LOC" -o none
ME="$(az ad signed-in-user show --query id -o tsv)"
KV_ID="$(az keyvault show -n "$KV" --query id -o tsv)"
az role assignment create --role "Key Vault Secrets Officer" --assignee "$ME" --scope "$KV_ID" -o none || true
echo "   Chờ 60 giây để quyền có hiệu lực..."; sleep 60
PASS="$(openssl rand -base64 32)"
az keyvault secret set --vault-name "$KV" -n backup-passphrase --value "$PASS" -o none
az keyvault secret set --vault-name "$KV" -n search-admin-key  --value "$ADMIN_KEY" -o none
put BACKUP_PASSPHRASE "\"$PASS\""
put AZURE_KEY_VAULT_URL "https://${KV}.vault.azure.net"

step "6. Application Insights"
put APPLICATIONINSIGHTS_CONNECTION_STRING "\"$(az monitor app-insights component create --app "$APPI" \
  -g "$RG" -l "$LOC" --kind web --application-type web --query connectionString -o tsv)\""

step "7. Function App (Python, gói Flex Consumption)"
# Nếu vùng chưa hỗ trợ Flex Consumption hoặc lệnh báo lỗi: tạo Function App trên portal
# (Python 3.11, Linux, gói Consumption/Flex Consumption) rồi chạy tiếp từ bước 8.
az functionapp create -g "$RG" -n "$FUNC" --storage-account "$ST" \
  --flexconsumption-location "$LOC" --runtime python --runtime-version 3.11 -o none
az functionapp config appsettings set -g "$RG" -n "$FUNC" -o none --settings \
  "AZURE_SEARCH_ENDPOINT=https://${SEARCH}.search.windows.net" \
  "AZURE_SEARCH_INDEX=rooms-public" \
  "AZURE_SEARCH_ADMIN_KEY=@Microsoft.KeyVault(VaultName=${KV};SecretName=search-admin-key)" \
  "OPS_QUEUE_NAME=ops-ticks"
put AZURE_FUNCTION_INGEST_URL "https://${FUNC}.azurewebsites.net/api/ingest-room"
echo "   Sau khi deploy code Function, lấy khóa hàm: az functionapp function keys list ..."
echo "   rồi ghi AZURE_FUNCTION_KEY vào .env của VM và vào Key Vault (function-key)."
echo "   Để Function đọc được Key Vault: bật managed identity cho Function App và gán quyền"
echo "   'Key Vault Secrets User' trên ${KV}."

step "Xong. Các giá trị cần thiết đã ghi vào ${OUT} (quyền 600). KHÔNG commit file này."
echo "Nhớ: tắt hoặc xóa tài nguyên sau khi quay video:  az group delete -n ${RG}"
