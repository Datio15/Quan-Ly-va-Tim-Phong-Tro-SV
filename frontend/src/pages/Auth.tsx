import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Me, RoomCardData } from "../api/types";
import Logo from "../components/Logo";
import RoomCard from "../components/RoomCard";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Loading, Notice, PageTitle, cx } from "../components/ui";
import { homeFor, useAuth } from "../lib/auth";
import { dateTime } from "../lib/format";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const m = useMutation({
    mutationFn: () => login(email, password),
    onSuccess: (me) => navigate(from || homeFor(me.role), { replace: true }),
  });

  return (
    <div className="mx-auto grid max-w-5xl items-center gap-8 py-6 lg:grid-cols-[1fr_380px]">
      <div className="hidden overflow-hidden rounded-2xl border border-slate-200 shadow-sm lg:block">
        <img src="/brand/easyrent-banner.webp" alt="EasyRent – Quản Lý Phòng Trọ Dễ Dàng" className="h-full w-full object-cover" />
      </div>
      <div>
      <div className="mb-5 flex justify-center lg:hidden"><Logo size="lg" tagline /></div>
      <Card>
        <h1 className="mb-5 text-xl font-semibold">Đăng nhập EasyRent</h1>
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
          <Field label="Email"><Input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
          <Field label="Mật khẩu"><Input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
          <ErrorBox error={m.error} />
          <Button type="submit" className="w-full" loading={m.isPending}>Đăng nhập</Button>
        </form>
        <p className="mt-4 text-center text-sm text-slate-500">Chưa có tài khoản? <Link to="/register" className="text-brand-700 underline">Đăng ký</Link></p>
      </Card>
      <p className="mt-4 text-center text-xs text-slate-400">Tài khoản demo: admin@, chutro1..4@, sinhvien1..6@example.com (mật khẩu SEED_DEMO_PASSWORD)</p>
      </div>
    </div>
  );
}

export function RegisterPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "", full_name: "", phone: "", role: "student" as "student" | "landlord" });
  const m = useMutation({
    mutationFn: async () => {
      await api("/auth/register", { body: { ...form, phone: form.phone || null } });
      return login(form.email, form.password);
    },
    onSuccess: (me) => navigate(homeFor(me.role), { replace: true }),
  });
  const set = (k: keyof typeof form, v: string) => setForm({ ...form, [k]: v });

  return (
    <div className="mx-auto max-w-md py-6">
      <div className="mb-5 flex justify-center"><Logo size="lg" tagline /></div>
      <Card>
        <h1 className="mb-5 text-xl font-semibold">Tạo tài khoản EasyRent</h1>
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
          <div className="grid grid-cols-2 gap-2">
            {(["student", "landlord"] as const).map((r) => (
              <button type="button" key={r} onClick={() => set("role", r)}
                className={cx("rounded-lg border p-3 text-sm", form.role === r ? "border-brand-600 bg-brand-50 font-semibold text-brand-700" : "border-slate-300")}>
                {r === "student" ? "🎓 Sinh viên" : "🏠 Chủ trọ"}
              </button>
            ))}
          </div>
          <Field label="Họ tên"><Input required minLength={2} maxLength={100} value={form.full_name} onChange={(e) => set("full_name", e.target.value)} /></Field>
          <Field label="Email"><Input type="email" required value={form.email} onChange={(e) => set("email", e.target.value)} /></Field>
          <Field label="Số điện thoại (tùy chọn)"><Input inputMode="tel" pattern="\+?[0-9]{9,12}" value={form.phone} onChange={(e) => set("phone", e.target.value)} /></Field>
          <Field label="Mật khẩu" hint="Tối thiểu 8 ký tự"><Input type="password" required minLength={8} autoComplete="new-password" value={form.password} onChange={(e) => set("password", e.target.value)} /></Field>
          <ErrorBox error={m.error} />
          <Button type="submit" className="w-full" loading={m.isPending}>Đăng ký</Button>
        </form>
        <p className="mt-4 text-center text-sm text-slate-500">Đã có tài khoản? <Link to="/login" className="text-brand-700 underline">Đăng nhập</Link></p>
      </Card>
    </div>
  );
}

