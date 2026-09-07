// ManageBookings.jsx — admin view of all bookings with edit/delete

import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import Layout from '../../components/Layout.jsx'
import LoadingSpinner from '../../components/LoadingSpinner.jsx'
import { bookingsApi } from '../../api/bookings.js'
import { venuesApi } from '../../api/venues.js'
import { useAuth } from '../../context/AuthContext.jsx'

const DAYS = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']
const ADMIN_ROLES = ['ADMIN', 'TIMETABLER']

export default function ManageBookings() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [bookings, setBookings] = useState([])
  const [venues, setVenues] = useState([])
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState({ msg: '', ok: true })

  const [search, setSearch] = useState('')
  const [filterDay, setFilterDay] = useState('')
  const [filterVenue, setFilterVenue] = useState('')
  const [filterStatus, setFilterStatus] = useState('ACTIVE')

  useEffect(() => {
    if (!user) { navigate('/login'); return }
    if (!ADMIN_ROLES.includes(user.role)) { navigate('/'); return }
    Promise.all([fetchBookings(), venuesApi.getLive().then(setVenues)]).finally(() => setLoading(false))
  }, [user])

  const fetchBookings = async () => {
    const data = await bookingsApi.all({ day: filterDay, venue_id: filterVenue, status: filterStatus, search })
    setBookings(data)
  }

  useEffect(() => { if (!loading) fetchBookings() }, [filterDay, filterVenue, filterStatus, search])

  const showToast = (msg, ok = true) => {
    setToast({ msg, ok })
    setTimeout(() => setToast({ msg: '', ok: true }), 3000)
  }

  const handleCancel = async (id, label) => {
    if (!confirm(`Cancel "${label}"?`)) return
    try {
      await bookingsApi.cancel(id)
      setBookings(prev => prev.map(b => b.id === id ? { ...b, status: 'CANCELLED' } : b))
      showToast('Booking cancelled.')
    } catch (e) { showToast(e.message, false) }
  }

  const statusColor = (s) => ({
    ACTIVE: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    COMPLETED: 'bg-gray-100 text-gray-500 border-gray-200',
    CANCELLED: 'bg-red-50 text-red-600 border-red-200',
  })[s] ?? 'bg-gray-100 text-gray-500 border-gray-200'

  if (loading) return <Layout><LoadingSpinner message="Loading bookings..." /></Layout>

  const active = bookings.filter(b => b.status === 'ACTIVE').length

  return (
    <Layout>
      {toast.msg && (
        <div className={`fixed top-20 right-4 z-50 text-white text-sm font-medium px-4 py-3 rounded-xl shadow-lg ${toast.ok ? 'bg-blue-700' : 'bg-red-600'}`}>
          {toast.msg}
        </div>
      )}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-black text-gray-900">Manage Bookings</h1>
          <p className="text-sm text-gray-500 mt-1">{active} active · {bookings.length} shown</p>
        </div>
        <Link to="/staff/book"
          className="bg-blue-900 hover:bg-blue-800 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors">
          + New Booking
        </Link>
      </div>

      {/* Filters */}
      <div className="card p-4 mb-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
        <input
          type="text" placeholder="Search venue, course, lecturer..."
          value={search} onChange={e => setSearch(e.target.value)}
          className="col-span-2 sm:col-span-4 border border-gray-200 rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select value={filterDay} onChange={e => setFilterDay(e.target.value)}
          className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">All days</option>
          {DAYS.map(d => <option key={d} value={d}>{d.charAt(0) + d.slice(1).toLowerCase()}</option>)}
        </select>
        <select value={filterVenue} onChange={e => setFilterVenue(e.target.value)}
          className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">All venues</option>
          {venues.map(v => <option key={v.venue_id} value={v.venue_id}>{v.venue_name}</option>)}
        </select>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
          className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">All statuses</option>
          <option value="ACTIVE">Active</option>
          <option value="CANCELLED">Cancelled</option>
          <option value="COMPLETED">Completed</option>
        </select>
        <button onClick={fetchBookings}
          className="bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold text-sm rounded-xl px-4 py-2 transition-colors">
          Refresh
        </button>
      </div>

      {/* Table */}
      {bookings.length === 0 ? (
        <div className="card p-10 text-center text-gray-400 text-sm">No bookings match your filters.</div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  {['Venue', 'Course', 'Day / Date', 'Time', 'Type', 'Booked By', 'Status', ''].map(h => (
                    <th key={h} className="text-left text-xs font-semibold text-gray-500 px-4 py-3 whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {bookings.map(b => (
                  <tr key={b.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-medium text-gray-800 whitespace-nowrap">{b.venue_name || `#${b.venue_id}`}</td>
                    <td className="px-4 py-3 text-gray-600 max-w-[160px] truncate">
                      {[b.course_code, b.course_name].filter(Boolean).join(' · ') || '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                      {b.is_recurring
                        ? <span className="text-blue-600 font-medium">{b.day_of_week?.charAt(0) + b.day_of_week?.slice(1).toLowerCase()} ↻</span>
                        : b.booking_date
                          ? new Date(b.booking_date + 'T00:00:00').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
                          : b.day_of_week}
                    </td>
                    <td className="px-4 py-3 font-mono text-gray-600 whitespace-nowrap">{b.start_time} – {b.end_time}</td>
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap text-xs">{b.booking_type}</td>
                    <td className="px-4 py-3 text-gray-500 max-w-[120px] truncate">{b.holder_name || '—'}</td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${statusColor(b.status)}`}>
                        {b.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {b.status === 'ACTIVE' && (
                        <button
                          onClick={() => handleCancel(b.id, b.course_name || b.venue_name)}
                          className="text-xs font-medium text-red-600 hover:text-red-700 hover:bg-red-50 px-3 py-1.5 rounded-lg transition-colors">
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Layout>
  )
}
