/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { RoomCardData, School } from "../api/types";
import { useConfig } from "../lib/catalog";
import { shortVnd, vnd } from "../lib/format";
import { HANOI_CENTER, loadAtlas } from "./azureMaps";
import { cx } from "./ui";

interface Props {
  rooms: RoomCardData[];
  school?: School | null;
  radiusM?: number | null;
  highlightedId?: string | null;
  className?: string;
}

/** Bản đồ các phòng (F05): ghim giá phòng, vòng tròn bán kính quanh trường. */
export default function MapView({ rooms, school, radiusM, highlightedId, className }: Props) {
  const { data: cfg } = useConfig();
  const el = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const layersRef = useRef<{ markers: any[]; circle: any; popup: any }>({ markers: [], circle: null, popup: null });
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const key = cfg?.maps_key;

  useEffect(() => {
    if (!key || !el.current) return;
    let disposed = false;
    loadAtlas()
      .then((atlas) => {
        if (disposed || !el.current) return;
        const map = new atlas.Map(el.current, {
          center: HANOI_CENTER,
          zoom: 13,
          language: "vi-VN",
          view: "Auto",
          authOptions: { authType: "subscriptionKey", subscriptionKey: key },
        });
        map.events.add("ready", () => {
          map.controls.add(new atlas.control.ZoomControl(), { position: "top-right" });
          const ds = new atlas.source.DataSource();
          map.sources.add(ds);
          map.layers.add(new atlas.layer.PolygonLayer(ds, undefined, { fillColor: "rgba(24,90,98,0.12)" }));
          map.layers.add(new atlas.layer.LineLayer(ds, undefined, { strokeColor: "#185a62", strokeWidth: 2 }));
          layersRef.current.circle = ds;
          layersRef.current.popup = new atlas.Popup({ pixelOffset: [0, -28], closeButton: false });
          mapRef.current = map;
          setReady(true);
        });
      })
      .catch((e) => setError(e.message));
    return () => {
      disposed = true;
      mapRef.current?.dispose();
      mapRef.current = null;
      setReady(false);
    };
  }, [key]);

  // Vẽ lại ghim khi danh sách phòng đổi
  useEffect(() => {
    const map = mapRef.current;
    const atlas = window.atlas;
    if (!ready || !map || !atlas) return;
    const st = layersRef.current;
    st.markers.forEach((m) => map.markers.remove(m));
    st.markers = [];
    const positions: [number, number][] = [];

    for (const r of rooms) {
      if (r.lat === null || r.lng === null) continue;
      const pos: [number, number] = [r.lng, r.lat];
      positions.push(pos);
      const active = r.id === highlightedId;
      const marker = new atlas.HtmlMarker({
        position: pos,
        htmlContent: `<div style="transform:translateY(-50%);padding:2px 8px;border-radius:999px;font:600 12px system-ui;white-space:nowrap;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.25);background:${active ? "#f07a30" : "#185a62"};color:#fff">${shortVnd(r.price_month)}</div>`,
        anchor: "bottom",
      });
      map.events.add("click", marker, () => navigate(`/rooms/${r.id}`));
      map.events.add("mouseover", marker, () => {
        st.popup.setOptions({
          position: pos,
          content: `<div style="padding:8px 10px;max-width:220px;font:13px system-ui"><b>${escapeHtml(r.title)}</b><br/>${vnd(r.price_month)} · ${r.area_m2} m²</div>`,
        });
        st.popup.open(map);
      });
      map.events.add("mouseout", marker, () => st.popup.close());
      map.markers.add(marker);
      st.markers.push(marker);
    }

    st.circle.clear();
    if (school) {
      const sm = new atlas.HtmlMarker({
        position: [school.lng, school.lat],
        htmlContent: `<div style="font-size:22px;transform:translateY(-50%)" title="${escapeHtml(school.name)}">🎓</div>`,
      });
      map.markers.add(sm);
      st.markers.push(sm);
      positions.push([school.lng, school.lat]);
      if (radiusM) {
        st.circle.add(new atlas.data.Feature(new atlas.data.Point([school.lng, school.lat]), { subType: "Circle", radius: radiusM }));
      }
    }

    if (positions.length > 1) {
      map.setCamera({ bounds: atlas.data.BoundingBox.fromPositions(positions), padding: 50, maxZoom: 16 });
    } else if (positions.length === 1) {
      map.setCamera({ center: positions[0], zoom: 15 });
    }
  }, [ready, rooms, school, radiusM, highlightedId, navigate]);

  if (!key) {
    return (
      <div className={cx("flex items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500", className)}>
        Chưa cấu hình Azure Maps (biến AZURE_MAPS_KEY). Danh sách phòng vẫn dùng bình thường.
      </div>
    );
  }
  return (
    <div className={cx("relative overflow-hidden rounded-xl border border-slate-200 bg-slate-100", className)}>
      <div ref={el} className="absolute inset-0" />
      {error && <div className="absolute inset-0 flex items-center justify-center text-sm text-rose-600">{error}</div>}
    </div>
  );
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string);
}
