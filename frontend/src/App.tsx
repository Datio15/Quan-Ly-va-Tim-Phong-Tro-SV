import type { ReactNode } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import type { Role } from "./api/types";
import Layout from "./components/Layout";
import { Loading } from "./components/ui";
import { useAuth } from "./lib/auth";
import { FavoritesPage, LoginPage, ProfilePage, RegisterPage } from "./pages/Auth";
import BookingsPage from "./pages/Bookings";
import ComparePage from "./pages/Compare";
import RoomDetailPage from "./pages/RoomDetail";
import SearchPage from "./pages/Search";
import HousesPage from "./pages/landlord/Houses";
import InvoicesPage from "./pages/landlord/Invoices";
import RoomEditPage from "./pages/landlord/RoomEdit";
import LandlordRoomsPage from "./pages/landlord/Rooms";
import TenantsPage from "./pages/landlord/Tenants";
import ModerationPage from "./pages/admin/Moderation";
import { LandlordsPage, ReportsPage } from "./pages/admin/ReportsLandlords";
import SystemStatusPage from "./pages/admin/SystemStatus";

function RequireRole({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (roles && !roles.includes(user.role)) {
    return <div className="py-16 text-center text-slate-500">Bạn không có quyền xem trang này. <Link className="text-brand-700 underline" to="/">Về trang chủ</Link></div>;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<SearchPage />} />
        <Route path="rooms/:id" element={<RoomDetailPage />} />
        <Route path="compare" element={<ComparePage />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route path="profile" element={<RequireRole><ProfilePage /></RequireRole>} />
        <Route path="favorites" element={<RequireRole roles={["student"]}><FavoritesPage /></RequireRole>} />
        <Route path="bookings" element={<RequireRole roles={["student", "landlord"]}><BookingsPage /></RequireRole>} />

        <Route path="landlord/houses" element={<RequireRole roles={["landlord"]}><HousesPage /></RequireRole>} />
        <Route path="landlord/rooms" element={<RequireRole roles={["landlord"]}><LandlordRoomsPage /></RequireRole>} />
        <Route path="landlord/rooms/:id" element={<RequireRole roles={["landlord"]}><RoomEditPage /></RequireRole>} />
        <Route path="landlord/tenants" element={<RequireRole roles={["landlord"]}><TenantsPage /></RequireRole>} />
        <Route path="landlord/invoices" element={<RequireRole roles={["landlord"]}><InvoicesPage /></RequireRole>} />

        <Route path="admin/moderation" element={<RequireRole roles={["admin"]}><ModerationPage /></RequireRole>} />
        <Route path="admin/reports" element={<RequireRole roles={["admin"]}><ReportsPage /></RequireRole>} />
        <Route path="admin/landlords" element={<RequireRole roles={["admin"]}><LandlordsPage /></RequireRole>} />
        <Route path="admin/system" element={<RequireRole roles={["admin"]}><SystemStatusPage /></RequireRole>} />

        <Route path="*" element={<div className="py-16 text-center text-slate-500">Không tìm thấy trang. <Link className="text-brand-700 underline" to="/">Về trang chủ</Link></div>} />
      </Route>
    </Routes>
  );
}
