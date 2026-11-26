# Lưu ý: chuyển worker sang SAS giới hạn quyền

Dành cho người triển khai Azure và vm-app. Đọc hết trước khi làm, làm **đúng thứ tự**.

## 1. Vì sao đổi

Trước đây worker dùng `AZURE_STORAGE_CONNECTION_STRING`, chuỗi kết nối chứa khóa tài khoản lưu trữ, tức là **toàn quyền**
trên `stphongtro<SUFFIX>`. Ai chiếm được vm-app có thể xóa luôn container `backups`, làm mất tác dụng của việc
tách SAS ghi/đọc cho sao lưu (SPEC mục 16).

Worker thật ra chỉ cần:

| Tài nguyên | Thao tác của worker | SAS mới | Policy |
|---|---|---|---|
| Container `public-images` | tải ảnh lên, liệt kê và xóa ảnh khi phòng bị ẩn | `cwdl` (tạo, ghi, xóa, liệt kê; **không đọc**) | `worker-pub` |
| Queue `ops-ticks` | nhận tin, xóa tin đã xử lý | `p` (process; **không thêm tin**) | `worker-queue` |

Mỗi SAS gắn một **stored access policy**: xóa policy là SAS mất hiệu lực ngay, không phải đổi khóa tài khoản.

## 2. Thay đổi trong mã (nhánh `fix/worker-sas`)

| File | Thay đổi |
|---|---|
| `worker/worker/storage.py` (mới) | Tạo client Blob/Queue: ưu tiên SAS, thiếu SAS thì dùng chuỗi kết nối như cũ |
| `worker/worker/outbox.py`, `queue.py` | Dùng `storage.py` thay cho chuỗi kết nối |
| `worker/worker/outbox.py` | `public_url` luôn bỏ phần query: client tạo từ SAS có `blob_client.url` **kèm chữ ký SAS**, nếu không bỏ thì SAS quyền ghi/xóa bị lưu vào CSDL và lộ lên AI Search |
| `worker/tests/test_storage.py` (mới) | 11 kiểm thử, không cần Azure |
| `infra/azure/setup.sh` | Tạo hai policy và hai SAS cho worker |
| `.env.example`, `SPEC.md`, `LUU-Y.md` | Biến môi trường mới |

Biến môi trường mới (đặt trong `.env` của **vm-app**):

```
AZURE_PUBLIC_IMAGES_SAS="<SAS cwdl của public-images>"
AZURE_QUEUE_URL=https://stphongtro<SUFFIX>.queue.core.windows.net/ops-ticks
AZURE_QUEUE_SAS="<SAS p của ops-ticks>"
```

URL container lấy từ `AZURE_BLOB_PUBLIC_BASE_URL` sẵn có. Nếu biến này về sau trỏ sang CDN, đặt thêm
`AZURE_PUBLIC_IMAGES_URL=https://stphongtro<SUFFIX>.blob.core.windows.net/public-images`.

## 3. Bước 1: tạo SAS trên Azure (Cloud Shell, chế độ **Bash**)

Cloud Shell đang ở PowerShell (`PS /home/...>`) thì gõ `bash` trước. Làm bước này lúc nào cũng được: worker đang chạy
không bị ảnh hưởng.

```bash
RG=rg-phongtro
ST=$(az storage account list -g $RG --query "[?starts_with(name,'stphongtro')].name" -o tsv); echo $ST
KEY=$(az storage account keys list -g $RG -n $ST --query "[0].value" -o tsv)
EXP=2027-01-31T00:00Z

az storage container policy create --container-name public-images --name worker-pub \
  --permissions cwdl --expiry $EXP --account-name $ST --account-key "$KEY"
az storage queue policy create --queue-name ops-ticks --name worker-queue \
  --permissions p --expiry $EXP --account-name $ST --account-key "$KEY"

PUB_SAS=$(az storage container generate-sas --name public-images --policy-name worker-pub \
  --https-only --account-name $ST --account-key "$KEY" -o tsv)
Q_SAS=$(az storage queue generate-sas --name ops-ticks --policy-name worker-queue \
  --https-only --account-name $ST --account-key "$KEY" -o tsv)
```

Biến trong Cloud Shell mất khi phiên hết hạn. Mất thì chạy lại các dòng `ST=`, `KEY=`, `PUB_SAS=`, `Q_SAS=`;
policy vẫn còn, SAS sinh lại bao nhiêu lần cũng được.

## 4. Bước 2: kiểm tra quyền (chụp ảnh cho báo cáo, mục IAM)

```bash
# Phải CHẠY ĐƯỢC
az storage blob list -c public-images --account-name $ST --sas-token "$PUB_SAS" --num-results 3 -o table
# Phải BỊ TỪ CHỐI (AuthorizationFailure): SAS ảnh không đụng được container backups
az storage blob list -c backups --account-name $ST --sas-token "$PUB_SAS" -o table
# Phải BỊ TỪ CHỐI: SAS hàng đợi không thêm được tin
az storage message put -q ops-ticks --content test --account-name $ST --sas-token "$Q_SAS"
```

