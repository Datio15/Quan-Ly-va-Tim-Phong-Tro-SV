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
  /** Người dùng xóa trống ô tọa độ. */
  onClear?: () => void;
}

/** Chọn tọa độ nhà trọ: geocode địa chỉ bằng Azure Maps rồi kéo ghim để sửa (SPEC 9.6). */
export default function MapPicker({ lat, lng, address, onChange, onClear }: Props) {
  const { data: cfg } = useConfig();
  const key = cfg?.maps_key;
  const el = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const markerRef = useRef<any>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  // FE-08: ô nhập là chuỗi riêng, xóa trống được; chỉ báo lên khi đủ cả hai số (không tự điền kinh độ giả).
  const [latText, setLatText] = useState(lat === null ? "" : String(lat));
  const [lngText, setLngText] = useState(lng === null ? "" : String(lng));
  useEffect(() => {
    setLatText(lat === null ? "" : String(lat));
    setLngText(lng === null ? "" : String(lng));
  }, [lat, lng]);

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
          // FE-08: nhà chưa có tọa độ thì ẩn ghim, tránh tưởng nhầm "đã đặt ghim" ở trung tâm Hà Nội.
          const marker = new atlas.HtmlMarker({ position: start, draggable: true, color: "#f07a30", visible: lat !== null && lng !== null });
          map.markers.add(marker);
          map.events.add("dragend", marker, () => {
            const [x, y] = marker.getOptions().position;
            onChangeRef.current(round(y), round(x));
          });
          map.events.add("click", (e: any) => {
            marker.setOptions({ position: e.position, visible: true });
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
    if (!markerRef.current || !mapRef.current) return;
    if (lat === null || lng === null) {
      markerRef.current.setOptions({ visible: false });
      return;
    }
    const [x, y] = markerRef.current.getOptions().position;
    markerRef.current.setOptions({ visible: true });
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

  function typed(latS: string, lngS: string, setText: (v: string) => void, isLng = false) {
    setText(isLng ? lngS : latS);
    if (latS === "" && lngS === "") {
      onClear?.();
      return;
    }
    const la = Number(latS), ln = Number(lngS);
    if (latS !== "" && lngS !== "" && Number.isFinite(la) && Number.isFinite(ln) && Math.abs(la) <= 90 && Math.abs(ln) <= 180) {
      onChange(la, ln);
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
        <Input type="number" step="any" min={-90} max={90} placeholder="Vĩ độ (lat)" value={latText}
          onChange={(e) => typed(e.target.value, lngText, setLatText)} />
        <Input type="number" step="any" min={-180} max={180} placeholder="Kinh độ (lng)" value={lngText}
          onChange={(e) => typed(latText, e.target.value, setLngText, true)} />
      </div>
      {(latText === "") !== (lngText === "") && <p className="text-xs text-amber-700">Cần nhập cả vĩ độ và kinh độ.</p>}
    </div>
  );
}

function round(x: number) {
  return Math.round(x * 1e6) / 1e6;
}
