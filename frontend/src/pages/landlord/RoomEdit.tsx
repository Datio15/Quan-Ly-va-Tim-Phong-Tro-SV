import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "../../api/client";
import type { CostRates, House, LandlordRoomFull } from "../../api/types";
import { Badge, Button, Card, ErrorBox, Field, Input, Loading, Notice, PageTitle, STATUS_TONE, Select, Textarea, cx } from "../../components/ui";
import { useAmenities } from "../../lib/catalog";
import { ROOM_STATUS_LABEL, vnd } from "../../lib/format";

interface RoomForm {
  house_id: string;
  title: string;
  description: string;
  price_month: string;
  deposit_amount: string;
  area_m2: string;
  floor: string;
  max_people: string;
  curfew_time: string;
  available_from: string;
  amenities: string[];
  cost_rates: CostRates;
}

const EMPTY_RATES: CostRates = {
  electricity_per_kwh: 3500, water_mode: "per_m3", water_per_m3: 25000, water_per_person: 100000,
  internet_per_month: 50000, parking_per_vehicle: 100000, service_per_month: 30000,
};

function toForm(r: LandlordRoomFull): RoomForm {
  return {
    house_id: r.house_id, title: r.title, description: r.description, price_month: String(r.price_month),
    deposit_amount: String(r.deposit_amount), area_m2: String(r.area_m2), floor: r.floor === null ? "" : String(r.floor),
    max_people: String(r.max_people), curfew_time: r.curfew_time || "", available_from: r.available_from || "",
    amenities: r.amenities, cost_rates: r.cost_rates,
  };
}

function toBody(f: RoomForm) {
  return {
    house_id: f.house_id, title: f.title.trim(), description: f.description, price_month: Number(f.price_month),
    deposit_amount: Number(f.deposit_amount || 0), area_m2: Number(f.area_m2), floor: f.floor === "" ? null : Number(f.floor),
    max_people: Number(f.max_people || 1), curfew_time: f.curfew_time || null, available_from: f.available_from || null,
    amenities: f.amenities, cost_rates: f.cost_rates,
  };
}

