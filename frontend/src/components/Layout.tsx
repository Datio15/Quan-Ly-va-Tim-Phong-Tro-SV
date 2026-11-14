import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { useCompare } from "../lib/compare";
import Logo from "./Logo";
import { cx } from "./ui";

interface NavItem {
  to: string;
  label: string;
}

function navFor(role: string | undefined): NavItem[] {
  const common = [{ to: "/", label: "Tìm phòng" }];
  if (role === "student") return [...common, { to: "/favorites", label: "Yêu thích" }, { to: "/bookings", label: "Lịch xem" }];
  if (role === "landlord")
    return [
      { to: "/landlord/rooms", label: "Phòng" },
      { to: "/landlord/houses", label: "Nhà trọ" },
      { to: "/bookings", label: "Lịch xem" },
      { to: "/landlord/tenants", label: "Khách thuê" },
      { to: "/landlord/invoices", label: "Hóa đơn" },
    ];
  if (role === "admin")
    return [
      { to: "/admin/moderation", label: "Duyệt tin" },
      { to: "/admin/reports", label: "Báo cáo" },
      { to: "/admin/landlords", label: "Chủ trọ" },
      { to: "/admin/system", label: "Hệ thống" },
      ...common,
    ];
  return common;
}

export default function Layout() {
  const { user, logout } = useAuth();
  const compare = useCompare();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const items = navFor(user?.role);

  const linkCls = ({ isActive }: { isActive: boolean }) =>
    cx("rounded-lg px-3 py-2 text-sm font-medium", isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100");

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4">
          <Link to="/" className="shrink-0" aria-label="EasyRent – trang chủ">
            <Logo size="sm" />
          </Link>
          <nav className="ml-4 hidden flex-1 items-center gap-1 md:flex">
            {items.map((i) => (
              <NavLink key={i.to} to={i.to} end={i.to === "/"} className={linkCls}>
                {i.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {user ? (
              <>
                <NavLink to="/profile" className="hidden max-w-[12rem] truncate rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 sm:block">
                  {user.full_name}
                </NavLink>
                <button
                  className="hidden rounded-lg px-3 py-2 text-sm text-slate-500 hover:bg-slate-100 md:block"
                  onClick={() => {
                    logout();
                    navigate("/");
                  }}
                >
                  Đăng xuất
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100">Đăng nhập</Link>
                <Link to="/register" className="hidden rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700 sm:block">Đăng ký</Link>
              </>
            )}
            <button className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 md:hidden" onClick={() => setOpen(!open)} aria-label="Menu">
              ☰
            </button>
          </div>
        </div>
        {open && (
          <nav className="border-t border-slate-100 px-4 py-2 md:hidden" onClick={() => setOpen(false)}>
            {items.map((i) => (
              <NavLink key={i.to} to={i.to} end={i.to === "/"} className={({ isActive }) => cx(linkCls({ isActive }), "block")}>
                {i.label}
              </NavLink>
            ))}
            {user && (
              <>
                <NavLink to="/profile" className={({ isActive }) => cx(linkCls({ isActive }), "block")}>Hồ sơ</NavLink>
                <button className="block w-full rounded-lg px-3 py-2 text-left text-sm text-slate-600 hover:bg-slate-100" onClick={() => { logout(); navigate("/"); }}>
                  Đăng xuất
                </button>
              </>
            )}
          </nav>
        )}
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
        <Outlet />
      </main>

      {compare.items.length > 0 && (
        <div className="sticky bottom-0 z-30 border-t border-slate-200 bg-white/95 shadow-[0_-4px_12px_rgba(0,0,0,0.05)] backdrop-blur">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-2 px-4 py-3 text-sm">
            <span className="font-medium">So sánh ({compare.items.length}/3):</span>
            {compare.items.map((i) => (
              <span key={i.id} className="flex max-w-[14rem] items-center gap-1 truncate rounded-full bg-slate-100 px-3 py-1">
                <span className="truncate">{i.title}</span>
                <button className="text-slate-400 hover:text-rose-600" onClick={() => compare.toggle(i)} aria-label="Bỏ">✕</button>
              </span>
            ))}
            <div className="ml-auto flex gap-2">
              <button className="rounded-lg px-3 py-1.5 text-slate-500 hover:bg-slate-100" onClick={compare.clear}>Xóa</button>
              <button
                disabled={compare.items.length < 2}
                className="rounded-lg bg-brand-600 px-3 py-1.5 font-medium text-white disabled:opacity-50"
                onClick={() => navigate("/compare")}
              >
                So sánh ngay
              </button>
            </div>
          </div>
        </div>
      )}

      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-400">
        <b className="text-brand-700">Easy</b><b className="text-accent-500">Rent</b> – Quản lý phòng trọ dễ dàng · Bài tập lớn Điện toán đám mây (OpenStack + Azure) · Dữ liệu giả phục vụ demo
      </footer>
    </div>
  );
}
