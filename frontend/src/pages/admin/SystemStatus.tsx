import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { JobRun, SystemStatus } from "../../api/types";
import { Badge, Button, Card, ErrorBox, Loading, Notice, PageTitle, STATUS_TONE, cx } from "../../components/ui";
import { dateTime } from "../../lib/format";

const JOB_LABEL: Record<string, string> = {
  backup: "Sao lưu", restore_test: "Khôi phục thử", sync_resync: "Đồng bộ lại",
  viewing_reminder: "Nhắc lịch xem", invoice_due_check: "Kiểm tra hóa đơn", contract_expiring: "Nhắc hợp đồng",
};

/** Trang trạng thái hệ thống (F14): đồng bộ, hàng đợi, sao lưu, khôi phục thử. */
export default function SystemStatusPage() {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["system-status"],
    queryFn: () => api<SystemStatus>("/admin/system/status"),
    refetchInterval: 10_000,
  });
  const [watchJob, setWatchJob] = useState<number | null>(null);
  const resync = useMutation({
    mutationFn: () => api<{ enqueued: number; reset_failed: number }>("/admin/sync/resync", { body: {} }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["system-status"] }),
  });
  const runJob = useMutation({
    mutationFn: (kind: "run" | "restore-test") => api<{ job_run_id: number; status: string }>(`/admin/backup/${kind}`, { method: "POST" }),
    onSuccess: (r) => setWatchJob(r.job_run_id),
  });

  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  const s = q.data!;

  return (
    <div className="space-y-5">
      <PageTitle actions={<Button variant="secondary" onClick={() => q.refetch()} loading={q.isFetching}>Làm mới</Button>}>Trạng thái hệ thống</PageTitle>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Light ok={s.db} label="PostgreSQL" sub="vm-data" />
        <Light ok={s.minio} label="MinIO" sub="vm-data" />
        <Light ok={s.azure_search_reachable} label="Azure AI Search" sub={s.azure_search_reachable ? "đang dùng" : "tìm kiếm dự phòng bằng CSDL"} />
        <Light ok={s.search_fallback_last_hour === 0} label="Tìm kiếm dự phòng" sub={`${s.search_fallback_last_hour} lần / giờ qua`} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 font-semibold">Đồng bộ OpenStack → Azure (outbox)</h2>
          <div className="grid grid-cols-3 gap-3 text-center">
            <Stat label="Đang chờ" value={s.outbox.pending} tone={s.outbox.pending > 0 ? "text-amber-600" : ""} />
            <Stat label="Lỗi" value={s.outbox.failed} tone={s.outbox.failed > 0 ? "text-rose-600" : ""} />
            <Stat label="Gửi gần nhất" value={dateTime(s.outbox.last_sent_at)} small />
          </div>
          <div className="mt-4 flex items-center gap-3">
            <Button loading={resync.isPending} onClick={() => confirm("Xếp lại mọi phòng công khai để đồng bộ?") && resync.mutate()}>Đồng bộ lại toàn bộ</Button>
            {resync.data && <span className="text-sm text-emerald-700">Đã xếp {resync.data.enqueued} phòng, đặt lại {resync.data.reset_failed} dòng lỗi.</span>}
          </div>
          {s.outbox_failed_rows.length > 0 && (
            <div className="mt-4 max-h-56 overflow-y-auto text-xs">
              {s.outbox_failed_rows.map((o) => (
                <div key={o.id} className="border-t border-slate-100 py-1.5">
                  <span className="font-mono">#{o.id}</span> {o.op} phòng <span className="font-mono">{o.room_id.slice(0, 8)}</span> · {o.attempts} lần
                  <div className="text-rose-600">{o.last_error}</div>
                </div>
              ))}
            </div>
          )}
          <p className="mt-3 text-xs text-slate-500">Hàng đợi hẹn giờ (Azure Queue ops-ticks) – tin gần nhất: {dateTime(s.queue.last_message_at)}</p>
        </Card>

        <Card>
          <h2 className="mb-3 font-semibold">Sao lưu & khôi phục (F13)</h2>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-lg bg-slate-50 p-3">
              <div className="text-xs text-slate-500">Sao lưu thành công gần nhất</div>
              <div className="font-medium">{dateTime(s.backup.last_success_at)}</div>
              <div className="text-xs text-slate-500">{s.backup.size_bytes ? `${(s.backup.size_bytes / 1024).toFixed(1)} KB` : ""} {s.backup.duration_ms ? `· ${s.backup.duration_ms} ms` : ""}</div>
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <div className="text-xs text-slate-500">Khôi phục thử gần nhất</div>
              <div className="font-medium">{dateTime(s.restore_test.last_at)}</div>
              <div className="text-xs text-slate-500">
                {s.restore_test.total_ms !== null && `RTO ${s.restore_test.total_ms} ms · `}
                {s.restore_test.counts_match === null ? "" : s.restore_test.counts_match ? "số dòng khớp ✓" : "LỆCH số dòng ✕"}
              </div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button loading={runJob.isPending && runJob.variables === "run"} onClick={() => runJob.mutate("run")}>Sao lưu ngay</Button>
            <Button variant="secondary" loading={runJob.isPending && runJob.variables === "restore-test"} onClick={() => runJob.mutate("restore-test")}>Khôi phục thử</Button>
          </div>
          <ErrorBox error={runJob.error} className="mt-3" />
          {watchJob && <JobWatcher id={watchJob} onDone={() => qc.invalidateQueries({ queryKey: ["system-status"] })} />}
        </Card>
      </div>

      <Card>
        <h2 className="mb-3 font-semibold">Việc nền gần đây</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead className="text-left text-xs uppercase text-slate-500">
              <tr><th className="p-2">#</th><th className="p-2">Việc</th><th className="p-2">Trạng thái</th><th className="p-2">Bắt đầu</th><th className="p-2">Kết thúc</th><th className="p-2">Chi tiết</th></tr>
            </thead>
            <tbody>
              {s.recent_jobs.map((j) => (
                <tr key={j.id} className="border-t border-slate-100 align-top">
                  <td className="p-2 font-mono text-xs">{j.id}</td>
                  <td className="p-2">{JOB_LABEL[j.job] || j.job}</td>
                  <td className="p-2"><Badge tone={STATUS_TONE[j.status]}>{j.status}</Badge></td>
                  <td className="p-2 text-xs">{dateTime(j.started_at)}</td>
                  <td className="p-2 text-xs">{dateTime(j.finished_at)}</td>
                  <td className="p-2"><JobDetails details={j.details} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function JobWatcher({ id, onDone }: { id: number; onDone: () => void }) {
  const q = useQuery({
    queryKey: ["job", id],
    queryFn: () => api<JobRun>(`/admin/jobs/${id}`),
    refetchInterval: (query) => (query.state.data && ["success", "failed"].includes(query.state.data.status) ? false : 3000),
  });
  const finished = q.data && ["success", "failed"].includes(q.data.status);
  useEffect(() => {
    if (finished) onDone();
  }, [finished, onDone]);
  if (!q.data) return null;
  const j = q.data;
  return (
    <div className="mt-3">
      <Notice tone={j.status === "failed" ? "warn" : j.status === "success" ? "success" : "info"}>
        {JOB_LABEL[j.job]} #{j.id}: <b>{j.status}</b>
        {j.status === "queued" && " – chờ worker nhận việc (worker chạy backup.sh / restore-test.sh)."}
        <div className="mt-1"><JobDetails details={j.details} /></div>
      </Notice>
    </div>
  );
}

function JobDetails({ details }: { details: Record<string, unknown> }) {
  const entries = Object.entries(details || {}).filter(([k]) => k !== "requested_by");
  if (!entries.length) return <span className="text-xs text-slate-400">–</span>;
  return (
    <div className="flex flex-wrap gap-x-3 text-xs text-slate-600">
      {entries.map(([k, v]) => <span key={k}><span className="text-slate-400">{k}:</span> {String(v)}</span>)}
    </div>
  );
}

function Light({ ok, label, sub }: { ok: boolean; label: string; sub: string }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4">
      <span className={cx("h-3 w-3 shrink-0 rounded-full", ok ? "bg-emerald-500" : "bg-rose-500")} />
      <div className="min-w-0">
        <div className="font-medium">{label}</div>
        <div className="truncate text-xs text-slate-500">{sub}</div>
      </div>
    </div>
  );
}

function Stat({ label, value, tone, small }: { label: string; value: string | number; tone?: string; small?: boolean }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <div className={cx(small ? "text-sm font-medium" : "text-2xl font-bold", tone)}>{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}
