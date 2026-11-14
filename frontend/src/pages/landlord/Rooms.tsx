import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { House, LandlordRoom, Paged } from "../../api/types";
import { RoomThumb } from "../../components/RoomCard";
import { Badge, Button, Empty, ErrorBox, Loading, PageTitle, Pagination, STATUS_TONE, Select } from "../../components/ui";
import { ROOM_STATUS_LABEL, dateTime, vnd } from "../../lib/format";

export default function LandlordRoomsPage() {
  const [sp, setSp] = useSearchParams();
  const houseId = sp.get("house_id") || "";
  const status = sp.get("status") || "";
  const page = Number(sp.get("page") || 1);
  const houses = useQuery({ queryKey: ["houses"], queryFn: () => api<House[]>("/landlord/houses") });
  const q = useQuery({
    queryKey: ["landlord-rooms", houseId, status, page],
    queryFn: () => api<Paged<LandlordRoom>>("/landlord/rooms", { query: { house_id: houseId || undefined, status: status || undefined, page } }),
  });
  const setParam = (k: string, v: string) => {
    const next = new URLSearchParams(sp);
    if (v) next.set(k, v);
    else next.delete(k);
    if (k !== "page") next.delete("page");
    setSp(next);
  };

  return (
    <div>
      <PageTitle actions={<Link to="/landlord/rooms/new"><Button>+ Đăng phòng mới</Button></Link>}>Phòng của tôi</PageTitle>
      <div className="mb-4 flex flex-wrap gap-2">
        <Select value={houseId} onChange={(e) => setParam("house_id", e.target.value)} className="!w-auto">
          <option value="">Tất cả nhà</option>
          {houses.data?.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
        </Select>
        <Select value={status} onChange={(e) => setParam("status", e.target.value)} className="!w-auto">
          <option value="">Mọi trạng thái</option>
          {Object.entries(ROOM_STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
      </div>
      {houses.data?.length === 0 && (
        <Empty>Bạn cần <Link to="/landlord/houses" className="text-brand-700 underline">thêm nhà trọ</Link> trước khi đăng phòng.</Empty>
      )}
      <ErrorBox error={q.error} />
      {q.isLoading && <Loading />}
      {q.data && q.data.items.length === 0 && houses.data?.length !== 0 && <Empty>Chưa có phòng.</Empty>}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {q.data?.items.map((r) => (
          <Link key={r.id} to={`/landlord/rooms/${r.id}`} className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm hover:shadow-md">
            <div className="h-36"><RoomThumb url={r.thumbnail_url || null} title={r.title} /></div>
            <div className="space-y-1 p-4">
              <div className="flex items-start justify-between gap-2">
                <span className="font-semibold leading-snug">{r.title}</span>
                <Badge tone={STATUS_TONE[r.status]}>{ROOM_STATUS_LABEL[r.status]}</Badge>
              </div>
              <div className="text-sm text-slate-500">{r.house_name} · {r.area_m2} m² · {vnd(r.price_month)}</div>
              {r.status === "rejected" && r.reject_reason && <div className="text-xs text-rose-600">Lý do: {r.reject_reason}</div>}
              <div className="text-xs text-slate-400">Cập nhật {dateTime(r.updated_at)} · v{r.version}</div>
            </div>
          </Link>
        ))}
      </div>
      {q.data && <Pagination page={q.data.page} pageSize={q.data.page_size} total={q.data.total} onChange={(p) => setParam("page", String(p))} />}
    </div>
  );
}
