import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "../../api/client";
import type { AdminLandlord, AdminReport, Paged } from "../../api/types";
import { Badge, Button, Card, Empty, ErrorBox, Loading, PageTitle, Pagination, STATUS_TONE, Select, Stars } from "../../components/ui";
import { dateTime } from "../../lib/format";

export function ReportsPage() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("open");
  const [page, setPage] = useState(1);
  const q = useQuery({
    queryKey: ["admin-reports", status, page],
    queryFn: () => api<Paged<AdminReport>>("/admin/reports", { query: { status, page } }),
  });
  const resolve = useMutation({
    mutationFn: ({ id, action, hide }: { id: string; action: "resolve" | "dismiss"; hide: boolean }) =>
      api(`/admin/reports/${id}/resolve`, { body: { action, hide_review: hide } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-reports"] }),
    onError: (e) => alert(errorMessage(e)),
  });
  const LABEL = { open: "Đang mở", resolved: "Đã xử lý", dismissed: "Bỏ qua" };

  return (
    <div>
      <PageTitle actions={
        <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="!w-auto">
          {Object.entries(LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
      }>Báo cáo vi phạm</PageTitle>
      <ErrorBox error={q.error} />
      {q.isLoading && <Loading />}
      {q.data?.items.length === 0 && <Empty>Không có báo cáo.</Empty>}
      <div className="space-y-3">
        {q.data?.items.map((r) => (
          <Card key={r.id}>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="text-sm">
                <Badge tone="violet">{r.target.type === "room" ? "Tin đăng" : "Đánh giá"}</Badge>{" "}
                <Badge tone={STATUS_TONE[r.status]}>{LABEL[r.status]}</Badge>
                <span className="ml-2 text-xs text-slate-400">{dateTime(r.created_at)}</span>
                <p className="mt-2"><b>Lý do:</b> {r.reason}</p>
                {r.target.type === "review" ? (
                  <div className="mt-2 rounded bg-slate-50 p-2">
                    <b>{r.target.student_name}</b> <Stars value={r.target.rating ?? null} size="text-sm" /> {r.target.is_hidden && <Badge tone="red">Đã ẩn</Badge>}
                    <p className="text-slate-700">{r.target.comment}</p>
                    {r.target.room_id && <Link to={`/rooms/${r.target.room_id}`} className="text-xs text-brand-700 underline">Xem phòng</Link>}
                  </div>
                ) : (
                  <div className="mt-2">
                    <Link to={`/rooms/${r.target.id}`} className="text-brand-700 underline">{r.target.title}</Link> <span className="text-xs text-slate-500">({r.target.status})</span>
                    <p className="text-xs text-slate-500">Muốn gỡ tin: vào “Duyệt tin” → Tin đang hiển thị → Gỡ tin.</p>
                  </div>
                )}
              </div>
              {r.status === "open" && (
                <div className="flex flex-wrap gap-2">
                  {r.target.type === "review" && !r.target.is_hidden && (
                    <Button variant="danger" onClick={() => resolve.mutate({ id: r.id, action: "resolve", hide: true })}>Ẩn đánh giá</Button>
                  )}
                  <Button variant="secondary" onClick={() => resolve.mutate({ id: r.id, action: "resolve", hide: false })}>Đã xử lý</Button>
                  <Button variant="ghost" onClick={() => resolve.mutate({ id: r.id, action: "dismiss", hide: false })}>Bỏ qua</Button>
                </div>
              )}
            </div>
          </Card>
        ))}
      </div>
      {q.data && <Pagination page={q.data.page} pageSize={q.data.page_size} total={q.data.total} onChange={setPage} />}
    </div>
  );
}

export function LandlordsPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["admin-landlords"], queryFn: () => api<AdminLandlord[]>("/admin/landlords") });
  const m = useMutation({
    mutationFn: ({ id, verify }: { id: string; verify: boolean }) => api(`/admin/landlords/${id}/${verify ? "verify" : "unverify"}`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-landlords"] }),
    onError: (e) => alert(errorMessage(e)),
  });
  return (
    <div>
      <PageTitle>Chủ trọ</PageTitle>
      <ErrorBox error={q.error} />
      {q.isLoading && <Loading />}
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full min-w-[600px] text-sm">
          <thead className="text-left text-xs uppercase text-slate-500">
            <tr><th className="p-3">Họ tên</th><th className="p-3">Liên hệ</th><th className="p-3">Số phòng</th><th className="p-3">Xác minh</th><th /></tr>
          </thead>
          <tbody>
            {q.data?.map((l) => (
              <tr key={l.id} className="border-t border-slate-100">
                <td className="p-3 font-medium">{l.full_name}</td>
                <td className="p-3 text-slate-600">{l.email}<div className="text-xs">{l.phone}</div></td>
                <td className="p-3">{l.room_count}</td>
                <td className="p-3">{l.verified ? <Badge tone="green">Đã xác minh</Badge> : <Badge>Chưa</Badge>}</td>
                <td className="p-3 text-right">
                  <Button variant={l.verified ? "ghost" : "secondary"} onClick={() => m.mutate({ id: l.id, verify: !l.verified })}>
                    {l.verified ? "Bỏ xác minh" : "Xác minh"}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-500">Đổi trạng thái xác minh sẽ đồng bộ lại mọi phòng công khai của chủ trọ đó sang Azure.</p>
    </div>
  );
}
