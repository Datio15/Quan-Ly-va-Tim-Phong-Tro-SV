import { useEffect, useState, type ReactNode } from "react";
import type { Facet } from "../api/types";
import { useAmenities, useSchools } from "../lib/catalog";
import { Button, Input, Select, cx } from "./ui";

export interface Filters {
  q: string;
  price_min: string;
  price_max: string;
  cost_max: string;
  area_min: string;
  area: string[];
  amenities: string[];
  no_curfew: boolean;
  people: string;
  school_id: string;
  max_distance_m: string;
  verified_only: boolean;
  sort: string;
}

export const EMPTY_FILTERS: Filters = {
  q: "", price_min: "", price_max: "", cost_max: "", area_min: "", area: [], amenities: [], no_curfew: false,
  people: "", school_id: "", max_distance_m: "", verified_only: false, sort: "relevance",
};

// Khu vực quen gọi có trong dữ liệu mẫu; cộng thêm giá trị facet từ Azure khi có.
const KNOWN_AREAS = ["Cầu Giấy", "Dịch Vọng", "Mai Dịch", "Mỹ Đình", "Nghĩa Tân", "Cổ Nhuế"];

const PRICE_PRESETS = [
  { label: "Dưới 2,5 tr", max: "2500000" },
  { label: "2,5 - 3,5 tr", min: "2500000", max: "3500000" },
  { label: "Trên 3,5 tr", min: "3500000" },
];

export default function FilterPanel({
  value, onApply, facets, className,
}: { value: Filters; onApply: (f: Filters) => void; facets?: { area: Facet[]; amenities: Facet[] }; className?: string }) {
  const [f, setF] = useState<Filters>(value);
  const { data: amenities } = useAmenities();
  const { data: schools } = useSchools();
  useEffect(() => setF(value), [value]);

  const set = <K extends keyof Filters>(k: K, v: Filters[K]) => setF((prev) => ({ ...prev, [k]: v }));
  const toggleIn = (k: "area" | "amenities", v: string) =>
    setF((prev) => ({ ...prev, [k]: prev[k].includes(v) ? prev[k].filter((x) => x !== v) : [...prev[k], v] }));

  const areaCount = new Map((facets?.area || []).map((x) => [x.value, x.count]));
  const amenCount = new Map((facets?.amenities || []).map((x) => [x.value, x.count]));
  const areas = Array.from(new Set([...KNOWN_AREAS, ...(facets?.area || []).map((x) => x.value)]));

  return (
    <form
      className={cx("space-y-5", className)}
      onSubmit={(e) => {
        e.preventDefault();
        onApply(f);
      }}
    >
      <Section title="Trường học & khoảng cách">
        <Select value={f.school_id} onChange={(e) => set("school_id", e.target.value)}>
          <option value="">— Không chọn trường —</option>
          {schools?.map((s) => (
            <option key={s.id} value={s.id}>{s.short_name} – {s.name}</option>
          ))}
        </Select>
        {f.school_id && (
          <Select className="mt-2" value={f.max_distance_m} onChange={(e) => set("max_distance_m", e.target.value)}>
            <option value="">Mọi khoảng cách</option>
            <option value="1000">Trong 1 km</option>
            <option value="1500">Trong 1,5 km</option>
            <option value="2000">Trong 2 km</option>
            <option value="3000">Trong 3 km</option>
            <option value="5000">Trong 5 km</option>
          </Select>
        )}
      </Section>

      <Section title="Giá phòng (đ/tháng)">
        <div className="mb-2 flex flex-wrap gap-1">
          {PRICE_PRESETS.map((p) => (
            <button key={p.label} type="button" className="rounded-full border border-slate-300 px-2.5 py-1 text-xs hover:bg-slate-100"
              onClick={() => setF((prev) => ({ ...prev, price_min: p.min || "", price_max: p.max || "" }))}>
              {p.label}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Input type="number" min={0} step={100000} placeholder="Từ" value={f.price_min} onChange={(e) => set("price_min", e.target.value)} />
          <Input type="number" min={0} step={100000} placeholder="Đến" value={f.price_max} onChange={(e) => set("price_max", e.target.value)} />
        </div>
        <Input className="mt-2" type="number" min={0} step={100000} placeholder="Chi phí ước tính tối đa (gồm điện nước...)" value={f.cost_max} onChange={(e) => set("cost_max", e.target.value)} />
      </Section>

      <Section title="Diện tích & số người">
        <div className="grid grid-cols-2 gap-2">
          <Input type="number" min={0} placeholder="Từ (m²)" value={f.area_min} onChange={(e) => set("area_min", e.target.value)} />
          <Input type="number" min={1} max={20} placeholder="Số người" value={f.people} onChange={(e) => set("people", e.target.value)} />
        </div>
      </Section>

      <Section title="Khu vực">
        <div className="flex flex-wrap gap-1.5">
          {areas.map((a) => (
            <Chip key={a} active={f.area.includes(a)} onClick={() => toggleIn("area", a)}>
              {a}{areaCount.has(a) && <span className="ml-1 opacity-60">{areaCount.get(a)}</span>}
            </Chip>
          ))}
        </div>
      </Section>

      <Section title="Tiện nghi (phải có tất cả)">
        <div className="flex flex-wrap gap-1.5">
          {amenities?.map((a) => (
            <Chip key={a.code} active={f.amenities.includes(a.code)} onClick={() => toggleIn("amenities", a.code)}>
              {a.label}{amenCount.has(a.code) && <span className="ml-1 opacity-60">{amenCount.get(a.code)}</span>}
            </Chip>
          ))}
        </div>
      </Section>

      <Section title="Khác">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={f.no_curfew} onChange={(e) => set("no_curfew", e.target.checked)} /> Giờ giấc tự do
        </label>
        <label className="mt-1 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={f.verified_only} onChange={(e) => set("verified_only", e.target.checked)} /> Chỉ chủ trọ đã xác minh
        </label>
      </Section>

      <div className="flex gap-2">
        <Button type="submit" className="flex-1">Áp dụng</Button>
        <Button type="button" variant="secondary" onClick={() => onApply({ ...EMPTY_FILTERS, q: f.q, sort: f.sort })}>Xóa lọc</Button>
      </div>
    </form>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-2 text-sm font-semibold text-slate-700">{title}</div>
      {children}
    </div>
  );
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cx("rounded-full border px-2.5 py-1 text-xs transition",
        active ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100")}
    >
      {children}
    </button>
  );
}
