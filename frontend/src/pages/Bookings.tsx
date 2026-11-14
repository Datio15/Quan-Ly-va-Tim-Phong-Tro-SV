import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "../api/client";
import type { Booking, Paged } from "../api/types";
import { Badge, Button, Card, Empty, ErrorBox, Loading, PageTitle, Pagination, STATUS_TONE, cx } from "../components/ui";
import { useAuth } from "../lib/auth";
import { BOOKING_STATUS_LABEL, dateTime } from "../lib/format";

const TABS = ["", "requested", "confirmed", "done", "declined", "cancelled"];

/** Lịch xem phòng của sinh viên, hoặc các lịch của phòng mình (chủ trọ) – F08. */
export default function BookingsPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const isLandlord = user?.role === "landlord";

  const q = useQuery({
    queryKey: ["bookings", status, page],
    queryFn: () => api<Paged<Booking>>("/bookings", { query: { status: status || undefined, page } }),
  });
  const act = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) => api(`/bookings/${id}/${action}`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bookings"] }),
    onError: (e) => alert(errorMessage(e)),
  });

  const run = (id: string, action: string, confirmText?: string) => {
    if (confirmText && !confirm(confirmText)) return;
    act.mutate({ id, action });
  };

  return (
    <div>
      <PageTitle>{isLandlord ? "Lịch xem phòng của khách" : "Lịch xem phòng của tôi"}</PageTitle>
      <div className="mb-4 flex flex-wrap gap-1">
        {TABS.map((t) => (
          <button key={t} onClick={() => { setStatus(t); setPage(1); }}
            className={cx("rounded-full px-3 py-1.5 text-sm", status === t ? "bg-brand-600 text-white" : "bg-white text-slate-600 hover:bg-slate-100")}>
            {t ? BOOKING_STATUS_LABEL[t] : "Tất cả"}
          </button>
        ))}
      </div>
      <ErrorBox error={q.error} />
      {q.isLoading && <Loading />}
      {q.data && q.data.items.length === 0 && <Empty>Chưa có lịch nào.</Empty>}
      <div className="grid gap-3 md:grid-cols-2">
        {q.data?.items.map((b) => {
          const past = new Date(b.slot_start).getTime() <= Date.now();
          return (
            <Card key={b.id}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <Link to={`/rooms/${b.room.id}`} className="font-semibold hover:text-brand-700">{b.room.title}</Link>
                  <div className="text-sm text-slate-500">{b.room.street}, {b.room.area}{b.house_name && ` · ${b.house_name}`}</div>
                </div>
                <Badge tone={STATUS_TONE[b.status]}>{BOOKING_STATUS_LABEL[b.status]}</Badge>
              </div>
              <div className="mt-3 text-sm">🕒 <b>{dateTime(b.slot_start)}</b></div>
              {b.student && <div className="mt-1 text-sm text-slate-600">👤 {b.student.full_name}{b.student.phone && ` · ${b.student.phone}`}</div>}
              {b.room.address && <div className="mt-1 text-sm text-slate-600">📍 {b.room.address}</div>}
              {b.landlord && <div className="mt-1 text-sm text-slate-600">🏠 Chủ trọ: {b.landlord.full_name}{b.landlord.phone && ` · ${b.landlord.phone}`}</div>}
              {b.student_note && <div className="mt-2 rounded bg-slate-50 px-2 py-1 text-sm text-slate-600">“{b.student_note}”</div>}
              {b.landlord_note && <div className="mt-1 text-xs text-slate-500">Chủ trọ ghi chú: {b.landlord_note}</div>}
              <div className="mt-3 flex flex-wrap gap-2">
                {isLandlord && b.status === "requested" && (
                  <>
                    <Button onClick={() => run(b.id, "confirm")}>Xác nhận</Button>
                    <Button variant="secondary" onClick={() => run(b.id, "decline", "Từ chối lịch này?")}>Từ chối</Button>
                  </>
                )}
                {isLandlord && b.status === "confirmed" && past && <Button onClick={() => run(b.id, "done")}>Đánh dấu đã xem</Button>}
                {(b.status === "requested" || b.status === "confirmed") && (
                  <Button variant="ghost" onClick={() => run(b.id, "cancel", "Hủy lịch này?")}>Hủy lịch</Button>
                )}
                {!isLandlord && b.status === "done" && <Link to={`/rooms/${b.room.id}`} className="text-sm text-brand-700 underline">Viết đánh giá</Link>}
              </div>
            </Card>
          );
        })}
      </div>
      {q.data && <Pagination page={q.data.page} pageSize={q.data.page_size} total={q.data.total} onChange={setPage} />}
    </div>
  );
}
