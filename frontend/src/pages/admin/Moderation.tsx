import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { LandlordRoomFull, Paged } from "../../api/types";
import { Badge, Button, Card, Empty, ErrorBox, Loading, Modal, PageTitle, Pagination, Select, Textarea, cx } from "../../components/ui";
import { useAmenityLabels } from "../../lib/catalog";
import { dateTime, vnd } from "../../lib/format";

/** Duyệt tin và ảnh (F03). Phòng đang hiển thị có ảnh mới cũng được duyệt ở đây. */
export default function ModerationPage() {
  const [mode, setMode] = useState("pending");
  const [page, setPage] = useState(1);
  const q = useQuery({
    queryKey: ["admin-rooms", mode, page],
    queryFn: () =>
      api<Paged<LandlordRoomFull>>("/admin/rooms", {
        query: mode === "images" ? { status: "published", pending_images: true, page } : { status: mode, page },
      }),
  });

  return (
    <div>
      <PageTitle actions={
        <Select value={mode} onChange={(e) => { setMode(e.target.value); setPage(1); }} className="!w-auto">
          <option value="pending">Tin chờ duyệt</option>
          <option value="images">Phòng đang hiển thị có ảnh mới</option>
          <option value="published">Tin đang hiển thị</option>
          <option value="rejected">Tin bị từ chối</option>
        </Select>
      }>Duyệt tin đăng</PageTitle>
      <ErrorBox error={q.error} />
      {q.isLoading && <Loading />}
      {q.data?.items.length === 0 && <Empty>Không có tin nào.</Empty>}
      <div className="space-y-4">
        {q.data?.items.map((r) => <ModerationCard key={r.id} room={r} />)}
      </div>
      {q.data && <Pagination page={q.data.page} pageSize={q.data.page_size} total={q.data.total} onChange={setPage} />}
    </div>
  );
}

function ModerationCard({ room }: { room: LandlordRoomFull }) {
  const qc = useQueryClient();
  const label = useAmenityLabels();
  const pendingImgs = room.images.filter((i) => i.moderation === "pending");
  const [okIds, setOkIds] = useState<Set<string>>(new Set(pendingImgs.map((i) => i.id)));
  const [rejectOpen, setRejectOpen] = useState(false);
  const [reason, setReason] = useState("");
  const done = () => qc.invalidateQueries({ queryKey: ["admin-rooms"] });
  const approve = useMutation({
    mutationFn: () => api(`/admin/rooms/${room.id}/approve`, { body: { image_ids_ok: Array.from(okIds) } }),
    onSuccess: done,
  });
  const reject = useMutation({
    mutationFn: () => api(`/admin/rooms/${room.id}/reject`, { body: { reason } }),
    onSuccess: () => { setRejectOpen(false); done(); },
  });
  const toggle = (id: string) => {
    const next = new Set(okIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setOkIds(next);
  };

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="font-semibold">{room.title}</div>
          <div className="text-sm text-slate-500">
            {room.house.street}, {room.house.ward} · {room.house.area} · {vnd(room.price_month)} · {room.area_m2} m²
          </div>
          <div className="text-sm text-slate-500">
            Chủ trọ: {room.landlord?.full_name} {room.landlord?.verified ? <Badge tone="green">Đã xác minh</Badge> : <Badge>Chưa xác minh</Badge>}
            <span className="ml-2 text-xs text-slate-400">cập nhật {dateTime(room.updated_at)}</span>
          </div>
        </div>
        <div className="flex gap-2">
          {(room.status === "pending" || room.status === "published") && (
            <>
              <Button loading={approve.isPending} onClick={() => approve.mutate()}>{room.status === "pending" ? "Duyệt" : "Duyệt ảnh"}</Button>
              <Button variant="danger" onClick={() => setRejectOpen(true)}>{room.status === "pending" ? "Từ chối" : "Gỡ tin"}</Button>
            </>
          )}
        </div>
      </div>
      {room.description && <p className="mt-2 line-clamp-3 text-sm text-slate-700">{room.description}</p>}
      <div className="mt-2 flex flex-wrap gap-1">{room.amenities.map((a) => <Badge key={a}>{label(a)}</Badge>)}</div>
      {room.reject_reason && <p className="mt-2 text-sm text-rose-600">Lý do từ chối: {room.reject_reason}</p>}
      {room.images.length > 0 && (
        <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-8">
          {room.images.map((im) => {
            const pending = im.moderation === "pending";
            const ok = okIds.has(im.id);
            return (
              <button key={im.id} type="button" disabled={!pending} onClick={() => toggle(im.id)}
                className={cx("relative overflow-hidden rounded-lg border-2", pending ? (ok ? "border-emerald-500" : "border-rose-400 opacity-60") : "border-transparent")}>
                <img src={im.url} alt="" className="h-20 w-full object-cover" />
                <span className="absolute bottom-0 left-0 right-0 bg-black/50 text-[10px] text-white">
                  {pending ? (ok ? "✓ Đạt" : "✕ Loại") : im.moderation === "ok" ? "Đã duyệt" : "Bị loại"}
                </span>
              </button>
            );
          })}
        </div>
      )}
      {pendingImgs.length > 0 && <p className="mt-1 text-xs text-slate-500">Bấm vào ảnh chờ duyệt để chọn đạt/loại trước khi duyệt.</p>}
      <ErrorBox error={approve.error || reject.error} className="mt-3" />
      <Modal open={rejectOpen} title="Lý do từ chối" onClose={() => setRejectOpen(false)}>
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); reject.mutate(); }}>
          <Textarea rows={3} required minLength={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Ảnh không đúng thực tế, thiếu thông tin giá..." />
          <Button type="submit" variant="danger" className="w-full" loading={reject.isPending}>Xác nhận</Button>
        </form>
      </Modal>
    </Card>
  );
}
