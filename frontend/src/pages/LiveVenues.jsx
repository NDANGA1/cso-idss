// LiveVenues.jsx — shows all venues with live occupancy states

import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout.jsx'
import VenueCard from '../components/VenueCard.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import EmptyState from '../components/EmptyState.jsx'
import { venuesApi } from '../api/venues.js'
import { alarmsApi } from '../api/alarms.js'
import { useAuth } from '../context/AuthContext.jsx'
import { useNavigate } from 'react-router-dom'

const REFRESH_MS = 15_000

export default function LiveVenues() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [venues, setVenues] = useState([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [minCapacity, setMinCapacity] = useState('')
  const [search, setSearch] = useState('')
  const [toast, setToast] = useState('')
  const [lastRefresh, setLastRefresh] = useState(null)
  const [calendarPeriod, setCalendarPeriod] = useState(null)

  const fetchVenues = useCallback(async () => {
    try {
      const data = await venuesApi.getLive()
      setVenues(data)
      setLastRefresh(new Date())
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const base = import.meta.env.VITE_API_URL || '/api'
    fetch(`${base}/calendar/period`)
      .then(r => r.json())
      .then(setCalendarPeriod)
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetchVenues()
    const t = setInterval(fetchVenues, REFRESH_MS)
    return () => clearInterval(t)
  }, [fetchVenues])

  const handleAlarm = async (venue) => {
    if (!user) { navigate('/login'); return }
    try {
      await alarmsApi.create(venue.venue_id, `Notify me when ${venue.venue_name} is free`)
      setToast(`Alarm set for ${venue.venue_name}`)
    } catch (e) {
      setToast(e.message)
    }
    setTimeout(() => setToast(''), 3000)
  }

  const filtered = venues.filter(v => {
    if (statusFilter === 'RED' && v.availability_state !== 'RED' && v.availability_state !== 'FULL') return false
    if (statusFilter !== 'ALL' && statusFilter !== 'RED' && v.availability_state !== statusFilter) return false
    if (minCapacity && v.capacity < Number(minCapacity)) return false
    if (search && !v.venue_name.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  if (loading) return <Layout><LoadingSpinner message="Loading live venue data..." /></Layout>

  return (
    <Layout>
      {toast && (
        <div className="fixed top-20 right-4 z-50 bg-blue-700 text-white text-sm font-medium px-4 py-3 rounded-xl shadow-lg">
          {toast}
        </div>
      )}

      {/* Academic break banner */}
      {calendarPeriod?.is_break && (
        <div className="mb-5 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <span className="text-lg leading-none"></span>
          <div>
            <span className="font-semibold">{calendarPeriod.period}</span>
            <span className="ml-2 text-amber-700">— Timetable bookings are paused. Venues show real occupancy only; status turns RED only when booked through the system.</span>
          </div>
        </div>
      )}

      <div className="flex items-end justify-between mb-6">
        <div>
          <h1 className="text-2xl font-black text-gray-900">Live Venues</h1>
          <p className="text-sm text-gray-500 mt-1">Real-time availability across all IFM spaces · auto-refreshes every 15s</p>
        </div>
        {lastRefresh && (
          <span className="text-xs text-gray-400">
            Updated {lastRefresh.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
        )}
      </div>

      {/* Filters */}
      <div className="card p-4 mb-6 flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          placeholder="Search venue name..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <input
          type="number"
          placeholder="Min capacity"
          value={minCapacity}
          onChange={e => setMinCapacity(e.target.value)}
          className="w-36 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <div className="flex gap-2">
          {['ALL', 'GREEN', 'RED'].map(s => (
            <button key={s} onClick={() => setStatusFilter(s)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                statusFilter === s
                  ? s === 'GREEN' ? 'bg-emerald-500 text-white'
                    : s === 'RED' ? 'bg-red-500 text-white'
                    : 'bg-blue-900 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}>
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Result count */}
      <p className="text-xs text-gray-400 mb-3">
        Showing {filtered.length} of {venues.length} venues
      </p>

      {filtered.length === 0 ? (
        <EmptyState title="No venues found" message="Try adjusting your filters." />
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {filtered.map(v => (
            <VenueCard key={v.venue_id} venue={v} onAlarm={handleAlarm} />
          ))}
        </div>
      )}
    </Layout>
  )
}
