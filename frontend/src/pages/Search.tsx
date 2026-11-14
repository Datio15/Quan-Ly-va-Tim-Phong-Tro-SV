import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiRaw } from "../api/client";
import type { SearchResult } from "../api/types";
import FilterPanel, { type Filters } from "../components/FilterPanel";
import MapView from "../components/MapView";
import RoomCard from "../components/RoomCard";
import { Badge, Button, Empty, ErrorBox, Input, Loading, Pagination, Select, cx } from "../components/ui";
import { useSchools } from "../lib/catalog";

function readFilters(sp: URLSearchParams): Filters {
  return {
    q: sp.get("q") || "",
    price_min: sp.get("price_min") || "",
    price_max: sp.get("price_max") || "",
    cost_max: sp.get("cost_max") || "",
    area_min: sp.get("area_min") || "",
    area: sp.getAll("area"),
    amenities: sp.getAll("amenities"),
    no_curfew: sp.get("no_curfew") === "true",
    people: sp.get("people") || "",
    school_id: sp.get("school_id") || "",
    max_distance_m: sp.get("max_distance_m") || "",
    verified_only: sp.get("verified_only") === "true",
    sort: sp.get("sort") || "relevance",
  };
}

function writeFilters(f: Filters, page = 1): URLSearchParams {
  const sp = new URLSearchParams();
  Object.entries(f).forEach(([k, v]) => {
    if (Array.isArray(v)) v.forEach((x) => sp.append(k, x));
    else if (v === true) sp.set(k, "true");
    else if (v && v !== "relevance") sp.set(k, String(v));
  });
  if (!f.school_id) {
    sp.delete("max_distance_m");
    if (f.sort === "distance_asc") sp.delete("sort");
  }
  if (page > 1) sp.set("page", String(page));
  return sp;
}

const SORTS = [
  { v: "relevance", label: "Phù hợp nhất" },
  { v: "price_asc", label: "Giá tăng dần" },
  { v: "price_desc", label: "Giá giảm dần" },
  { v: "cost_asc", label: "Chi phí thực tế thấp" },
  { v: "distance_asc", label: "Gần trường nhất" },
  { v: "rating_desc", label: "Đánh giá cao" },
  { v: "newest", label: "Mới nhất" },
];

