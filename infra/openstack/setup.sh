#!/usr/bin/env bash
# =====================================================================
# setup.sh – Dựng hạ tầng OpenStack cho hệ thống phòng trọ (Người 4).
# Chạy trên máy host DevStack, sau khi nạp biến môi trường quản trị:
#     source /opt/stack/devstack/openrc admin admin
#     ADMIN_CIDR=<dải IP được SSH, vd 100.64.0.0/10 nếu dùng Tailscale> bash infra/openstack/setup.sh
# Script chạy lại được nhiều lần: tài nguyên đã có thì bỏ qua.
# Kiểm tra mỗi khối bằng Horizon hoặc lệnh `openstack ... list` trước khi sang khối sau.
# =====================================================================
set -euo pipefail

PROJECT="${PROJECT:-phongtro}"
EXT_NET="${EXT_NET:-public}"                    # mạng ngoài mặc định của DevStack
ADMIN_CIDR="${ADMIN_CIDR:?Đặt ADMIN_CIDR: dải IP được phép SSH}"
SUBNET_RANGE="${SUBNET_RANGE:-10.20.0.0/24}"
IMAGE_NAME="ubuntu-24.04"                         # 24.04 có sẵn postgresql-client 16 (khớp PostgreSQL 16)
IMAGE_FILE="noble-server-cloudimg-amd64.img"
IMAGE_URL="https://cloud-images.ubuntu.com/noble/current/${IMAGE_FILE}"
FLAVOR="pt.small"                                 # 2 vCPU, 3 GB RAM, 20 GB đĩa
PUBKEY="${PUBKEY:-$HOME/.ssh/id_ed25519.pub}"
HERE="$(cd "$(dirname "$0")" && pwd)"

step() { printf '\n==> %s\n' "$*"; }
exists() { openstack "$@" >/dev/null 2>&1; }

step "1. Project ${PROJECT} và gán quyền admin hiện tại vào project"
openstack project create --or-show --description "BTL phong tro" "$PROJECT" >/dev/null
openstack role add --project "$PROJECT" --user admin admin 2>/dev/null || true
export OS_PROJECT_NAME="$PROJECT"                  # từ đây mọi tài nguyên tạo trong project này

step "2. Image ${IMAGE_NAME}"
if ! exists image show "$IMAGE_NAME"; then
  [[ -f "/tmp/${IMAGE_FILE}" ]] || wget -q -O "/tmp/${IMAGE_FILE}" "$IMAGE_URL"
  openstack image create --disk-format qcow2 --container-format bare \
    --file "/tmp/${IMAGE_FILE}" "$IMAGE_NAME" >/dev/null
fi

step "3. Flavor ${FLAVOR} (cần quyền admin)"
exists flavor show "$FLAVOR" || openstack flavor create --vcpus 2 --ram 3072 --disk 20 "$FLAVOR" >/dev/null

step "4. Mạng riêng, subnet, router ra ${EXT_NET}"
exists network show net-phongtro || openstack network create net-phongtro >/dev/null
exists subnet show subnet-phongtro || openstack subnet create --network net-phongtro \
  --subnet-range "$SUBNET_RANGE" --dns-nameserver 8.8.8.8 subnet-phongtro >/dev/null
if ! exists router show r-phongtro; then
  openstack router create r-phongtro >/dev/null
  openstack router set --external-gateway "$EXT_NET" r-phongtro
  openstack router add subnet r-phongtro subnet-phongtro
fi

step "5. Security group: sg-app (web) và sg-data (CSDL, MinIO chỉ nhận từ sg-app)"
if ! exists security group show sg-app; then
  openstack security group create sg-app --description "web: 80/443 mo, 22 tu ADMIN_CIDR" >/dev/null
  openstack security group rule create --proto tcp --dst-port 80  --remote-ip 0.0.0.0/0 sg-app >/dev/null
  openstack security group rule create --proto tcp --dst-port 443 --remote-ip 0.0.0.0/0 sg-app >/dev/null
  openstack security group rule create --proto tcp --dst-port 22  --remote-ip "$ADMIN_CIDR" sg-app >/dev/null
  openstack security group rule create --proto icmp --remote-ip "$ADMIN_CIDR" sg-app >/dev/null
fi
if ! exists security group show sg-data; then
  openstack security group create sg-data --description "data: 5432/9000 chi tu sg-app" >/dev/null
  openstack security group rule create --proto tcp --dst-port 5432 --remote-group sg-app sg-data >/dev/null
  openstack security group rule create --proto tcp --dst-port 9000 --remote-group sg-app sg-data >/dev/null
  openstack security group rule create --proto tcp --dst-port 22   --remote-group sg-app sg-data >/dev/null
fi

step "6. Keypair kp-phongtro từ ${PUBKEY}"
exists keypair show kp-phongtro || openstack keypair create --public-key "$PUBKEY" kp-phongtro >/dev/null

step "7. Máy ảo vm-app và vm-data (cài Docker qua cloud-init)"
for vm in vm-app vm-data; do
  sg="sg-app"; [[ "$vm" == "vm-data" ]] && sg="sg-data"
  exists server show "$vm" || openstack server create --flavor "$FLAVOR" --image "$IMAGE_NAME" \
    --network net-phongtro --security-group "$sg" --key-name kp-phongtro \
    --user-data "$HERE/cloud-init.yaml" --wait "$vm" >/dev/null
done

step "8. Volume 20 GB cho CSDL và MinIO, gắn vào vm-data"
exists volume show vol-data || openstack volume create --size 20 vol-data >/dev/null
if [[ "$(openstack volume show vol-data -f value -c status)" == "available" ]]; then
  openstack server add volume vm-data vol-data
fi

step "9. Floating IP cho vm-app"
# addresses có dạng "net-phongtro=10.20.0.5" hoặc, khi đã có floating IP, "net-phongtro=10.20.0.5, 172.24.4.10"
if [[ "$(openstack server show vm-app -f value -c addresses)" != *,* ]]; then
  fip="$(openstack floating ip create "$EXT_NET" -f value -c floating_ip_address)"
  openstack server add floating ip vm-app "$fip"
fi

step "Xong. Tóm tắt:"
openstack server list -c Name -c Status -c Networks
openstack volume list -c Name -c Status -c Size

cat <<'EOF'

Việc tiếp theo (làm tay, ghi lại trong docs/ cho báo cáo):
  a) SSH vào vm-app:   ssh ubuntu@<floating-ip>
     SSH vào vm-data:  ssh -J ubuntu@<floating-ip> ubuntu@<ip-noi-bo-vm-data>
  b) Trên vm-data, định dạng và gắn volume (CHỈ LẦN ĐẦU, kiểm tra tên đĩa bằng lsblk):
       sudo mkfs.ext4 /dev/vdb && sudo mkdir -p /srv/data && echo '/dev/vdb /srv/data ext4 defaults,nofail 0 2' | sudo tee -a /etc/fstab && sudo mount -a
  c) Snapshot volume định kỳ (chạy trên host):
       openstack volume snapshot create --volume vol-data --force "snap-vol-data-$(date +%Y%m%d)"
  d) Floating IP của DevStack mặc định chỉ thấy từ máy host. Để cả nhóm truy cập,
     cài Tailscale trên host (hoặc dùng Cloudflare Tunnel) theo SPEC.md mục 13.
EOF
