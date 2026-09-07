// MyBookings.jsx — shows bookings made by the logged-in staff member

import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import Layout from '../../components/Layout.jsx'
import LoadingSpinner from '../../components/LoadingSpinner.jsx'
import EmptyState from '../../components/EmptyState.jsx'
import { bookingsApi } from '../../api/bookings.js'
import { useAuth } from '../../context/AuthContext.jsx'

export default function MyBookings() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [bookings, setBookings] = useState([])
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState('')

  useEffect(() => {
    if (!user) { navigate('/login'); return }
    if (user.role === 'STUDENT') { navigate('/'); return }
    fetchBookings()
  }, [user])

  const fetchBookings = async () => {
    setLoading(true)
    try {
      const data = await bookingsApi.my()
      setBookings(data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const handleCancel = async (id, name) => {
    if (!confirm(`Cancel booking "${name || 'this booking'}"?`)) return
    try {
      await bookingsApi.cancel(id)
      setBookings(prev => prev.map(b => b.id === id ? { ...b, status: 'CANCELLED' } : b))
      setToast('Booking cancelled.')
    } catch (e) {
      setToast(e.message)
    }
    setTimeout(() => setToast(''), 3000)
  }

  if (loading) return <Layout><LoadingSpinner message="Loading your bookings..." /></Layout>

  const active = bookings.filter(b => b.status === 'ACTIVE')
  const past = bookings.filter(b => b.status !== 'ACTIVE')

  return (
    <Layout>
      {toast && (
        <div className="fixed top-20 right-4 z-50 bg-blue-700 text-white text-sm font-medium px-4 py-3 rounded-xl shadow-lg">
          {toast}
        </div>
      )}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-black text-gray-900">My Bookings</h1>
          <p className="text-sm text-gray-500 mt-1">All bookings you have created</p>
        </div>
        <Link to="/staff/book"
          className="bg-blue-900 hover:bg-blue-800 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors">
          + New Booking
        </Link>
      </div>

      {bookings.length === 0 ? (
        <EmptyState
          title="No bookings yet"
          message="Create your first booking to reserve a venue."
          action={{ label: '+ Create Booking', onClick: () => navigate('/staff/book') }}
        />
      ) : (
        <>
          {active.length > 0 && (
            <section className="mb-6">
              <h2 className="text-sm font-bold text-gray-600 mb-3 uppercase tracking-wide">
                Active ({active.length})
              </h2>
              <div className="flex flex-col gap-3">
                {active.map(b => (
                  <BookingRow key={b.id} booking={b} onCancel={handleCancel} />
                ))}
              </div>
            </section>
          )}
          {past.length > 0 && (
            <section>
              <h2 className="text-sm font-bold text-gray-600 mb-3 uppercase tracking-wide">
                Past / Cancelled ({past.length})
              </h2>
              <div className="flex flex-col gap-3 opacity-60">
                {past.map(b => (
                  <BookingRow key={b.id} booking={b} readonly />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </Layout>
  )
}

function BookingRow({ booking: b, onCancel, readonly = false }) {
  const statusColor = {
    ACTIVE: 'bg-emerald-50 text-emerald-700 border-emerald-100',
    COMPLETED: 'bg-gray-100 text-gray-500 border-gray-200',
    CANCELLED: 'bg-red-50 text-red-600 border-red-100',
  }[b.status] ?? 'bg-gray-100 text-gray-500'

  const borderColor = b.is_recurring ? 'border-l-blue-500' : 'border-l-amber-400'

  return (
    <div className={`card p-4 border-l-4 ${borderColor} flex items-start justify-between gap-4`}>
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${statusColor}`}>
            {b.status}
          </span>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            b.is_recurring
              ? 'bg-blue-50 text-blue-700'
              : 'bg-amber-50 text-amber-700'
          }`}>
            {b.is_recurring ? 'RECURRING' : 'ONE-TIME'}
          </span>
        </div>

        <p className="font-semibold text-gray-800 text-sm leading-tight">
          {b.venue_name || `Venue #${b.venue_id}`}
        </p>
        {(b.course_name || b.course_code) && (
          <p className="text-xs text-gray-500 mt-0.5">
            {[b.course_code, b.course_name].filter(Boolean).join(' · ')}
          </p>
        )}

        <div className="flex flex-wrap gap-3 mt-2 text-xs text-gray-500">
          <span>
            {b.is_recurring
              ? b.day_of_week.charAt(0) + b.day_of_week.slice(1).toLowerCase()
              : b.booking_date
                ? new Date(b.booking_date + 'T00:00:00').toLocaleDateString('en-GB', {
                    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
                  })
                : b.day_of_week}
          </span>
          <span className="font-mono">{b.start_time} – {b.end_time}</span>
        </div>
      </div>

      {!readonly && b.status === 'ACTIVE' && (
        <button
          onClick={() => onCancel(b.id, b.course_name || b.venue_name)}
          className="flex-shrink-0 text-xs font-medium text-red-600 hover:text-red-700 hover:bg-red-50 px-3 py-1.5 rounded-lg transition-colors">
          Cancel
        </button>
      )}
    </div>
  )
}