export default function SearchPage() {
  const [sp, setSp] = useSearchParams();
  const filters = useMemo(() => readFilters(sp), [sp]);
  const [q, setQ] = useState(filters.q);
  const [showFilters, setShowFilters] = useState(false);
  const [view, setView] = useState<"list" | "map">("list");
  const [hovered, setHovered] = useState<string | null>(null);
  const { data: schools } = useSchools();
  const school = schools?.find((s) => s.id === filters.school_id) || null;

  const query = useQuery({
    queryKey: ["search", sp.toString()],
    queryFn: async () => {
      const qs = new URLSearchParams(sp);
      qs.set("page_size", "20");
      const res = await apiRaw(`/search/rooms?${qs.toString()}`);
      return { data: (await res.json()) as SearchResult, source: res.headers.get("X-Search-Source") || "?" };
    },
    placeholderData: keepPreviousData,
  });

  const apply = (f: Filters, p = 1) => {
    setSp(writeFilters(f, p));
    setShowFilters(false);
  };
  const activeCount =
    [filters.price_min, filters.price_max, filters.cost_max, filters.area_min, filters.people, filters.school_id].filter(Boolean).length +
    filters.area.length + filters.amenities.length + (filters.no_curfew ? 1 : 0) + (filters.verified_only ? 1 : 0);

  const result = query.data?.data;

  return (
    <div>
      <div className="relative mb-5 overflow-hidden rounded-2xl bg-gradient-to-r from-brand-800 via-brand-700 to-brand-600 p-5 text-white sm:p-7">
        <img src="/brand/easyrent-icon.png" alt="" className="pointer-events-none absolute -right-6 -top-4 hidden h-48 w-auto opacity-10 sm:block" />
        <p className="text-sm font-medium text-accent-200">EasyRent · Quản lý phòng trọ dễ dàng</p>
        <h1 className="mt-1 text-xl font-bold sm:text-2xl">Tìm phòng trọ gần trường, biết rõ chi phí mỗi tháng</h1>
        <form
          className="mt-4 flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            apply({ ...filters, q });
          }}
        >
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Từ khóa: gác lửng, Xuân Thủy, Cầu Giấy..." className="!border-0 !py-2.5 text-slate-800" />
          <Select
            value={filters.school_id}
            onChange={(e) => apply({ ...filters, q, school_id: e.target.value, sort: e.target.value ? "distance_asc" : "relevance" })}
            className="!border-0 !py-2.5 text-slate-800 sm:max-w-xs"
          >
            <option value="">Gần trường...</option>
            {schools?.map((s) => <option key={s.id} value={s.id}>{s.short_name}</option>)}
          </Select>
          <Button type="submit" className="!bg-accent-500 hover:!bg-accent-600 sm:px-6">Tìm</Button>
        </form>
      </div>

      <div className="flex gap-6">
        <aside className="hidden w-72 shrink-0 lg:block">
          <div className="sticky top-20 max-h-[calc(100vh-6rem)] overflow-y-auto rounded-xl border border-slate-200 bg-white p-4">
            <FilterPanel value={filters} onApply={(f) => apply({ ...f, q })} facets={result?.facets} />
          </div>
        </aside>

        <section className="min-w-0 flex-1">
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <Button variant="secondary" className="lg:hidden" onClick={() => setShowFilters(true)}>
              Bộ lọc {activeCount > 0 && <Badge tone="blue">{activeCount}</Badge>}
            </Button>
            <span className="text-sm text-slate-600">
              {result ? <><b>{result.total}</b> phòng</> : "…"}
              {query.data && (
                <span className="ml-2" title="Nguồn kết quả tìm kiếm">
                  <Badge tone={query.data.source === "azure" ? "blue" : "amber"}>
                    {query.data.source === "azure" ? "Azure AI Search" : "Dự phòng CSDL"}
                  </Badge>
                </span>
              )}
            </span>
            <div className="ml-auto flex items-center gap-2">
              <Select value={filters.sort} onChange={(e) => apply({ ...filters, sort: e.target.value })} className="!w-auto">
                {SORTS.filter((s) => s.v !== "distance_asc" || filters.school_id).map((s) => (
                  <option key={s.v} value={s.v}>{s.label}</option>
                ))}
              </Select>
              <div className="flex overflow-hidden rounded-lg border border-slate-300 text-sm xl:hidden">
                {(["list", "map"] as const).map((v) => (
                  <button key={v} className={cx("px-3 py-2", view === v ? "bg-brand-600 text-white" : "bg-white")} onClick={() => setView(v)}>
                    {v === "list" ? "Danh sách" : "Bản đồ"}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <ErrorBox error={query.error} className="mb-4" />
          {query.isLoading && <Loading />}

          {result && (
            <div className="flex gap-4">
              <div className={cx("min-w-0 flex-1 space-y-3", view === "map" && "hidden xl:block")}>
                {result.items.length === 0 ? (
                  <Empty>Không có phòng phù hợp. Thử nới bộ lọc nhé.</Empty>
                ) : (
                  result.items.map((r) => <RoomCard key={r.id} room={r} highlighted={hovered === r.id} onHover={setHovered} />)
                )}
                <Pagination page={result.page} pageSize={result.page_size} total={result.total} onChange={(p) => apply(filters, p)} />
              </div>
              <div className={cx("xl:block xl:w-[42%]", view === "map" ? "block w-full" : "hidden")}>
                <MapView
                  rooms={result.items}
                  school={school}
                  radiusM={filters.max_distance_m ? Number(filters.max_distance_m) : null}
                  highlightedId={hovered}
                  className="sticky top-20 h-[70vh]"
                />
              </div>
            </div>
          )}
        </section>
      </div>

      {showFilters && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 lg:hidden" onClick={() => setShowFilters(false)}>
          <div className="absolute inset-y-0 right-0 w-full max-w-sm overflow-y-auto bg-white p-5" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Bộ lọc</h2>
              <button onClick={() => setShowFilters(false)} className="p-1 text-slate-500">✕</button>
            </div>
            <FilterPanel value={filters} onApply={(f) => apply({ ...f, q })} facets={result?.facets} />
          </div>
        </div>
      )}
    </div>
  );
}

