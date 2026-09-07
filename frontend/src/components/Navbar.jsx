// Navbar.jsx — top navigation bar with role-based menu items

import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { useState } from 'react'

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)

  const navClass = ({ isActive }) =>
    `text-sm font-medium transition-colors ${isActive
      ? 'text-white'
      : 'text-blue-200 hover:text-white'}`

  const handleLogout = () => { logout(); navigate('/login') }

  return (
    <nav className="bg-blue-900 shadow-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">

          {/* Brand */}
          <Link to="/" className="flex items-center gap-3">
            <div className="w-8 h-8 bg-emerald-400 rounded-lg flex items-center justify-center">
              <span className="text-blue-900 font-black text-sm">IFM</span>
            </div>
            <div className="hidden sm:block">
              <p className="text-white font-bold text-sm leading-tight">CSO-IDSS</p>
              <p className="text-blue-300 text-xs leading-tight">Campus Space System</p>
            </div>
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-6">
            <NavLink to="/" end className={navClass}>Dashboard</NavLink>
            <NavLink to="/venues" className={navClass}>Live Venues</NavLink>
            <NavLink to="/search" className={navClass}>Search</NavLink>
            <NavLink to="/analytics" className={navClass}>Analytics</NavLink>
            <NavLink to="/forecast" className={navClass}>Forecast</NavLink>
            {user && user.role === 'STUDENT' && (
              <NavLink to="/alarms" className={navClass}>My Alarms</NavLink>
            )}
            {user && user.role !== 'STUDENT' && (<>
              <NavLink to="/staff/book" className={navClass}>Book Venue</NavLink>
              <NavLink to="/staff/bookings" className={navClass}>My Bookings</NavLink>
            </>)}
            {user && ['ADMIN', 'TIMETABLER'].includes(user.role) && (<>
              <NavLink to="/admin/bookings" className={navClass}>All Bookings</NavLink>
              <NavLink to="/admin/venues" className={navClass}>Venues</NavLink>
            </>)}
          </div>

          {/* User */}
          <div className="flex items-center gap-3">
            {user ? (
              <div className="flex items-center gap-2">
                <div className="text-right hidden sm:block">
                  <p className="text-white text-sm font-medium leading-tight">{user.name}</p>
                  <p className="text-blue-300 text-xs leading-tight capitalize">{user.role.toLowerCase()}</p>
                </div>
                <button onClick={handleLogout}
                  className="text-xs text-blue-200 hover:text-white border border-blue-600 hover:border-blue-400 rounded-lg px-3 py-1.5 transition-colors">
                  Logout
                </button>
              </div>
            ) : (
              <Link to="/login"
                className="text-sm font-medium bg-emerald-500 hover:bg-emerald-400 text-white px-4 py-2 rounded-lg transition-colors">
                Sign in
              </Link>
            )}

            {/* Mobile menu button */}
            <button className="md:hidden text-blue-200 hover:text-white p-1" onClick={() => setMenuOpen(!menuOpen)}>
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d={menuOpen ? "M6 18L18 6M6 6l12 12" : "M4 6h16M4 12h16M4 18h16"} />
              </svg>
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {menuOpen && (
          <div className="md:hidden pb-3 pt-1 border-t border-blue-800 flex flex-col gap-2">
            <NavLink to="/" end className={navClass} onClick={() => setMenuOpen(false)}>Dashboard</NavLink>
            <NavLink to="/venues" className={navClass} onClick={() => setMenuOpen(false)}>Live Venues</NavLink>
            <NavLink to="/search" className={navClass} onClick={() => setMenuOpen(false)}>Search</NavLink>
            <NavLink to="/analytics" className={navClass} onClick={() => setMenuOpen(false)}>Analytics</NavLink>
            <NavLink to="/forecast" className={navClass} onClick={() => setMenuOpen(false)}>Forecast</NavLink>
            {user && user.role === 'STUDENT' && (
              <NavLink to="/alarms" className={navClass} onClick={() => setMenuOpen(false)}>My Alarms</NavLink>
            )}
            {user && user.role !== 'STUDENT' && (<>
              <NavLink to="/staff/book" className={navClass} onClick={() => setMenuOpen(false)}>Book Venue</NavLink>
              <NavLink to="/staff/bookings" className={navClass} onClick={() => setMenuOpen(false)}>My Bookings</NavLink>
            </>)}
            {user && ['ADMIN', 'TIMETABLER'].includes(user.role) && (<>
              <NavLink to="/admin/bookings" className={navClass} onClick={() => setMenuOpen(false)}>All Bookings</NavLink>
              <NavLink to="/admin/venues" className={navClass} onClick={() => setMenuOpen(false)}>Venues</NavLink>
            </>)}
          </div>
        )}
      </div>
    </nav>
  )
}
