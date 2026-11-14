import { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { CostBreakdown } from "../api/types";
import { useConfig } from "../lib/catalog";
import { vnd } from "../lib/format";
import { Input } from "./ui";

/** Chi phí thực tế mỗi tháng, chỉnh được số điện, nước, người, xe (F07, SPEC 9.5). */
export default function CostTable({ roomId }: { roomId: string }) {
  const { data: cfg } = useConfig();
  const [inputs, setInputs] = useState({ kwh: 100, m3: 4, people: 1, vehicles: 1 });
  const [debounced, setDebounced] = useState(inputs);

  useEffect(() => {
    if (cfg) {
      setInputs(cfg.est_defaults);
      setDebounced(cfg.est_defaults);
    }
  }, [cfg]);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(inputs), 300);
    return () => clearTimeout(t);
  }, [inputs]);

  const { data, isFetching } = useQuery({
    queryKey: ["cost", roomId, debounced],
    queryFn: () => api<CostBreakdown>(`/rooms/${roomId}/cost`, { query: debounced }),
    placeholderData: keepPreviousData,
  });

  const fields: { key: keyof typeof inputs; label: string; step: number; min: number }[] = [
    { key: "kwh", label: "Điện (kWh)", step: 10, min: 0 },
    { key: "m3", label: "Nước (m³)", step: 1, min: 0 },
    { key: "people", label: "Số người", step: 1, min: 1 },
    { key: "vehicles", label: "Số xe", step: 1, min: 0 },
  ];

  return (
    <div>
      <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {fields.map((f) => (
          <label key={f.key} className="text-xs text-slate-600">
            {f.label}
            <Input
              type="number"
              min={f.min}
              step={f.step}
              value={inputs[f.key]}
              onChange={(e) => setInputs({ ...inputs, [f.key]: Math.max(f.min, Number(e.target.value) || 0) })}
              className="mt-1"
            />
          </label>
        ))}
      </div>
      <table className={`w-full text-sm ${isFetching ? "opacity-60" : ""}`}>
        <tbody>
          {data?.lines.map((l) => (
            <tr key={l.code} className="border-b border-slate-100">
              <td className="py-1.5 text-slate-600">{l.label}</td>
              <td className="py-1.5 text-right tabular-nums">{vnd(l.amount)}</td>
            </tr>
          ))}
          <tr>
            <td className="pt-2 font-semibold">Tổng mỗi tháng</td>
            <td className="pt-2 text-right text-lg font-bold tabular-nums text-accent-600">{vnd(data?.total)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
