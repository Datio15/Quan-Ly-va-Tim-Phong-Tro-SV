import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "../../api/client";
import type { Invoice, LandlordRoom, MeterReading, Paged } from "../../api/types";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Loading, Notice, PageTitle, Pagination, STATUS_TONE, Select } from "../../components/ui";
import { INVOICE_STATUS_LABEL, currentMonth, date, vnd } from "../../lib/format";

interface GenerateResult {
  month: string;
  created: Invoice[];
  skipped: { tenant_id: string; room_title: string; reason: string }[];
  existing_count: number;
}

/** Chỉ số điện nước, tạo hóa đơn tháng, đánh dấu đã trả (F17, SPEC 9.8). */
export default function InvoicesPage() {
  const qc = useQueryClient();
  const [month, setMonth] = useState(currentMonth(-1));
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [genMonth, setGenMonth] = useState(currentMonth(-1));

  const q = useQuery({
    queryKey: ["invoices", month, status, page],
    queryFn: () => api<Paged<Invoice>>("/landlord/invoices", { query: { month: month || undefined, status: status || undefined, page } }),
  });
  const gen = useMutation({
    mutationFn: () => api<GenerateResult>("/landlord/invoices/generate", { body: { month: genMonth } }),
    onSuccess: (r) => {
      setMonth(r.month);
      qc.invalidateQueries({ queryKey: ["invoices"] });
    },
  });
  const paid = useMutation({
    mutationFn: (id: string) => api(`/landlord/invoices/${id}/paid`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["invoices"] }),
    onError: (e) => alert(errorMessage(e)),
  });

  return (
    <div className="space-y-5">
      <PageTitle>Chỉ số & hóa đơn</PageTitle>

      <div className="grid gap-5 lg:grid-cols-2">
        <MeterReadingCard />
        <Card className="space-y-3">
          <h2 className="font-semibold">Tạo hóa đơn tháng</h2>
          <p className="text-sm text-slate-600">
            Hóa đơn tháng M dùng chỉ số ngày 1/M và 1/(M+1). Hạn thanh toán ngày 10 tháng sau. Mỗi khách một hóa đơn mỗi tháng.
          </p>
          <div className="flex gap-2">
            <Input type="month" value={genMonth} onChange={(e) => setGenMonth(e.target.value)} className="!w-auto" />
            <Button loading={gen.isPending} onClick={() => gen.mutate()}>Tạo hóa đơn</Button>
          </div>
          <ErrorBox error={gen.error} />
          {gen.data && (
            <Notice tone={gen.data.created.length ? "success" : "warn"}>
              Đã tạo {gen.data.created.length} hóa đơn{gen.data.existing_count > 0 && `, ${gen.data.existing_count} khách đã có hóa đơn`}.
              {gen.data.skipped.map((s) => <div key={s.tenant_id} className="text-xs">Bỏ qua {s.room_title}: {s.reason}</div>)}
            </Notice>
          )}
        </Card>
      </div>

      <Card>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 className="mr-auto font-semibold">Danh sách hóa đơn</h2>
          <Input type="month" value={month} onChange={(e) => { setMonth(e.target.value); setPage(1); }} className="!w-auto" />
          <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="!w-auto">
            <option value="">Mọi trạng thái</option>
            {Object.entries(INVOICE_STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
        </div>
        <ErrorBox error={q.error} />
        {q.isLoading && <Loading />}
        {q.data?.items.length === 0 && <Empty>Không có hóa đơn.</Empty>}
        {q.data && q.data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="p-2">Mã</th><th className="p-2">Khách / phòng</th><th className="p-2 text-right">Phòng</th>
                  <th className="p-2 text-right">Điện</th><th className="p-2 text-right">Nước</th><th className="p-2 text-right">Khác</th>
                  <th className="p-2 text-right">Tổng</th><th className="p-2">Hạn</th><th className="p-2">Trạng thái</th><th />
                </tr>
              </thead>
              <tbody>
                {q.data.items.map((i) => (
                  <tr key={i.id} className="border-t border-slate-100">
                    <td className="p-2 font-mono text-xs">{i.code}</td>
                    <td className="p-2">{i.tenant_name}<div className="text-xs text-slate-500">{i.room_title}</div></td>
                    <td className="p-2 text-right tabular-nums">{vnd(i.rent)}</td>
                    <td className="p-2 text-right tabular-nums">{vnd(i.electricity_amount)}<div className="text-xs text-slate-500">{i.electricity_used} kWh</div></td>
                    <td className="p-2 text-right tabular-nums">{vnd(i.water_amount)}<div className="text-xs text-slate-500">{i.water_used} m³</div></td>
                    <td className="p-2 text-right tabular-nums">{vnd(i.internet_amount + i.parking_amount + i.service_amount + i.other_amount)}</td>
                    <td className="p-2 text-right font-semibold tabular-nums">{vnd(i.total)}</td>
                    <td className="p-2">{date(i.due_date)}</td>
                    <td className="p-2"><Badge tone={STATUS_TONE[i.status]}>{INVOICE_STATUS_LABEL[i.status]}</Badge></td>
                    <td className="p-2">
                      {(i.status === "unpaid" || i.status === "overdue") && (
                        <Button variant="secondary" className="!px-2 !py-1 text-xs" onClick={() => paid.mutate(i.id)}>Đã trả</Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {q.data && <Pagination page={q.data.page} pageSize={q.data.page_size} total={q.data.total} onChange={setPage} />}
      </Card>
    </div>
  );
}

function MeterReadingCard() {
  const qc = useQueryClient();
  const rooms = useQuery({ queryKey: ["landlord-rooms", "all"], queryFn: () => api<Paged<LandlordRoom>>("/landlord/rooms", { query: { page_size: 50 } }) });
  const [roomId, setRoomId] = useState("");
  const [month, setMonth] = useState(currentMonth());
  const [e, setE] = useState("");
  const [w, setW] = useState("");
  const readings = useQuery({
    queryKey: ["readings", roomId],
    queryFn: () => api<MeterReading[]>("/landlord/meter-readings", { query: { room_id: roomId } }),
    enabled: !!roomId,
  });
  const save = useMutation({
    mutationFn: () => api("/landlord/meter-readings", { body: { room_id: roomId, month, electricity_index: Number(e), water_index: Number(w) } }),
    onSuccess: () => {
      setE("");
      setW("");
      qc.invalidateQueries({ queryKey: ["readings", roomId] });
    },
  });

  return (
    <Card className="space-y-3">
      <h2 className="font-semibold">Nhập chỉ số công tơ (ngày 1 hằng tháng)</h2>
      <form className="space-y-3" onSubmit={(ev) => { ev.preventDefault(); save.mutate(); }}>
        <Field label="Phòng">
          <Select required value={roomId} onChange={(ev) => setRoomId(ev.target.value)}>
            <option value="">— Chọn phòng —</option>
            {rooms.data?.items.map((r) => <option key={r.id} value={r.id}>{r.house_name} · {r.title}</option>)}
          </Select>
        </Field>
        <div className="grid grid-cols-3 gap-2">
          <Field label="Kỳ (tháng)"><Input type="month" required value={month} onChange={(ev) => setMonth(ev.target.value)} /></Field>
          <Field label="Chỉ số điện"><Input type="number" required min={0} step={0.1} value={e} onChange={(ev) => setE(ev.target.value)} /></Field>
          <Field label="Chỉ số nước"><Input type="number" required min={0} step={0.1} value={w} onChange={(ev) => setW(ev.target.value)} /></Field>
        </div>
        <ErrorBox error={save.error} />
        <Button type="submit" loading={save.isPending} disabled={!roomId}>Lưu chỉ số</Button>
      </form>
      {roomId && readings.data && (
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500"><tr><th className="py-1">Kỳ</th><th className="py-1 text-right">Điện</th><th className="py-1 text-right">Nước</th></tr></thead>
          <tbody>
            {readings.data.slice(0, 6).map((r) => (
              <tr key={r.id} className="border-t border-slate-100">
                <td className="py-1">01/{r.month.slice(5)}/{r.month.slice(0, 4)}</td>
                <td className="py-1 text-right tabular-nums">{r.electricity_index}</td>
                <td className="py-1 text-right tabular-nums">{r.water_index}</td>
              </tr>
            ))}
            {readings.data.length === 0 && <tr><td colSpan={3} className="py-2 text-slate-500">Chưa có chỉ số.</td></tr>}
          </tbody>
        </table>
      )}
    </Card>
  );
}
