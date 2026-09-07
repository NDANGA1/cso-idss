// Dashboard.jsx
// This is the landing page after login. I show live venue cards here,
// pulling data every 8 seconds to keep occupancy counts up to date.

import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Layout from '../components/Layout.jsx'
import VenueCard from '../components/VenueCard.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import { venuesApi } from '../api/venues.js'
import { alarmsApi } from '../api/alarms.js'
import { useAuth } from '../context/AuthContext.jsx'

const REFRESH_MS = 15_000

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [venues, setVenues] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('ALL')    // ALL | GREEN | RED
  const [alarmMsg, setAlarmMsg] = useState('')
  const [lastRefresh, setLastRefresh] = useState(null)

  const fetchData = useCallback(async () => {
    try {
      const [v, s] = await Promise.all([venuesApi.getLive(), venuesApi.getSummary()])
      setVenues(v)
      setSummary(s)
      setLastRefresh(new Date())
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const t = setInterval(fetchData, REFRESH_MS)
    return () => clearInterval(t)
  }, [fetchData])

  const handleAlarm = async (venue) => {
    if (!user) { navigate('/login?next=/alarms'); return }
    try {
      await alarmsApi.create(venue.venue_id, `Notify me when ${venue.venue_name} is free`)
      setAlarmMsg(`Alarm set for ${venue.venue_name}`)
      setTimeout(() => setAlarmMsg(''), 3000)
    } catch (e) {
      setAlarmMsg(e.message)
      setTimeout(() => setAlarmMsg(''), 3000)
    }
  }

  const filtered = filter === 'ALL' ? venues
    : filter === 'RED' ? venues.filter(v => v.availability_state === 'RED' || v.availability_state === 'FULL')
    : venues.filter(v => v.availability_state === filter)

  if (loading) return <Layout><LoadingSpinner message="Loading campus data..." /></Layout>

  return (
    <Layout>
      {/* Toast */}
      {alarmMsg && (
        <div className="fixed top-20 right-4 z-50 bg-blue-700 text-white text-sm font-medium px-4 py-3 rounded-xl shadow-lg">
          {alarmMsg}
        </div>
      )}

      {/* Hero summary */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          <SummaryCard label="Total Venues" value={summary.total_venues} color="blue" />
          <SummaryCard label="Available Now" value={summary.available} color="emerald" />
          <SummaryCard label="Occupied" value={summary.occupied} color="red" />
          <SummaryCard label="Campus Availability" value={`${summary.availability_percentage}%`} color="indigo" />
        </div>
      )}

      {/* CCTV banner */}
      <div className="bg-gradient-to-r from-blue-900 to-blue-700 rounded-2xl px-6 py-4 mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-blue-800 rounded-xl flex items-center justify-center flex-shrink-0">
            <svg className="w-5 h-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M15 10l4.553-2.069A1 1 0 0121 8.882v6.236a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </div>
          <div>
            <p className="text-white font-semibold text-sm">AI Camera Integration</p>
            <p className="text-blue-300 text-xs">YOLOv8n real-time people detection · CCTV feed coming soon</p>
          </div>
        </div>
        <span className="text-xs font-medium bg-amber-400 text-amber-900 px-3 py-1 rounded-full flex-shrink-0">
          Timetable Mode
        </span>
      </div>

      {/* Filter tabs + quick search */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
        <div className="flex gap-2">
          {['ALL', 'GREEN', 'RED'].map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                filter === f
                  ? f === 'GREEN' ? 'bg-emerald-500 text-white'
                    : f === 'RED' ? 'bg-red-500 text-white'
                    : 'bg-blue-900 text-white'
                  : 'bg-white text-gray-600 border border-gray-200 hover:border-gray-300'
              }`}>
              {f === 'ALL' ? `All (${venues.length})`
                : f === 'GREEN' ? `Available (${venues.filter(v => v.availability_state === 'GREEN').length})`
                : `Occupied (${venues.filter(v => v.availability_state === 'RED' || v.availability_state === 'FULL').length})`}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="text-xs text-gray-400">
              Updated {lastRefresh.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          )}
          <Link to="/search"
            className="text-sm font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 px-4 py-2 rounded-lg transition-colors">
            Advanced Search →
          </Link>
        </div>
      </div>

      {/* Venue grid */}
      {filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400">No venues match this filter.</div>
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

function SummaryCard({ label, value, color }) {
  const colors = {
    blue: 'bg-blue-50 text-blue-700 border-blue-100',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-100',
    red: 'bg-red-50 text-red-700 border-red-100',
    indigo: 'bg-indigo-50 text-indigo-700 border-indigo-100',
  }
  return (
    <div className={`card p-4 border ${colors[color]}`}>
      <p className="text-2xl font-black">{value}</p>
      <p className="text-xs font-medium mt-1 opacity-80">{label}</p>
    </div>
  )
}
