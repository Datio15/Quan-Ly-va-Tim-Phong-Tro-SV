#!/usr/bin/env bash
# =====================================================================
# setup.sh – Dựng tài nguyên Azure cho hệ thống phòng trọ (Người 5). Khớp SPEC v0.4 mục 14.
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
#   * Key Vault dùng ACCESS POLICY (không dùng RBAC). Cấp quyền bằng `az keyvault set-policy`;
#     gán role RBAC không có tác dụng trên vault này.
#   * KHÔNG chạy lại cả script khi tài nguyên đã có: lần chạy mới sinh passphrase sao lưu mới.
#     Script dừng nếu .env.azure đã có nội dung, trừ khi đặt FORCE=1.
# =====================================================================
set -euo pipefail

SUFFIX="${SUFFIX:?Đặt SUFFIX, vd SUFFIX=nhom8}"
LOC="${LOC:-eastasia}"              # vùng đã chốt (SPEC mục 23); Maps là ngoại lệ, xem bước 4
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

if [ -s "$OUT" ] && [ "${FORCE:-0}" != "1" ]; then
  echo "Đã có $OUT. Chạy lại sẽ ghi đè file này và sinh passphrase sao lưu mới." >&2
  echo "Nếu chắc chắn muốn chạy lại: FORCE=1 SUFFIX=$SUFFIX bash $0" >&2
  exit 1
fi

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
put AZURE_QUEUE_NAME ops-ticks
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

step "4. Azure Maps (tài khoản Maps nằm ở vùng global, không theo LOC)"
MAPS_KEY=""
if az maps account create -n "$MAPS" -g "$RG" --sku G2 --kind Gen2 --accept-tos -o none; then
  MAPS_KEY="$(az maps account keys list -n "$MAPS" -g "$RG" --query primaryKey -o tsv)"
  put AZURE_MAPS_KEY "$MAPS_KEY"
else
  echo "   Không tạo được Maps bằng CLI (thường do chính sách vùng của gói Azure for Students)."
  echo "   Tạo ${MAPS} trên portal (gói Gen2, vùng mà portal cho chọn), rồi chạy:"
  echo "   az maps account keys list -n ${MAPS} -g ${RG} --query primaryKey -o tsv"
  echo "   và ghi AZURE_MAPS_KEY vào ${OUT} + Key Vault (azure-maps-key). Tiếp tục các bước sau."
fi

step "5. Key Vault (access policy) và các bí mật"
az keyvault create -n "$KV" -g "$RG" -l "$LOC" --enable-rbac-authorization false -o none
ME="$(az ad signed-in-user show --query id -o tsv)"
az keyvault set-policy -n "$KV" --object-id "$ME" --secret-permissions get list set delete -o none
echo "   Chờ 15 giây để quyền có hiệu lực..."; sleep 15
PASS="$(openssl rand -base64 32)"
az keyvault secret set --vault-name "$KV" -n backup-passphrase --value "$PASS" -o none
az keyvault secret set --vault-name "$KV" -n search-admin-key  --value "$ADMIN_KEY" -o none
if [ -n "$MAPS_KEY" ]; then
  az keyvault secret set --vault-name "$KV" -n azure-maps-key --value "$MAPS_KEY" -o none
fi
put BACKUP_PASSPHRASE "\"$PASS\""
put AZURE_KEY_VAULT_URL "https://${KV}.vault.azure.net"
echo "   Cấp quyền đọc cho thành viên khác (object id lấy bằng az ad user show --id <email> --query id -o tsv):"
echo "   az keyvault set-policy -n ${KV} --object-id <object-id> --secret-permissions get list"

step "6. Application Insights"
put APPLICATIONINSIGHTS_CONNECTION_STRING "\"$(az monitor app-insights component create --app "$APPI" \
  -g "$RG" -l "$LOC" --kind web --application-type web --query connectionString -o tsv)\""

step "7. Function App (Python, gói Flex Consumption)"
# Nếu vùng chưa hỗ trợ Flex Consumption hoặc lệnh báo lỗi: tạo Function App trên portal
# (Python 3.11, Linux, gói Flex Consumption) rồi chạy tiếp các lệnh còn lại của bước này.
az functionapp create -g "$RG" -n "$FUNC" --storage-account "$ST" \
  --flexconsumption-location "$LOC" --runtime python --runtime-version 3.11 -o none
# Managed identity của Function đọc Key Vault qua access policy (quyền get).
FUNC_PRINCIPAL="$(az functionapp identity assign -g "$RG" -n "$FUNC" --query principalId -o tsv)"
az keyvault set-policy -n "$KV" --object-id "$FUNC_PRINCIPAL" --secret-permissions get -o none
az functionapp config appsettings set -g "$RG" -n "$FUNC" -o none --settings \
  "AZURE_SEARCH_ENDPOINT=https://${SEARCH}.search.windows.net" \
  "AZURE_SEARCH_INDEX=rooms-public" \
  "AZURE_SEARCH_ADMIN_KEY=@Microsoft.KeyVault(VaultName=${KV};SecretName=search-admin-key)" \
  "OPS_QUEUE_NAME=ops-ticks"
# Kiểm tra đủ 4 app settings (chỉ in tên, không in giá trị).
SETTINGS="$(az functionapp config appsettings list -g "$RG" -n "$FUNC" --query '[].name' -o tsv)"
for k in AZURE_SEARCH_ENDPOINT AZURE_SEARCH_INDEX AZURE_SEARCH_ADMIN_KEY OPS_QUEUE_NAME; do
  if printf '%s\n' "$SETTINGS" | grep -qx "$k"; then echo "   có $k"; else echo "   THIẾU $k, đặt lại bằng appsettings set"; fi
done
put AZURE_FUNCTION_INGEST_URL "https://${FUNC}.azurewebsites.net/api/ingest-room"
echo "   Sau khi deploy code Function, lấy khóa hàm:"
echo "   az functionapp keys list -n ${FUNC} -g ${RG} --query functionKeys.default -o tsv"
echo "   rồi ghi AZURE_FUNCTION_KEY vào .env của VM và vào Key Vault (function-key)."
echo "   Trên portal, Function App → Environment variables: AZURE_SEARCH_ADMIN_KEY phải hiện Resolved."

step "Xong. Các giá trị cần thiết đã ghi vào ${OUT} (quyền 600). KHÔNG commit file này."
echo "Nhớ: tắt hoặc xóa tài nguyên sau khi quay video:  az group delete -n ${RG}"
