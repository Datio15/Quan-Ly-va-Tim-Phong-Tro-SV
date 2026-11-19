import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ApiError, api } from "../api/client";
import type { RoomCardData } from "../api/types";
import { RoomThumb } from "../components/RoomCard";
import { Empty, ErrorBox, Loading, Notice, PageTitle, Select, cx } from "../components/ui";
import { useAmenities, useSchools } from "../lib/catalog";
import { useCompare } from "../lib/compare";
import { distance, vnd } from "../lib/format";

type CompareRoom = Pick<RoomCardData, "id" | "title" | "price_month" | "est_monthly_cost" | "area_m2" | "distance_m" | "amenities" |
  "curfew" | "curfew_time" | "rating_avg" | "rating_count" | "landlord_verified" | "area" | "street" | "thumbnail_url"> & {
  deposit_amount: number;
  max_people: number;
};

interface CompareResult {
  rooms: CompareRoom[];
  missing?: string[];
  best: Record<string, string | null>;
}

/** So sánh 2-3 phòng cạnh nhau (F06). */
export default function ComparePage() {
  const compare = useCompare();
  const { data: schools } = useSchools();
  const { data: amenities } = useAmenities();
  const [schoolId, setSchoolId] = useState("");
  const ids = compare.items.map((i) => i.id);
  const [removedNote, setRemovedNote] = useState<string[]>([]);

  const q = useQuery({
    queryKey: ["compare", ids, schoolId],
    queryFn: () => api<CompareResult>("/rooms/compare", { body: { ids, school_id: schoolId || null } }),
    enabled: ids.length >= 2,
  });

  // FE-13: phòng không còn công khai (lưu trong trình duyệt từ trước) thì tự bỏ khỏi danh sách và báo rõ.
  const { remove } = compare;
  useEffect(() => {
    const fromError = q.error instanceof ApiError ? (q.error.details?.missing as string[] | undefined) : undefined;
    const missing = q.data?.missing?.length ? q.data.missing : fromError;
    if (missing?.length) {
      setRemovedNote(compare.items.filter((i) => missing.includes(i.id)).map((i) => i.title));
      remove(missing);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q.data, q.error, remove]);

  if (ids.length < 2) {
    return (
      <div>
        <PageTitle>So sánh phòng</PageTitle>
        {removedNote.length > 0 && <div className="mb-3"><Notice tone="warn">Đã bỏ khỏi so sánh vì không còn hiển thị: {removedNote.join(", ")}.</Notice></div>}
        <Empty>Chọn ít nhất 2 phòng (ô “So sánh” trên mỗi phòng) để so sánh. <Link to="/" className="text-brand-700 underline">Tìm phòng</Link></Empty>
      </div>
    );
  }

  const rooms = q.data?.rooms || [];
  const best = q.data?.best || {};
  // Hai phòng bằng nhau ở tiêu chí tốt nhất thì cùng được đánh dấu (API chỉ trả một id).
  const isBest = (key: string, r: CompareRoom) => {
    const winner = rooms.find((x) => x.id === best[key]);
    if (!winner) return false;
    const field = key as keyof CompareRoom;
    return winner.id === r.id || (winner[field] !== null && winner[field] === r[field]);
  };
  const rows: { key: string; label: string; render: (r: CompareRoom) => ReactNode }[] = [
    { key: "price_month", label: "Giá phòng", render: (r) => vnd(r.price_month) },
    { key: "est_monthly_cost", label: "Chi phí ước tính/tháng", render: (r) => vnd(r.est_monthly_cost) },
    { key: "deposit", label: "Đặt cọc", render: (r) => vnd(r.deposit_amount) },
    { key: "area_m2", label: "Diện tích", render: (r) => `${r.area_m2} m²` },
    { key: "max_people", label: "Số người tối đa", render: (r) => r.max_people },
    { key: "distance_m", label: "Khoảng cách tới trường", render: (r) => (schoolId ? distance(r.distance_m) || "–" : "Chọn trường") },
    { key: "curfew", label: "Giờ giấc", render: (r) => (r.curfew ? `Đóng cửa ${r.curfew_time}` : "Tự do") },
    { key: "rating_avg", label: "Đánh giá", render: (r) => (r.rating_avg !== null ? `★ ${r.rating_avg} (${r.rating_count})` : "–") },
    { key: "verified", label: "Chủ trọ xác minh", render: (r) => (r.landlord_verified ? "✓" : "–") },
    { key: "location", label: "Khu vực", render: (r) => `${r.street}, ${r.area}` },
  ];

  return (
    <div>
      <PageTitle actions={
        <Select value={schoolId} onChange={(e) => setSchoolId(e.target.value)} className="!w-auto">
          <option value="">Khoảng cách tới trường...</option>
          {schools?.map((s) => <option key={s.id} value={s.id}>{s.short_name}</option>)}
        </Select>
      }>So sánh phòng</PageTitle>
      {removedNote.length > 0 && <div className="mb-3"><Notice tone="warn">Đã bỏ khỏi so sánh vì không còn hiển thị: {removedNote.join(", ")}.</Notice></div>}
      <ErrorBox error={q.error} className="mb-4" />
      {q.isLoading ? <Loading /> : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr>
                <th className="w-44 p-3" />
                {rooms.map((r) => (
                  <th key={r.id} className="p-3 text-left align-top font-normal">
                    <Link to={`/rooms/${r.id}`} className="block">
                      <div className="mb-2 h-28 overflow-hidden rounded-lg"><RoomThumb url={r.thumbnail_url} title={r.title} /></div>
                      <span className="font-semibold text-slate-800 hover:text-brand-700">{r.title}</span>
                    </Link>
                    <button className="mt-1 text-xs text-slate-400 hover:text-rose-600" onClick={() => compare.toggle({ id: r.id, title: r.title })}>Bỏ khỏi so sánh</button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.key} className="border-t border-slate-100">
                  <td className="p-3 font-medium text-slate-600">{row.label}</td>
                  {rooms.map((r) => (
                    <td key={r.id} className={cx("p-3", isBest(row.key, r) && "bg-emerald-50 font-semibold text-emerald-700")}>
                      {row.render(r)} {isBest(row.key, r) && <span title="Tốt nhất">🏆</span>}
                    </td>
                  ))}
                </tr>
              ))}
              <tr className="border-t border-slate-100">
                <td className="p-3 font-medium text-slate-600">Tiện nghi</td>
                {rooms.map((r) => <td key={r.id} />)}
              </tr>
              {amenities?.map((a) => (
                <tr key={a.code} className="border-t border-slate-50">
                  <td className="px-3 py-1.5 pl-6 text-slate-500">{a.label}</td>
                  {rooms.map((r) => (
                    <td key={r.id} className="px-3 py-1.5">{r.amenities.includes(a.code) ? <span className="text-emerald-600">✓</span> : <span className="text-slate-300">–</span>}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
