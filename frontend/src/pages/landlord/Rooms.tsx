import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { House, LandlordRoom, Paged } from "../../api/types";
import { RoomThumb } from "../../components/RoomCard";
import { Badge, Button, Empty, ErrorBox, Loading, PageTitle, Pagination, STATUS_TONE } from "../../components/ui";
import { ROOM_STATUS_LABEL, dateTime, vnd } from "../../lib/format";
import * as RadixSelect from "@radix-ui/react-select";

type FilterOption = {
  value: string;
  label: string;
};

function RoomFilterSelect({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (value: string) => void;
  options: FilterOption[];
}) {
  return (
    <RadixSelect.Root
      value={value || "__all__"}
      onValueChange={(v) => onChange(v === "__all__" ? "" : v)}
    >
      <RadixSelect.Trigger
        className="
          inline-flex h-11 min-w-[150px] max-w-full
          items-center justify-between gap-3
          rounded-xl border border-slate-200
          bg-white px-3 text-sm text-slate-700
          outline-none transition
          hover:border-slate-300
          focus:ring-2 focus:ring-teal-500
          data-[state=open]:border-teal-500
        "
      >
        <RadixSelect.Value />
        <RadixSelect.Icon className="shrink-0 text-slate-500">
          ▾
        </RadixSelect.Icon>
      </RadixSelect.Trigger>

      <RadixSelect.Portal>
        <RadixSelect.Content
          position="popper"
          align="start"
          sideOffset={4}
          className="
            z-[100] min-w-[var(--radix-select-trigger-width)]
            max-w-[calc(100vw-24px)]
            overflow-hidden rounded-xl
            border border-slate-200 bg-white
            p-1 shadow-xl
          "
        >
          <RadixSelect.Viewport className="max-h-64">
            {options.map((option) => (
              <RadixSelect.Item
                key={option.value}
                value={option.value || "__all__"}
                className="
                  relative flex min-h-10 cursor-pointer
                  items-center rounded-lg
                  py-2 pl-3 pr-9 text-sm text-slate-700
                  outline-none
                  data-[highlighted]:bg-teal-50
                  data-[highlighted]:text-teal-800
                "
              >
                <RadixSelect.ItemText>
                  {option.label}
                </RadixSelect.ItemText>

                <RadixSelect.ItemIndicator
                  className="
                    absolute right-3
                    font-bold text-emerald-600
                  "
                >
                  ✓
                </RadixSelect.ItemIndicator>
              </RadixSelect.Item>
            ))}
          </RadixSelect.Viewport>
        </RadixSelect.Content>
      </RadixSelect.Portal>
    </RadixSelect.Root>
  );
}

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
        <RoomFilterSelect
          value={houseId}
          onChange={(v) => setParam("house_id", v)}
          options={[
            { value: "", label: "Tất cả nhà" },
            ...(houses.data ?? []).map((h) => ({
              value: String(h.id),
              label: h.name,
            })),
          ]}
        />

        <RoomFilterSelect
          value={status}
          onChange={(v) => setParam("status", v)}
          options={[
            { value: "", label: "Mọi trạng thái" },
            ...Object.entries(ROOM_STATUS_LABEL).map(([k, v]) => ({
              value: k,
              label: v,
            })),
          ]}
        />
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
              <div className="flex flex-wrap items-start justify-between gap-2">
                <span className="min-w-[10rem] flex-1 break-words font-semibold leading-snug">
                  {r.title}
                </span>

                <span className="inline-flex shrink-0 whitespace-nowrap [&>*]:whitespace-nowrap">
                  <Badge tone={STATUS_TONE[r.status]}>
                    {ROOM_STATUS_LABEL[r.status]}
                  </Badge>
                </span>
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
