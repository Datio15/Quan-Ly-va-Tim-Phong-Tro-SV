import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "../../api/client";
import type { House } from "../../api/types";
import MapPicker from "../../components/MapPicker";
import { Button, Card, Empty, ErrorBox, Field, Input, Loading, Modal, PageTitle } from "../../components/ui";

type HouseForm = Omit<House, "id" | "room_count">;
const EMPTY: HouseForm = { name: "", address_private: "", street: "", ward: "", area: "", city: "Hà Nội", lat: null, lng: null };

export default function HousesPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["houses"], queryFn: () => api<House[]>("/landlord/houses") });
  const [editing, setEditing] = useState<House | null>(null);
  const [creating, setCreating] = useState(false);
  const del = useMutation({
    mutationFn: (id: string) => api(`/landlord/houses/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["houses"] }),
    onError: (e) => alert(errorMessage(e)),
  });

  return (
    <div>
      <PageTitle actions={<Button onClick={() => setCreating(true)}>+ Thêm nhà</Button>}>Nhà trọ của tôi</PageTitle>
      <ErrorBox error={q.error} />
      {q.isLoading && <Loading />}
      {q.data?.length === 0 && <Empty>Chưa có nhà trọ. Thêm nhà trước, rồi tạo phòng trong nhà đó.</Empty>}
      <div className="grid gap-3 md:grid-cols-2">
        {q.data?.map((h) => (
          <Card key={h.id}>
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="font-semibold">{h.name}</div>
                <div className="text-sm text-slate-600">{h.address_private}</div>
                <div className="text-sm text-slate-500">{h.street}, {h.ward} · {h.area}, {h.city}</div>
                <div className="mt-1 text-xs text-slate-400">{h.lat !== null ? `📍 ${h.lat}, ${h.lng}` : "⚠️ Chưa có tọa độ"}</div>
              </div>
              <Link to={`/landlord/rooms?house_id=${h.id}`} className="shrink-0 text-sm text-brand-700 underline">{h.room_count} phòng</Link>
            </div>
            <div className="mt-3 flex gap-2">
              <Button variant="secondary" onClick={() => setEditing(h)}>Sửa</Button>
              <Button variant="ghost" onClick={() => confirm(`Xóa "${h.name}" và mọi phòng trong nhà?`) && del.mutate(h.id)}>Xóa</Button>
            </div>
          </Card>
        ))}
      </div>
      {(creating || editing) && (
        <HouseModal
          house={editing}
          onClose={() => { setCreating(false); setEditing(null); }}
        />
      )}
    </div>
  );
}

function HouseModal({ house, onClose }: { house: House | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [f, setF] = useState<HouseForm>(house ? { ...house } : EMPTY);
  const set = <K extends keyof HouseForm>(k: K, v: HouseForm[K]) => setF((p) => ({ ...p, [k]: v }));
  const m = useMutation({
    mutationFn: () => {
      const body = { name: f.name, address_private: f.address_private, street: f.street, ward: f.ward, area: f.area, city: f.city, lat: f.lat, lng: f.lng };
      return house ? api(`/landlord/houses/${house.id}`, { method: "PATCH", body }) : api("/landlord/houses", { body });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["houses"] });
      onClose();
    },
  });

  return (
    <Modal open title={house ? "Sửa nhà trọ" : "Thêm nhà trọ"} onClose={onClose}>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
        <Field label="Tên nhà"><Input required value={f.name} onChange={(e) => set("name", e.target.value)} placeholder="Nhà trọ Xuân Thủy" /></Field>
        <Field label="Số nhà, ngõ (riêng tư)" hint="Không hiển thị công khai, chỉ gửi cho sinh viên khi lịch xem được xác nhận.">
          <Input required value={f.address_private} onChange={(e) => set("address_private", e.target.value)} placeholder="Số 12 ngõ 34 Xuân Thủy" />
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Đường"><Input required value={f.street} onChange={(e) => set("street", e.target.value)} /></Field>
          <Field label="Phường/xã"><Input required value={f.ward} onChange={(e) => set("ward", e.target.value)} /></Field>
          <Field label="Khu vực quen gọi" hint="vd Cầu Giấy, Mai Dịch"><Input required value={f.area} onChange={(e) => set("area", e.target.value)} /></Field>
          <Field label="Tỉnh/thành"><Input required value={f.city} onChange={(e) => set("city", e.target.value)} /></Field>
        </div>
        <Field label="Vị trí trên bản đồ">
          <MapPicker lat={f.lat} lng={f.lng} address={[f.address_private, f.street, f.ward, f.city].filter(Boolean).join(", ")}
            onChange={(lat, lng) => setF((p) => ({ ...p, lat, lng }))} />
        </Field>
        <ErrorBox error={m.error} />
        <Button type="submit" className="w-full" loading={m.isPending}>Lưu</Button>
      </form>
    </Modal>
  );
}
