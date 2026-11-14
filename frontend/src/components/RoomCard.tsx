import { Link } from "react-router-dom";
import type { RoomCardData } from "../api/types";
import { useAmenityLabels } from "../lib/catalog";
import { useCompare } from "../lib/compare";
import { distance, vnd } from "../lib/format";
import { Badge, cx } from "./ui";

export function RoomThumb({ url, title, className }: { url: string | null; title: string; className?: string }) {
  return url ? (
    <img src={url} alt={title} loading="lazy" className={cx("h-full w-full object-cover", className)} />
  ) : (
    <div className={cx("flex h-full w-full items-center justify-center bg-gradient-to-br from-brand-50 via-white to-accent-50", className)}>
      <img src="/brand/easyrent-icon.png" alt="" className="h-1/3 max-h-16 w-auto opacity-40" />
    </div>
  );
}

export default function RoomCard({ room, highlighted, onHover }: { room: RoomCardData; highlighted?: boolean; onHover?: (id: string | null) => void }) {
  const label = useAmenityLabels();
  const compare = useCompare();
  const selected = compare.has(room.id);

  return (
    <div
      className={cx(
        "group flex flex-col overflow-hidden rounded-xl border bg-white shadow-sm transition hover:shadow-md sm:flex-row",
        highlighted ? "border-brand-500 ring-2 ring-brand-100" : "border-slate-200",
      )}
      onMouseEnter={() => onHover?.(room.id)}
      onMouseLeave={() => onHover?.(null)}
    >
      <Link to={`/rooms/${room.id}`} className="relative h-44 shrink-0 sm:h-auto sm:w-48">
        <RoomThumb url={room.thumbnail_url} title={room.title} />
        {room.landlord_verified && (
          <span className="absolute left-2 top-2 rounded-full bg-emerald-600/90 px-2 py-0.5 text-xs font-medium text-white">✓ Đã xác minh</span>
        )}
      </Link>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <Link to={`/rooms/${room.id}`} className="font-semibold leading-snug text-slate-800 group-hover:text-brand-700">
          {room.title}
        </Link>
        <div className="text-sm text-slate-500">
          {room.street}, {room.ward} · {room.area}
          {room.distance_m !== null && room.distance_m !== undefined && <span className="ml-1 font-medium text-brand-700">· cách trường {distance(room.distance_m)}</span>}
        </div>
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <span className="text-lg font-bold text-accent-600">{vnd(room.price_month)}<span className="text-sm font-normal text-slate-500">/tháng</span></span>
          <span className="text-sm text-slate-600">Ước tính <b>{vnd(room.est_monthly_cost)}</b></span>
          <span className="text-sm text-slate-600">{room.area_m2} m²</span>
        </div>
        <div className="flex flex-wrap gap-1">
          {room.amenities.slice(0, 5).map((a) => (
            <Badge key={a}>{label(a)}</Badge>
          ))}
          {room.amenities.length > 5 && <Badge>+{room.amenities.length - 5}</Badge>}
          {!room.curfew ? <Badge tone="green">Giờ giấc tự do</Badge> : room.curfew_time && <Badge tone="amber">Đóng cửa {room.curfew_time}</Badge>}
        </div>
        <div className="mt-auto flex items-center justify-between pt-1 text-sm">
          <span className="text-slate-500">
            {room.rating_avg !== null ? <>★ {room.rating_avg} <span className="text-slate-400">({room.rating_count})</span></> : "Chưa có đánh giá"}
          </span>
          <label className="flex cursor-pointer items-center gap-1.5 text-slate-600">
            <input
              type="checkbox"
              checked={selected}
              onChange={() => {
                if (!compare.toggle({ id: room.id, title: room.title })) alert("Chỉ so sánh tối đa 3 phòng");
              }}
            />
            So sánh
          </label>
        </div>
      </div>
    </div>
  );
}
