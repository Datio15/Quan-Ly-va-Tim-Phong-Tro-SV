
import { Routes, Route } from 'react-router-dom'

import Layout from './components/Layout'
import Search from './pages/Search'
import RoomDetail from './pages/RoomDetail'
import Compare from './pages/Compare'
import MyBookings from './pages/MyBookings'
import Favorites from './pages/Favorites'
import Login from './pages/Login'
import Register from './pages/Register'
import Profile from './pages/Profile'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Search />} />
        <Route path="/rooms/:id" element={<RoomDetail />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/me/bookings" element={<MyBookings />} />
        <Route path="/me/favorites" element={<Favorites />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/profile" element={<Profile />} />
        <Route
          path="*"
          element={<h1>Không tìm thấy trang</h1>}
        />
      </Route>
    </Routes>
  )
}
