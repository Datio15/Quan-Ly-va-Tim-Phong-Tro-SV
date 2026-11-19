import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, apiAll, errorMessage } from "../../api/client";
import type { LandlordRoom, Paged, Tenant } from "../../api/types";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Loading, Modal, PageTitle, Pagination, Select } from "../../components/ui";
import { date, todayVN, vnd } from "../../lib/format";

/** Khách thuê, hợp đồng (file GIẢ), kết thúc thuê (F16). */
export default function TenantsPage() {
  const qc = useQueryClient();
  const [active, setActive] = useState("true");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Tenant | "new" | null>(null);
  const q = useQuery({
    queryKey: ["tenants", active, page],
    queryFn: () => api<Paged<Tenant>>("/landlord/tenants", { query: { active: active || undefined, page } }),
  });
  const end = useMutation({
    mutationFn: (t: Tenant) => {
      // FE-11: ngày theo giờ Việt Nam; kết thúc sớm thì ngày kết thúc là hôm nay (không giữ ngày hợp đồng ở tương lai).
      const today = todayVN();
      let endDate = t.end_date && t.end_date < today ? t.end_date : today;
      if (endDate < t.start_date) endDate = t.start_date;
      return api(`/landlord/tenants/${t.id}`, { method: "PATCH", body: { is_active: false, end_date: endDate } });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tenants"] }),
    onError: (e) => alert(errorMessage(e)),
  });
  const openFile = async (t: Tenant, kind: "id_card" | "contract") => {
    try {
      const res = await api<{ url: string }>(`/landlord/tenants/${t.id}/files/${kind}`);
      window.open(res.url, "_blank", "noopener");
    } catch (e) {
      alert(errorMessage(e));
    }
  };

  const today = todayVN();
  const expired = (d: string | null) => !!d && d < today;
  const soon = (d: string | null) => !!d && !expired(d) && new Date(d).getTime() - Date.now() < 30 * 86400_000;

  return (
    <div>
      <PageTitle actions={<Button onClick={() => setEditing("new")}>+ Thêm khách thuê</Button>}>Khách thuê</PageTitle>
      <Select value={active} onChange={(e) => { setActive(e.target.value); setPage(1); }} className="mb-4 !w-auto">
        <option value="true">Đang thuê</option>
        <option value="false">Đã kết thúc</option>
        <option value="">Tất cả</option>
      </Select>
      <ErrorBox error={q.error} />
      {q.isLoading && <Loading />}
      {q.data?.items.length === 0 && <Empty>Chưa có khách thuê.</Empty>}
      <div className="grid gap-3 md:grid-cols-2">
        {q.data?.items.map((t) => (
          <Card key={t.id}>
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="font-semibold">{t.full_name}</div>
                <div className="text-sm text-slate-500">{t.room_title}</div>
              </div>
              {t.is_active ? (expired(t.end_date) ? <Badge tone="red">Quá hạn hợp đồng</Badge> : soon(t.end_date) ? <Badge tone="amber">Sắp hết hạn</Badge> : <Badge tone="green">Đang thuê</Badge>) : <Badge>Đã kết thúc</Badge>}
            </div>
            <div className="mt-2 grid grid-cols-2 gap-1 text-sm text-slate-600">
              <span>📞 {t.phone || "–"}</span>
              <span>👥 {t.people_count} người · 🛵 {t.vehicle_count} xe</span>
              <span>📅 {date(t.start_date)} → {date(t.end_date)}</span>
              <span>💰 Cọc {vnd(t.deposit_amount)}</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-sm">
              <Button variant="secondary" onClick={() => setEditing(t)}>Sửa</Button>
              {t.has_id_card && <Button variant="ghost" onClick={() => openFile(t, "id_card")}>CCCD</Button>}
              {t.has_contract && <Button variant="ghost" onClick={() => openFile(t, "contract")}>Hợp đồng</Button>}
              {t.is_active && <Button variant="ghost" onClick={() => confirm(`Kết thúc thuê cho ${t.full_name}?`) && end.mutate(t)}>Kết thúc thuê</Button>}
            </div>
          </Card>
        ))}
      </div>
      {q.data && <Pagination page={q.data.page} pageSize={q.data.page_size} total={q.data.total} onChange={setPage} />}
      {editing && <TenantModal tenant={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function TenantModal({ tenant, onClose }: { tenant: Tenant | null; onClose: () => void }) {
  const qc = useQueryClient();
  const rooms = useQuery({ queryKey: ["landlord-rooms", "all"], queryFn: () => apiAll<LandlordRoom>("/landlord/rooms") });
  const [f, setF] = useState({
    room_id: tenant?.room_id || "", full_name: tenant?.full_name || "", phone: tenant?.phone || "", email: tenant?.email || "",
    start_date: tenant?.start_date || todayVN(), end_date: tenant?.end_date || "",
    deposit_amount: String(tenant?.deposit_amount ?? 0), people_count: String(tenant?.people_count ?? 1), vehicle_count: String(tenant?.vehicle_count ?? 1),
  });
  const idCard = useRef<HTMLInputElement>(null);
  const contract = useRef<HTMLInputElement>(null);
  const set = (k: keyof typeof f, v: string) => setF({ ...f, [k]: v });
  // FE-04: khách đã được tạo ở lần bấm trước (rồi tải file lỗi) thì lần sau chỉ sửa, không tạo trùng.
  const [savedId, setSavedId] = useState<string | null>(tenant?.id ?? null);

  const m = useMutation({
    mutationFn: async () => {
      const body = {
        full_name: f.full_name, phone: f.phone || null, email: f.email || null, start_date: f.start_date, end_date: f.end_date || null,
        deposit_amount: Number(f.deposit_amount || 0), people_count: Number(f.people_count || 1), vehicle_count: Number(f.vehicle_count || 0),
      };
      const saved = savedId
        ? await api<Tenant>(`/landlord/tenants/${savedId}`, { method: "PATCH", body })
        : await api<Tenant>("/landlord/tenants", { body: { ...body, room_id: f.room_id } });
      setSavedId(saved.id);
      qc.invalidateQueries({ queryKey: ["tenants"] });
      for (const [kind, ref] of [["id_card", idCard], ["contract", contract]] as const) {
        const file = ref.current?.files?.[0];
        if (file) {
          const form = new FormData();
          form.append("kind", kind);
          form.append("file", file);
          try {
            await api(`/landlord/tenants/${saved.id}/files`, { form });
            if (ref.current) ref.current.value = "";
          } catch (e) {
            if (ref.current) ref.current.value = ""; // bỏ file lỗi để lần Lưu sau không tải lại đúng file đó
            throw new Error(`Đã lưu thông tin khách thuê, nhưng tải ${kind === "id_card" ? "ảnh CCCD" : "hợp đồng"} lỗi: ${errorMessage(e)}. Chọn lại file rồi bấm Lưu.`);
          }
        }
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenants"] });
      onClose();
    },
  });

  return (
    <Modal open title={tenant ? "Sửa khách thuê" : "Thêm khách thuê"} onClose={onClose}>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
        {!savedId && (
          <Field label="Phòng">
            <Select required value={f.room_id} onChange={(e) => set("room_id", e.target.value)}>
              <option value="">— Chọn phòng —</option>
              {rooms.data?.map((r) => <option key={r.id} value={r.id}>{r.house_name} · {r.title}</option>)}
            </Select>
          </Field>
        )}
        <Field label="Họ tên"><Input required minLength={2} value={f.full_name} onChange={(e) => set("full_name", e.target.value)} /></Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Số điện thoại"><Input pattern="\+?[0-9]{9,12}" value={f.phone} onChange={(e) => set("phone", e.target.value)} /></Field>
          <Field label="Email"><Input type="email" value={f.email} onChange={(e) => set("email", e.target.value)} /></Field>
          <Field label="Ngày bắt đầu"><Input type="date" required value={f.start_date} onChange={(e) => set("start_date", e.target.value)} /></Field>
          <Field label="Ngày kết thúc"><Input type="date" value={f.end_date} onChange={(e) => set("end_date", e.target.value)} /></Field>
          <Field label="Tiền cọc"><Input type="number" min={0} max={1000000000} step={1000} value={f.deposit_amount} onChange={(e) => set("deposit_amount", e.target.value)} /></Field>
          <Field label="Số người"><Input type="number" min={1} max={20} value={f.people_count} onChange={(e) => set("people_count", e.target.value)} /></Field>
          <Field label="Số xe"><Input type="number" min={0} max={20} value={f.vehicle_count} onChange={(e) => set("vehicle_count", e.target.value)} /></Field>
        </div>
        <Field label="Ảnh CCCD (GIẢ – chỉ dùng file mẫu)" hint="JPEG/PNG/PDF ≤ 10 MB, lưu ở MinIO bucket private">
          <input ref={idCard} type="file" accept="image/jpeg,image/png,application/pdf" className="text-sm" />
        </Field>
        <Field label="Hợp đồng (GIẢ)"><input ref={contract} type="file" accept="image/jpeg,image/png,application/pdf" className="text-sm" /></Field>
        <ErrorBox error={m.error} />
        <Button type="submit" className="w-full" loading={m.isPending}>Lưu</Button>
      </form>
    </Modal>
  );
}