/** Tạo / sửa phòng, bảng giá dịch vụ, tiện nghi, ảnh, gửi duyệt, ẩn/hiện (F02, F03). */
export default function RoomEditPage() {
  const { id } = useParams();
  const isNew = !id || id === "new";
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: amenities } = useAmenities();
  const houses = useQuery({ queryKey: ["houses"], queryFn: () => api<House[]>("/landlord/houses") });
  const room = useQuery({
    queryKey: ["landlord-room", id],
    queryFn: () => api<LandlordRoomFull>(`/landlord/rooms/${id}`),
    enabled: !isNew,
  });
  const [f, setF] = useState<RoomForm | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (isNew && houses.data && !f) {
      setF({
        house_id: houses.data[0]?.id || "", title: "", description: "", price_month: "", deposit_amount: "", area_m2: "",
        floor: "", max_people: "2", curfew_time: "", available_from: "", amenities: [], cost_rates: EMPTY_RATES,
      });
    }
  }, [isNew, houses.data, f]);
  useEffect(() => {
    if (room.data) setF(toForm(room.data));
  }, [room.data]);

  const save = useMutation({
    mutationFn: () =>
      isNew
        ? api<LandlordRoomFull>("/landlord/rooms", { body: toBody(f!) })
        : api<LandlordRoomFull>(`/landlord/rooms/${id}`, { method: "PATCH", body: toBody(f!) }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["landlord-rooms"] });
      qc.setQueryData(["landlord-room", r.id], r);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
      if (isNew) navigate(`/landlord/rooms/${r.id}`, { replace: true });
    },
  });
  const transition = useMutation({
    mutationFn: (action: string) => api<LandlordRoomFull>(`/landlord/rooms/${id}/${action}`, { method: "POST" }),
    onSuccess: (r) => {
      qc.setQueryData(["landlord-room", id], r);
      qc.invalidateQueries({ queryKey: ["landlord-rooms"] });
    },
    onError: (e) => alert(errorMessage(e)),
  });

  if ((!isNew && room.isLoading) || houses.isLoading) return <Loading />;
  if (room.error) return <ErrorBox error={room.error} />;
  if (isNew && houses.data?.length === 0) {
    return <Notice tone="warn">Bạn cần <Link className="underline" to="/landlord/houses">thêm nhà trọ</Link> trước khi đăng phòng.</Notice>;
  }
  if (!f) return <Loading />;

  const r = room.data;
  const set = <K extends keyof RoomForm>(k: K, v: RoomForm[K]) => setF({ ...f, [k]: v });
  const setRate = <K extends keyof CostRates>(k: K, v: CostRates[K]) => setF({ ...f, cost_rates: { ...f.cost_rates, [k]: v } });
  const toggleAmenity = (c: string) => set("amenities", f.amenities.includes(c) ? f.amenities.filter((x) => x !== c) : [...f.amenities, c]);

  return (
    <div className="space-y-5">
      <Link to="/landlord/rooms" className="text-sm text-slate-500 hover:text-brand-700">‹ Danh sách phòng</Link>
      <PageTitle
        actions={r && (
          <>
            {(r.status === "draft" || r.status === "rejected") && <Button loading={transition.isPending} onClick={() => transition.mutate("submit")}>Gửi duyệt</Button>}
            {r.status === "published" && <Button variant="secondary" loading={transition.isPending} onClick={() => transition.mutate("hide")}>Ẩn tin</Button>}
            {r.status === "hidden" && <Button variant="secondary" loading={transition.isPending} onClick={() => transition.mutate("unhide")}>Hiện lại</Button>}
            {r.status === "published" && <Link to={`/rooms/${r.id}`}><Button variant="ghost">Xem trang công khai ↗</Button></Link>}
          </>
        )}
      >
        {isNew ? "Đăng phòng mới" : "Sửa phòng"} {r && <Badge tone={STATUS_TONE[r.status]}>{ROOM_STATUS_LABEL[r.status]}</Badge>}
      </PageTitle>

      {r?.status === "rejected" && r.reject_reason && <Notice tone="warn">Bị từ chối: {r.reject_reason}. Sửa lại rồi gửi duyệt lại.</Notice>}
      {r?.status === "pending" && <Notice>Tin đang chờ quản trị viên duyệt.</Notice>}
      {r?.status === "published" && <Notice tone="success">Tin đang hiển thị. Mọi thay đổi được đồng bộ sang Azure AI Search trong vài giây (phiên bản v{r.version}).</Notice>}

      <form className="grid gap-5 lg:grid-cols-2" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
        <Card className="space-y-3">
          <h2 className="font-semibold">Thông tin phòng</h2>
          <Field label="Nhà trọ">
            <Select value={f.house_id} onChange={(e) => set("house_id", e.target.value)} required>
              {houses.data?.map((h) => <option key={h.id} value={h.id}>{h.name} – {h.street}</option>)}
            </Select>
          </Field>
          <Field label="Tiêu đề" hint="5-120 ký tự"><Input required minLength={5} maxLength={120} value={f.title} onChange={(e) => set("title", e.target.value)} placeholder="Phòng khép kín 20m² gần Xuân Thủy" /></Field>
          <Field label="Mô tả"><Textarea rows={4} value={f.description} onChange={(e) => set("description", e.target.value)} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Giá thuê (đ/tháng)"><Input type="number" required min={1} step={50000} value={f.price_month} onChange={(e) => set("price_month", e.target.value)} /></Field>
            <Field label="Đặt cọc (đ)"><Input type="number" min={0} step={50000} value={f.deposit_amount} onChange={(e) => set("deposit_amount", e.target.value)} /></Field>
            <Field label="Diện tích (m²)"><Input type="number" required min={1} step={0.1} value={f.area_m2} onChange={(e) => set("area_m2", e.target.value)} /></Field>
            <Field label="Tầng"><Input type="number" value={f.floor} onChange={(e) => set("floor", e.target.value)} /></Field>
            <Field label="Số người tối đa"><Input type="number" min={1} max={20} value={f.max_people} onChange={(e) => set("max_people", e.target.value)} /></Field>
            <Field label="Trống từ ngày"><Input type="date" value={f.available_from} onChange={(e) => set("available_from", e.target.value)} /></Field>
          </div>
          <Field label="Giờ đóng cửa" hint="Để trống nếu giờ giấc tự do">
            <div className="flex gap-2">
              <Input type="time" value={f.curfew_time} onChange={(e) => set("curfew_time", e.target.value)} />
              {f.curfew_time && <Button type="button" variant="ghost" onClick={() => set("curfew_time", "")}>Tự do</Button>}
            </div>
          </Field>
        </Card>

        <div className="space-y-5">
          <Card className="space-y-3">
            <h2 className="font-semibold">Bảng giá dịch vụ</h2>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Điện (đ/kWh)"><Input type="number" min={0} value={f.cost_rates.electricity_per_kwh} onChange={(e) => setRate("electricity_per_kwh", Number(e.target.value))} /></Field>
              <Field label="Cách tính nước">
                <Select value={f.cost_rates.water_mode} onChange={(e) => setRate("water_mode", e.target.value as CostRates["water_mode"])}>
                  <option value="per_m3">Theo m³</option>
                  <option value="per_person">Theo người</option>
                </Select>
              </Field>
              {f.cost_rates.water_mode === "per_m3" ? (
                <Field label="Nước (đ/m³)"><Input type="number" min={0} value={f.cost_rates.water_per_m3} onChange={(e) => setRate("water_per_m3", Number(e.target.value))} /></Field>
              ) : (
                <Field label="Nước (đ/người)"><Input type="number" min={0} value={f.cost_rates.water_per_person} onChange={(e) => setRate("water_per_person", Number(e.target.value))} /></Field>
              )}
              <Field label="Internet (đ/tháng)"><Input type="number" min={0} value={f.cost_rates.internet_per_month} onChange={(e) => setRate("internet_per_month", Number(e.target.value))} /></Field>
              <Field label="Gửi xe (đ/xe)"><Input type="number" min={0} value={f.cost_rates.parking_per_vehicle} onChange={(e) => setRate("parking_per_vehicle", Number(e.target.value))} /></Field>
              <Field label="Dịch vụ khác (đ/tháng)"><Input type="number" min={0} value={f.cost_rates.service_per_month} onChange={(e) => setRate("service_per_month", Number(e.target.value))} /></Field>
            </div>
          </Card>
          <Card>
            <h2 className="mb-3 font-semibold">Tiện nghi</h2>
            <div className="flex flex-wrap gap-1.5">
              {amenities?.map((a) => (
                <button type="button" key={a.code} onClick={() => toggleAmenity(a.code)}
                  className={cx("rounded-full border px-3 py-1 text-sm", f.amenities.includes(a.code) ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300 bg-white")}>
                  {a.label}
                </button>
              ))}
            </div>
          </Card>
          <div className="flex items-center gap-3">
            <Button type="submit" loading={save.isPending} className="px-6">{isNew ? "Tạo phòng (nháp)" : "Lưu thay đổi"}</Button>
            {saved && <span className="text-sm text-emerald-600">✓ Đã lưu</span>}
            {f.price_month && <span className="text-sm text-slate-500">Giá: {vnd(Number(f.price_month))}</span>}
          </div>
          <ErrorBox error={save.error} />
        </div>
      </form>

      {r && <ImagesCard room={r} />}
    </div>
  );
}

function ImagesCard({ room }: { room: LandlordRoomFull }) {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [err, setErr] = useState<unknown>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: ["landlord-room", room.id] });
  const upload = useMutation({
    mutationFn: async (files: FileList) => {
      for (const file of Array.from(files)) {
        const form = new FormData();
        form.append("file", file);
        await api(`/landlord/rooms/${room.id}/images`, { form });
      }
    },
    onSettled: refresh,
    onError: setErr,
    onMutate: () => setErr(null),
  });
  const del = useMutation({
    mutationFn: (imageId: string) => api(`/landlord/rooms/${room.id}/images/${imageId}`, { method: "DELETE" }),
    onSuccess: refresh,
    onError: setErr,
  });
  const MOD = { pending: ["amber", "Chờ duyệt"], ok: ["green", "Đã duyệt"], rejected: ["red", "Bị từ chối"] } as const;

  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">Ảnh phòng ({room.images.length}/10)</h2>
        <div>
          <input ref={input} type="file" accept="image/jpeg,image/png" multiple className="hidden"
            onChange={(e) => { if (e.target.files?.length) upload.mutate(e.target.files); e.target.value = ""; }} />
          <Button variant="secondary" loading={upload.isPending} disabled={room.images.length >= 10} onClick={() => input.current?.click()}>
            + Tải ảnh (JPEG/PNG ≤ 5 MB)
          </Button>
        </div>
      </div>
      <ErrorBox error={err} className="mb-3" />
      {room.images.length === 0 ? (
        <p className="text-sm text-slate-500">Chưa có ảnh. Ảnh mới sẽ được quản trị viên duyệt cùng tin đăng.</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {room.images.map((im) => (
            <div key={im.id} className="overflow-hidden rounded-lg border border-slate-200">
              <img src={im.url} alt="" className="h-28 w-full object-cover" />
              <div className="flex items-center justify-between p-2">
                <Badge tone={MOD[im.moderation][0]}>{MOD[im.moderation][1]}</Badge>
                <button className="text-xs text-rose-600" onClick={() => confirm("Xóa ảnh này?") && del.mutate(im.id)}>Xóa</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
