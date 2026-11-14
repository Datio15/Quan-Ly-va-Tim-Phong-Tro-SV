import { useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "../api/client";
import type { RoomDetail, ReviewPage } from "../api/types";
import CostTable from "../components/CostTable";
import MapView from "../components/MapView";
import { RoomThumb } from "../components/RoomCard";
import { Badge, Button, Card, ErrorBox, Field, Input, Loading, Modal, Notice, Pagination, Select, Stars, Textarea, cx } from "../components/ui";
import { useAuth } from "../lib/auth";
import { useAmenityLabels, useSchools } from "../lib/catalog";
import { useCompare } from "../lib/compare";
import { date, dateTime, distance, localInputToIso, vnInputValue, vnd } from "../lib/format";

export default function RoomDetailPage() {
  const { id = "" } = useParams();
  const { user } = useAuth();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const label = useAmenityLabels();
  const compare = useCompare();
  const { data: schools } = useSchools();
  const [schoolId, setSchoolId] = useState("");
  const [imgIdx, setImgIdx] = useState(0);
  const [bookingOpen, setBookingOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);

  const room = useQuery({
    queryKey: ["room", id, schoolId],
    queryFn: () => api<RoomDetail>(`/rooms/${id}`, { query: { school_id: schoolId || undefined } }),
  });

  const fav = useMutation({
    mutationFn: (on: boolean) => api(`/favorites/${id}`, { method: on ? "PUT" : "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["room", id] });
      qc.invalidateQueries({ queryKey: ["favorites"] });
    },
  });

  if (room.isLoading) return <Loading />;
  if (room.error) return <ErrorBox error={room.error} />;
  const r = room.data!;
  const school = schools?.find((s) => s.id === schoolId) || null;
  const isStudent = user?.role === "student";

  return (
    <div className="space-y-5">
      <button className="text-sm text-slate-500 hover:text-brand-700" onClick={() => navigate(-1)}>‹ Quay lại</button>

      <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
        <div className="space-y-5">
          <Card className="!p-0 overflow-hidden">
            <div className="relative aspect-[16/9] bg-slate-100">
              <RoomThumb url={r.images[imgIdx]?.url || r.thumbnail_url} title={r.title} />
              {r.images.length > 1 && (
                <>
                  <button className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-white/80 px-3 py-1 text-lg" onClick={() => setImgIdx((imgIdx - 1 + r.images.length) % r.images.length)}>‹</button>
                  <button className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-white/80 px-3 py-1 text-lg" onClick={() => setImgIdx((imgIdx + 1) % r.images.length)}>›</button>
                  <span className="absolute bottom-2 right-2 rounded bg-black/50 px-2 py-0.5 text-xs text-white">{imgIdx + 1}/{r.images.length}</span>
                </>
              )}
            </div>
            {r.images.length > 1 && (
              <div className="flex gap-2 overflow-x-auto p-2">
                {r.images.map((im, i) => (
                  <button key={im.id} className={cx("h-14 w-20 shrink-0 overflow-hidden rounded border-2", i === imgIdx ? "border-brand-600" : "border-transparent")} onClick={() => setImgIdx(i)}>
                    <img src={im.url} alt="" className="h-full w-full object-cover" />
                  </button>
                ))}
              </div>
            )}
          </Card>

          <Card>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h1 className="text-xl font-bold sm:text-2xl">{r.title}</h1>
                <p className="mt-1 text-slate-500">{r.street}, {r.ward}, {r.area}, {r.city}</p>
              </div>
              {r.landlord_verified && <Badge tone="green">✓ Chủ trọ đã xác minh</Badge>}
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <Info label="Giá phòng" value={<span className="font-bold text-accent-600">{vnd(r.price_month)}</span>} />
              <Info label="Đặt cọc" value={vnd(r.deposit_amount)} />
              <Info label="Diện tích" value={`${r.area_m2} m²`} />
              <Info label="Tối đa" value={`${r.max_people} người`} />
              <Info label="Tầng" value={r.floor ?? "–"} />
              <Info label="Giờ giấc" value={r.curfew ? `Đóng cửa ${r.curfew_time}` : "Tự do"} />
              <Info label="Trống từ" value={r.available_from ? date(r.available_from) : "Ngay"} />
              <Info label="Đánh giá" value={<span><Stars value={r.rating_avg} size="text-sm" /> {r.rating_count > 0 && `(${r.rating_count})`}</span>} />
            </div>
            <div className="mt-4 flex flex-wrap gap-1.5">
              {r.amenities.map((a) => <Badge key={a} tone="blue">{label(a)}</Badge>)}
            </div>
            {r.description && <p className="mt-4 whitespace-pre-line text-slate-700">{r.description}</p>}
          </Card>

          <Card>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold">Vị trí {school && r.distance_m !== null && <span className="font-normal text-brand-700">· cách {school.short_name} {distance(r.distance_m)}</span>}</h2>
              <Select value={schoolId} onChange={(e) => setSchoolId(e.target.value)} className="!w-auto">
                <option value="">Khoảng cách tới trường...</option>
                {schools?.map((s) => <option key={s.id} value={s.id}>{s.short_name}</option>)}
              </Select>
            </div>
            <MapView rooms={[r]} school={school} className="h-72" />
            <p className="mt-2 text-xs text-slate-500">Địa chỉ chi tiết (số nhà, ngõ) được gửi khi chủ trọ xác nhận lịch xem phòng.</p>
          </Card>

          <Reviews roomId={id} />
        </div>

        <div className="space-y-5">
          <Card className="lg:sticky lg:top-20">
            <h2 className="mb-3 font-semibold">Chi phí thực tế mỗi tháng</h2>
            <CostTable roomId={id} />
            <div className="mt-4 grid gap-2">
              {isStudent && <Button onClick={() => setBookingOpen(true)}>📅 Đặt lịch xem phòng</Button>}
              {!user && <Button onClick={() => navigate("/login", { state: { from: `/rooms/${id}` } })}>Đăng nhập để đặt lịch xem</Button>}
              <div className="grid grid-cols-2 gap-2">
                {isStudent && (
                  <Button variant="secondary" loading={fav.isPending} onClick={() => fav.mutate(!r.is_favorite)}>
                    {r.is_favorite ? "♥ Đã thích" : "♡ Yêu thích"}
                  </Button>
                )}
                <Button variant="secondary" className={cx(!isStudent && "col-span-2")}
                  onClick={() => { if (!compare.toggle({ id: r.id, title: r.title })) alert("Chỉ so sánh tối đa 3 phòng"); }}>
                  {compare.has(r.id) ? "✓ Đang so sánh" : "+ So sánh"}
                </Button>
              </div>
              {isStudent && <button className="text-xs text-slate-400 hover:text-rose-600" onClick={() => setReportOpen(true)}>Báo cáo tin đăng sai</button>}
            </div>
          </Card>
        </div>
      </div>

      <BookingModal open={bookingOpen} onClose={() => setBookingOpen(false)} roomId={id} />
      <ReportModal open={reportOpen} onClose={() => setReportOpen(false)} targetType="room" targetId={id} />
    </div>
  );
}

function Info({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="font-medium">{value}</div>
    </div>
  );
}

function BookingModal({ open, onClose, roomId }: { open: boolean; onClose: () => void; roomId: string }) {
  const [slot, setSlot] = useState(vnInputValue(26).slice(0, 14) + "00");
  const [note, setNote] = useState("");
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: () => api("/bookings", { body: { room_id: roomId, slot_start: localInputToIso(slot), student_note: note || null } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bookings"] }),
  });
  return (
    <Modal open={open} title="Đặt lịch xem phòng" onClose={() => { m.reset(); onClose(); }}>
      {m.isSuccess ? (
        <div className="space-y-4">
          <Notice tone="success">Đã gửi yêu cầu. Chủ trọ sẽ xác nhận hoặc từ chối; bạn theo dõi ở mục <Link className="underline" to="/bookings">Lịch xem</Link>.</Notice>
          <Button className="w-full" onClick={() => { m.reset(); onClose(); }}>Đóng</Button>
        </div>
      ) : (
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
          <Field label="Thời gian (giờ Việt Nam)" hint="Cách hiện tại ít nhất 2 giờ, tối đa 14 ngày tới.">
            <Input type="datetime-local" required value={slot} min={vnInputValue(2)} max={vnInputValue(24 * 14)} step={900} onChange={(e) => setSlot(e.target.value)} />
          </Field>
          <Field label="Ghi chú cho chủ trọ (tùy chọn)">
            <Textarea rows={2} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Em đi cùng bạn..." />
          </Field>
          <ErrorBox error={m.error} />
          <Button type="submit" className="w-full" loading={m.isPending}>Gửi yêu cầu</Button>
        </form>
      )}
    </Modal>
  );
}

export function ReportModal({ open, onClose, targetType, targetId }: { open: boolean; onClose: () => void; targetType: "room" | "review"; targetId: string }) {
  const [reason, setReason] = useState("");
  const m = useMutation({ mutationFn: () => api("/reports", { body: { target_type: targetType, target_id: targetId, reason } }) });
  return (
    <Modal open={open} title={targetType === "room" ? "Báo cáo tin đăng" : "Báo cáo đánh giá"} onClose={() => { m.reset(); setReason(""); onClose(); }}>
      {m.isSuccess ? (
        <Notice tone="success">Cảm ơn bạn, quản trị viên sẽ xem xét.</Notice>
      ) : (
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
          <Textarea rows={3} required minLength={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Lý do (thông tin sai, lừa đảo, ngôn từ không phù hợp...)" />
          <ErrorBox error={m.error} />
          <Button type="submit" variant="danger" className="w-full" loading={m.isPending}>Gửi báo cáo</Button>
        </form>
      )}
    </Modal>
  );
}

function Reviews({ roomId }: { roomId: string }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [editing, setEditing] = useState(false);
  const [reportId, setReportId] = useState<string | null>(null);

  const q = useQuery({
    queryKey: ["reviews", roomId, page, user?.id],
    queryFn: () => api<ReviewPage>(`/rooms/${roomId}/reviews`, { query: { page, page_size: 5 } }),
  });
  const save = useMutation({
    mutationFn: () => api(`/rooms/${roomId}/review`, { method: "PUT", body: { rating, comment } }),
    onSuccess: () => {
      setEditing(false);
      qc.invalidateQueries({ queryKey: ["reviews", roomId] });
      qc.invalidateQueries({ queryKey: ["room", roomId] });
    },
  });

  const data = q.data;
  const mine = data?.my_review;
  const showForm = user?.role === "student" && data?.can_review && (!mine || editing);

  return (
    <Card>
      <h2 className="mb-3 font-semibold">Đánh giá {data && `(${data.total})`}</h2>
      {user?.role === "student" && data && !data.can_review && !mine && (
        <p className="mb-3 text-sm text-slate-500">Bạn có thể đánh giá sau khi đã đi xem phòng (lịch được chủ trọ đánh dấu “Đã xem”).</p>
      )}
      {mine && !editing && (
        <div className="mb-3 rounded-lg bg-brand-50 p-3 text-sm">
          <div className="flex items-center justify-between">
            <span>Đánh giá của bạn: <Stars value={mine.rating} size="text-sm" /> {mine.is_hidden && <Badge tone="red">Đã bị ẩn</Badge>}</span>
            <button className="text-brand-700 underline" onClick={() => { setRating(mine.rating); setComment(mine.comment); setEditing(true); }}>Sửa</button>
          </div>
          {mine.comment && <p className="mt-1 text-slate-700">{mine.comment}</p>}
        </div>
      )}
      {showForm && (
        <form className="mb-4 space-y-2 rounded-lg border border-slate-200 p-3" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
          <div className="flex items-center gap-1 text-2xl">
            {[1, 2, 3, 4, 5].map((n) => (
              <button type="button" key={n} className={n <= rating ? "text-amber-500" : "text-slate-300"} onClick={() => setRating(n)}>★</button>
            ))}
          </div>
          <Textarea rows={2} maxLength={2000} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Chia sẻ trải nghiệm của bạn..." />
          <ErrorBox error={save.error} />
          <div className="flex gap-2">
            <Button type="submit" loading={save.isPending}>Lưu đánh giá</Button>
            {editing && <Button type="button" variant="ghost" onClick={() => setEditing(false)}>Hủy</Button>}
          </div>
        </form>
      )}
      {q.error && <p className="text-sm text-rose-600">{errorMessage(q.error)}</p>}
      <div className="divide-y divide-slate-100">
        {data?.items.map((rv) => (
          <div key={rv.id} className="py-3 text-sm">
            <div className="flex items-center justify-between">
              <span><b>{rv.student_name}</b> <Stars value={rv.rating} size="text-sm" /></span>
              <span className="text-xs text-slate-400">{dateTime(rv.created_at)}</span>
            </div>
            {rv.comment && <p className="mt-1 text-slate-700">{rv.comment}</p>}
            {user?.role === "student" && !rv.is_mine && (
              <button className="mt-1 text-xs text-slate-400 hover:text-rose-600" onClick={() => setReportId(rv.id)}>Báo cáo đánh giá sai</button>
            )}
          </div>
        ))}
        {data && data.items.length === 0 && <p className="py-3 text-sm text-slate-500">Chưa có đánh giá nào.</p>}
      </div>
      {data && <Pagination page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />}
      <ReportModal open={!!reportId} onClose={() => setReportId(null)} targetType="review" targetId={reportId || ""} />
    </Card>
  );
}