**Không** thử `az storage message get` với SAS hàng đợi: lệnh đó lấy mất tin nhắc việc thật của worker.

In ra để chép sang vm-app:

```bash
echo "AZURE_PUBLIC_IMAGES_SAS=\"$PUB_SAS\""
echo "AZURE_QUEUE_URL=https://$ST.queue.core.windows.net/ops-ticks"
echo "AZURE_QUEUE_SAS=\"$Q_SAS\""
```

## 5. Bước 3: vm-app (làm sau khi PR `fix/worker-sas` đã merge vào `main`)

1. Thêm ba dòng trên vào `.env` của vm-app. **Chưa** xóa `AZURE_STORAGE_CONNECTION_STRING`.
2. Lấy mã `main` mới, build image worker mới (ví dụ `phongtro-worker:v06`) và chạy lại, cùng cách đã làm với `v05`.
3. Xem log:
   ```bash
   docker compose logs worker --tail 100 | grep Storage
   ```
   Phải thấy `[Storage] queue: dùng SAS giới hạn quyền` (trong vòng 30 giây, lần đọc hàng đợi đầu tiên).
   Dòng `[Storage] public-images: dùng SAS giới hạn quyền` chỉ hiện khi có ảnh cần tải lên hoặc xóa.
   Thấy `đang dùng AZURE_STORAGE_CONNECTION_STRING` nghĩa là worker chưa đọc được SAS: kiểm tra lại tên biến và dấu nháy.
4. Chạy lại **TC13** (duyệt một phòng có ảnh, ảnh lên Blob, tìm thấy trên Azure trong 15 giây) và **TC18**
   (`tick-now?type=viewing_reminder`, Telegram nhận nhắc). Mở `public_url` của ảnh mới: **không** được có `?sv=`, `sig=`.
5. Cả hai đạt thì xóa dòng `AZURE_STORAGE_CONNECTION_STRING` khỏi `.env` của vm-app, chạy lại worker
   (`docker compose up -d worker`), kiểm tra lại bước 3 và 4. Log không còn dòng "toàn quyền tài khoản".

**Không** xóa chuỗi kết nối trước khi image mới chạy: worker cũ không biết SAS, sẽ dừng đẩy ảnh và đọc hàng đợi.

## 6. Quay lại khi có sự cố

Thêm lại `AZURE_STORAGE_CONNECTION_STRING` vào `.env` và xóa ba biến SAS, rồi `docker compose up -d worker`.
Mã mới tự dùng chuỗi kết nối khi thiếu SAS; image `v05` vẫn chạy được như trước.

## 7. Vận hành về sau

| Việc | Cách làm |
|---|---|
| SAS bị lộ | Xóa policy: `az storage container policy delete -c public-images -n worker-pub ...` (hoặc `queue policy delete -q ops-ticks -n worker-queue`). SAS mất hiệu lực ngay. Tạo policy mới, sinh SAS mới, thay trong `.env` |
| Gia hạn | `az storage container policy update -c public-images -n worker-pub --expiry <ngày mới> ...` (tương tự cho queue). **SAS giữ nguyên**, không phải sửa `.env` |
| Đổi khóa tài khoản | Nên làm **sau khi nộp bài** vì khóa cũ từng nằm trên VM. Thứ tự: chuyển `AzureWebJobsStorage` của Function App sang key2 → regenerate key1 → sinh lại mọi SAS bằng key2 (hai SAS worker và hai SAS sao lưu) → cập nhật `.env` trên vm-app và vm-data |

## 8. Máy cá nhân

Chỉ **một** worker được đọc hàng đợi `ops-ticks` (worker trên vm-app). Nếu `.env` máy cá nhân có SAS hàng đợi, đặt trong
`docker-compose.override.yml` (không đưa lên git):

```yaml
services:
  worker:
    environment:
      AZURE_QUEUE_SAS: ""
      AZURE_STORAGE_CONNECTION_STRING: ""
```

## 9. Không được

- Dán SAS hoặc chuỗi kết nối vào chat nhóm, ảnh chụp, video demo, báo cáo hay git.
- Dùng chung SAS của worker cho việc khác (sao lưu đã có SAS riêng `cw` và `rl`).
- Chép `AZURE_STORAGE_CONNECTION_STRING` từ `.env.azure` lên VM khi đã có SAS.

## 10. Kiểm thử mã

```bash
docker compose run --rm --no-deps -v ./worker/tests:/app/tests worker python -m unittest discover -s tests -v
```

Kết quả mong đợi: 14 kiểm thử (11 của `test_storage.py`, 3 của `test_metrics.py`) đều `ok`.