export function ProfilePage() {
  const { user, refresh } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [phone, setPhone] = useState(user?.phone || "");
  const save = useMutation({
    mutationFn: () => api<Me>("/me", { method: "PATCH", body: { full_name: fullName, phone: phone || null } }),
    onSuccess: () => refresh(),
  });
  const tg = useMutation({ mutationFn: () => api<{ url: string; expires_at: string }>("/me/telegram-link", { method: "POST" }) });
  if (!user) return null;
  const roleLabel = { student: "Sinh viên", landlord: "Chủ trọ", admin: "Quản trị viên" }[user.role];

  return (
    <div className="mx-auto max-w-xl space-y-5">
      <PageTitle>Hồ sơ</PageTitle>
      <Card>
        <div className="mb-4 flex flex-wrap items-center gap-2 text-sm text-slate-600">
          {user.email} <Badge tone="blue">{roleLabel}</Badge>
          {user.role === "landlord" && (user.verified ? <Badge tone="green">Đã xác minh</Badge> : <Badge>Chưa xác minh</Badge>)}
        </div>
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
          <Field label="Họ tên"><Input required minLength={2} value={fullName} onChange={(e) => setFullName(e.target.value)} /></Field>
          <Field label="Số điện thoại"><Input inputMode="tel" pattern="\+?[0-9]{9,12}" value={phone} onChange={(e) => setPhone(e.target.value)} /></Field>
          <ErrorBox error={save.error} />
          {save.isSuccess && <Notice tone="success">Đã lưu.</Notice>}
          <Button type="submit" loading={save.isPending}>Lưu thay đổi</Button>
        </form>
      </Card>
      <Card>
        <h2 className="mb-2 font-semibold">Thông báo Telegram</h2>
        <p className="mb-3 text-sm text-slate-600">
          Nhận nhắc lịch xem phòng{user.role === "landlord" && ", hóa đơn quá hạn, hợp đồng sắp hết hạn"} qua Telegram.
          Trạng thái: {user.telegram_linked ? <Badge tone="green">Đã liên kết</Badge> : <Badge>Chưa liên kết</Badge>}
        </p>
        {tg.data ? (
          <Notice>
            Mở liên kết sau và bấm <b>Start</b> trong Telegram (hạn đến {dateTime(tg.data.expires_at)}):{" "}
            <a href={tg.data.url} target="_blank" rel="noreferrer" className="break-all font-medium underline">{tg.data.url}</a>
            <div className="mt-2"><button className="underline" onClick={() => refresh()}>Tôi đã bấm Start – kiểm tra lại</button></div>
          </Notice>
        ) : (
          <Button variant="secondary" loading={tg.isPending} onClick={() => tg.mutate()}>Nhận thông báo Telegram</Button>
        )}
        <ErrorBox error={tg.error} className="mt-3" />
      </Card>
    </div>
  );
}

export function FavoritesPage() {
  const q = useQuery({ queryKey: ["favorites"], queryFn: () => api<{ items: RoomCardData[] }>("/favorites") });
  const qc = useQueryClient();
  const remove = useMutation({
    mutationFn: (id: string) => api(`/favorites/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["favorites"] }),
  });
  return (
    <div>
      <PageTitle>Phòng yêu thích</PageTitle>
      <ErrorBox error={q.error} />
      {q.isLoading && <Loading />}
      {q.data && q.data.items.length === 0 && <Empty>Chưa có phòng yêu thích. <Link to="/" className="text-brand-700 underline">Tìm phòng</Link></Empty>}
      <div className="space-y-3">
        {q.data?.items.map((r) => (
          <div key={r.id} className="relative">
            <RoomCard room={r} />
            <button className="absolute right-3 top-3 rounded-full bg-white/90 px-2 py-1 text-xs text-rose-600 shadow" onClick={() => remove.mutate(r.id)}>♥ Bỏ thích</button>
          </div>
        ))}
      </div>
    </div>
  );
}
