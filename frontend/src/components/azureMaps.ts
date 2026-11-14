// Tải Azure Maps Web SDK v3 từ CDN chính thức một lần (SPEC 5, 11.5).
/* eslint-disable @typescript-eslint/no-explicit-any */
declare global {
  interface Window {
    atlas?: any;
  }
}

const SDK_JS = "https://atlas.microsoft.com/sdk/javascript/mapcontrol/3/atlas.min.js";
const SDK_CSS = "https://atlas.microsoft.com/sdk/javascript/mapcontrol/3/atlas.min.css";
let loading: Promise<any> | null = null;

export function loadAtlas(): Promise<any> {
  if (window.atlas) return Promise.resolve(window.atlas);
  if (loading) return loading;
  loading = new Promise((resolve, reject) => {
    const css = document.createElement("link");
    css.rel = "stylesheet";
    css.href = SDK_CSS;
    document.head.appendChild(css);
    const s = document.createElement("script");
    s.src = SDK_JS;
    s.async = true;
    s.onload = () => (window.atlas ? resolve(window.atlas) : reject(new Error("Không tải được Azure Maps")));
    s.onerror = () => {
      loading = null;
      reject(new Error("Không tải được Azure Maps"));
    };
    document.head.appendChild(s);
  });
  return loading;
}

export const HANOI_CENTER: [number, number] = [105.79, 21.03]; // [lng, lat]

/** Geocode địa chỉ bằng Azure Maps Geocoding API (Search v2). Trả [lng, lat] hoặc null. */
export async function geocode(key: string, query: string): Promise<[number, number] | null> {
  const url =
    `https://atlas.microsoft.com/geocode?api-version=2023-06-01&countryRegion=VN&top=1` +
    `&query=${encodeURIComponent(query)}&subscription-key=${encodeURIComponent(key)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Geocode lỗi ${res.status}`);
  const data = await res.json();
  const coords = data?.features?.[0]?.geometry?.coordinates;
  return Array.isArray(coords) && coords.length >= 2 ? [coords[0], coords[1]] : null;
}
