import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

// Danh sách phòng chọn để so sánh (tối đa 3, F06). Lưu tạm trong trình duyệt cho tiện.
const KEY = "phongtro.compare";
export const MAX_COMPARE = 3;

interface CompareItem {
  id: string;
  title: string;
}

interface CompareState {
  items: CompareItem[];
  has: (id: string) => boolean;
  toggle: (item: CompareItem) => boolean;
  clear: () => void;
}

const Ctx = createContext<CompareState | null>(null);

function load(): CompareItem[] {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.slice(0, MAX_COMPARE) : [];
  } catch {
    return [];
  }
}

export function CompareProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CompareItem[]>(load);

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(items));
    } catch {
      /* bỏ qua */
    }
  }, [items]);

  const has = useCallback((id: string) => items.some((i) => i.id === id), [items]);
  const toggle = useCallback(
    (item: CompareItem) => {
      if (items.some((i) => i.id === item.id)) {
        setItems(items.filter((i) => i.id !== item.id));
        return true;
      }
      if (items.length >= MAX_COMPARE) return false;
      setItems([...items, item]);
      return true;
    },
    [items],
  );
  const clear = useCallback(() => setItems([]), []);
  const value = useMemo(() => ({ items, has, toggle, clear }), [items, has, toggle, clear]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCompare(): CompareState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useCompare ngoài CompareProvider");
  return ctx;
}
