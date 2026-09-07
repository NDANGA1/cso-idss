// Search.jsx
// Let users filter venues by day, time and availability.
// I added day-of-week pills and time range inputs to narrow results.

import { useState, useEffect, useRef } from 'react'
import Layout from '../components/Layout.jsx'
import VenueCard from '../components/VenueCard.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import EmptyState from '../components/EmptyState.jsx'
import { venuesApi } from '../api/venues.js'
import { alarmsApi } from '../api/alarms.js'
import { useAuth } from '../context/AuthContext.jsx'
import { useNavigate } from 'react-router-dom'

const DAYS = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']

function todayName() {
  return DAYS[new Date().getDay() === 0 ? 6 : new Date().getDay() - 1]
}

function nowTime() {
  const now = new Date()
  return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
}

export default function Search() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    day: todayName(),
    time: nowTime(),
    min_capacity: '',
    min_availability: '',
    status: '',
    available_now: false,
  })
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const lastParamsRef = useRef(null)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const runSearch = async (params, showLoading = true) => {
    if (showLoading) setLoading(true)
    setError('')
    try {
      const data = await venuesApi.search(params)
      setResults(data)
    } catch (e) {
      setError(e.message)
    } finally {
      if (showLoading) setLoading(false)
    }
  }

  const handleSearch = async (e) => {
    e.preventDefault()
    const params = {}
    if (form.day) params.day = form.day
    if (form.time) params.time = form.time
    if (form.min_capacity) params.min_capacity = Number(form.min_capacity)
    if (form.min_availability) params.min_availability = Number(form.min_availability)
    if (form.status) params.status = form.status
    if (form.available_now) params.available_now = true
    lastParamsRef.current = params
    await runSearch(params)
  }

  // Re-run the last search every 15s so results stay live
  useEffect(() => {
    const t = setInterval(() => {
      if (lastParamsRef.current) runSearch(lastParamsRef.current, false)
    }, 15_000)
    return () => clearInterval(t)
  }, [])

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

  return (
    <Layout>
      {toast && (
        <div className="fixed top-20 right-4 z-50 bg-blue-700 text-white text-sm font-medium px-4 py-3 rounded-xl shadow-lg">
          {toast}
        </div>
      )}

      <div className="mb-6">
        <h1 className="text-2xl font-black text-gray-900">Search Venues</h1>
        <p className="text-sm text-gray-500 mt-1">Find available spaces by day, time, and capacity</p>
      </div>

      {/* Search form */}
      <form onSubmit={handleSearch} className="card p-6 mb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">Day</label>
          <select value={form.day} onChange={e => set('day', e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            {DAYS.map(d => <option key={d} value={d}>{d.charAt(0) + d.slice(1).toLowerCase()}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">Time</label>
          <input type="time" value={form.time} onChange={e => set('time', e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">Minimum Capacity</label>
          <input type="number" min="1" placeholder="e.g. 30"
            value={form.min_capacity} onChange={e => set('min_capacity', e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">Min Availability %</label>
          <input type="number" min="0" max="100" placeholder="e.g. 50"
            value={form.min_availability} onChange={e => set('min_availability', e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">Status Filter</label>
          <select value={form.status} onChange={e => set('status', e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="">Any</option>
            <option value="GREEN">Available (GREEN)</option>
            <option value="RED">Occupied (RED)</option>
          </select>
        </div>

        <div className="flex flex-col justify-end">
          <label className="flex items-center gap-2 text-sm text-gray-700 mb-3 cursor-pointer">
            <input type="checkbox" checked={form.available_now}
              onChange={e => set('available_now', e.target.checked)}
              className="w-4 h-4 rounded accent-blue-700" />
            Available right now
          </label>
          <button type="submit" disabled={loading}
            className="w-full bg-blue-900 hover:bg-blue-800 text-white font-semibold rounded-lg py-2.5 text-sm transition-colors disabled:opacity-50">
            {loading ? 'Searching...' : 'Search Venues'}
          </button>
        </div>
      </form>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3 mb-4">
          {error}
        </div>
      )}

      {loading && <LoadingSpinner message="Searching venues..." />}

      {!loading && results !== null && (
        <>
          <p className="text-xs text-gray-400 mb-3">{results.length} result{results.length !== 1 ? 's' : ''} found</p>
          {results.length === 0 ? (
            <EmptyState title="No venues found"
              message="Try broadening your search — lower the minimum capacity or remove the time filter." />
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {results.map(v => (
                <VenueCard key={v.venue_id} venue={v} onAlarm={handleAlarm} />
              ))}
            </div>
          )}
        </>
      )}

      {!loading && results === null && (
        <EmptyState title="Start a search" message="Select a day and time above then hit Search Venues." />
      )}
    </Layout>
  )
}
