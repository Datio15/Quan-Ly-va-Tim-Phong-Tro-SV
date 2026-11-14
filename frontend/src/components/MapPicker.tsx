/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useRef, useState } from "react";
import { useConfig } from "../lib/catalog";
import { HANOI_CENTER, geocode, loadAtlas } from "./azureMaps";
import { Button, Input } from "./ui";

interface Props {
  lat: number | null;
  lng: number | null;
  address: string;
  onChange: (lat: number, lng: number) => void;
}

/** Chọn tọa độ nhà trọ: geocode địa chỉ bằng Azure Maps rồi kéo ghim để sửa (SPEC 9.6). */
export default function MapPicker({ lat, lng, address, onChange }: Props) {
  const { data: cfg } = useConfig();
  const key = cfg?.maps_key;
  const el = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const markerRef = useRef<any>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!key || !el.current) return;
    let disposed = false;
    loadAtlas()
      .then((atlas) => {
        if (disposed || !el.current) return;
        const start: [number, number] = lat !== null && lng !== null ? [lng, lat] : HANOI_CENTER;
        const map = new atlas.Map(el.current, {
          center: start,
          zoom: lat !== null ? 16 : 13,
          language: "vi-VN",
          authOptions: { authType: "subscriptionKey", subscriptionKey: key },
        });
        map.events.add("ready", () => {
          map.controls.add(new atlas.control.ZoomControl(), { position: "top-right" });
          const marker = new atlas.HtmlMarker({ position: start, draggable: true, color: "#f07a30" });
          map.markers.add(marker);
          map.events.add("dragend", marker, () => {
            const [x, y] = marker.getOptions().position;
            onChangeRef.current(round(y), round(x));
          });
          map.events.add("click", (e: any) => {
            marker.setOptions({ position: e.position });
            onChangeRef.current(round(e.position[1]), round(e.position[0]));
          });
          markerRef.current = marker;
          mapRef.current = map;
        });
      })
      .catch((e) => setMsg(e.message));
    return () => {
      disposed = true;
      mapRef.current?.dispose();
      mapRef.current = null;
    };
    // chỉ khởi tạo một lần theo khóa
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // Đồng bộ ghim khi người dùng gõ tọa độ tay
  useEffect(() => {
    if (lat === null || lng === null || !markerRef.current || !mapRef.current) return;
    const [x, y] = markerRef.current.getOptions().position;
    if (Math.abs(x - lng) > 1e-7 || Math.abs(y - lat) > 1e-7) {
      markerRef.current.setOptions({ position: [lng, lat] });
      mapRef.current.setCamera({ center: [lng, lat] });
    }
  }, [lat, lng]);

  async function doGeocode() {
    if (!key) return;
    setBusy(true);
    setMsg(null);
    try {
      const pos = await geocode(key, address);
      if (!pos) setMsg("Không tìm thấy địa chỉ, hãy kéo ghim trên bản đồ.");
      else {
        onChange(round(pos[1]), round(pos[0]));
        setMsg("Đã định vị, kéo ghim nếu chưa chính xác.");
      }
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      {key ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="secondary" loading={busy} onClick={doGeocode} disabled={!address.trim()}>
              📍 Định vị theo địa chỉ
            </Button>
            <span className="text-xs text-slate-500">Bấm trên bản đồ hoặc kéo ghim để chỉnh vị trí.</span>
          </div>
          <div className="relative h-64 overflow-hidden rounded-lg border border-slate-200">
            <div ref={el} className="absolute inset-0" />
          </div>
        </>
      ) : (
        <p className="text-xs text-slate-500">Chưa cấu hình Azure Maps: nhập tọa độ tay (có thể lấy từ Google Maps).</p>
      )}
      {msg && <p className="text-xs text-slate-600">{msg}</p>}
      <div className="grid grid-cols-2 gap-2">
        <Input type="number" step="0.000001" placeholder="Vĩ độ (lat)" value={lat ?? ""}
          onChange={(e) => e.target.value && onChange(Number(e.target.value), lng ?? HANOI_CENTER[0])} />
        <Input type="number" step="0.000001" placeholder="Kinh độ (lng)" value={lng ?? ""}
          onChange={(e) => e.target.value && onChange(lat ?? HANOI_CENTER[1], Number(e.target.value))} />
      </div>
    </div>
  );
}

function round(x: number) {
  return Math.round(x * 1e6) / 1e6;
}
