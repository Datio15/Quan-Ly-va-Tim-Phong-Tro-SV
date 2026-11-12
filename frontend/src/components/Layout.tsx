
import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'

const menuItems = [
  { to: '/', label: 'Tìm phòng' },
  { to: '/compare', label: 'So sánh' },
  { to: '/me/favorites', label: 'Yêu thích' },
  { to: '/me/bookings', label: 'Đặt phòng' },
]

export default function Layout() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <header className="bg-white shadow-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between p-4">

          <Link to="/" className="text-2xl font-bold text-blue-600">
            EasyRent
          </Link>

          <nav className="hidden items-center gap-6 md:flex">
            {menuItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  isActive ? 'font-semibold text-blue-600' : 'hover:text-blue-600'
                }
              >
                {item.label}
              </NavLink>
            ))}

            <Link to="/login" className="rounded-lg bg-blue-600 px-4 py-2 text-white">
              Đăng nhập
            </Link>
          </nav>

          <button
            type="button"
            className="md:hidden"
            aria-label="Mở menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen(!menuOpen)}
          >
            ☰
          </button>
        </div>

        {menuOpen && (
          <nav className="flex flex-col gap-3 border-t p-4 md:hidden">
            {menuItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMenuOpen(false)}
              >
                {item.label}
              </NavLink>
            ))}
            <Link to="/login" onClick={() => setMenuOpen(false)}>
              Đăng nhập
            </Link>
          </nav>
        )}
      </header>

      <main className="mx-auto max-w-6xl p-6">
        <Outlet />
      </main>
    </div>
  )
}
