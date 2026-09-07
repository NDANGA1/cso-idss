// VenueLayout.jsx
// Shows the seat-level view — each seat coloured by occupancy state.
// Data comes from the seatmap API and refreshes every few seconds.

import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import Layout from '../components/Layout.jsx'
import SeatGrid from '../components/SeatGrid.jsx'
import CameraView from '../components/CameraView.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import { seatmapApi } from '../api/seatmap.js'
import { venuesApi } from '../api/venues.js'

const POLL_MS = 8_000   // refresh every 8s — fast enough for real-time feel

export default function VenueLayout() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [seatmap, setSeatmap] = useState(null)
  const [venue, setVenue] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)
  const [changedIds, setChangedIds] = useState(new Set())
  const prevSeatsRef = useRef({})   // seat_id → occupied (previous poll)
  const [view, setView] = useState('grid')   // 'grid' | 'camera' | 'split'

  const fetchSeatmap = useCallback(async () => {
    try {
      const data = await seatmapApi.get(id)

      // Detect which seats changed since last poll
      const changed = new Set()
      data.seats.forEach(s => {
        if (prevSeatsRef.current[s.id] !== undefined &&
            prevSeatsRef.current[s.id] !== s.occupied) {
          changed.add(s.id)
        }
        prevSeatsRef.current[s.id] = s.occupied
      })
      setChangedIds(changed)
      setTimeout(() => setChangedIds(new Set()), 2000)   // clear pulse after 2s

      setSeatmap(data)
      setLastUpdated(new Date())
    } catch (e) {
      setError(e.message)
    }
  }, [id])

  useEffect(() => {
    Promise.all([
      venuesApi.getVenue(id).then(setVenue).catch(() => {}),
      fetchSeatmap(),
    ]).finally(() => setLoading(false))

    const t = setInterval(fetchSeatmap, POLL_MS)
    return () => clearInterval(t)
  }, [fetchSeatmap, id])

  if (loading) return <Layout><LoadingSpinner message="Loading seat map..." /></Layout>

  if (error || !seatmap) return (
    <Layout>
      <div className="text-center py-20">
        <p className="text-red-500 font-medium">{error || 'Seat map not found.'}</p>
        <button onClick={() => navigate(-1)} className="mt-4 text-sm text-blue-600 hover:underline">← Back</button>
      </div>
    </Layout>
  )

  const occupancyPct = seatmap.occupancy_percentage
  const pctColor = occupancyPct >= 80 ? 'text-red-600' : occupancyPct >= 50 ? 'text-amber-500' : 'text-emerald-600'

  return (
    <Layout>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <button onClick={() => navigate(`/venues/${id}`)}
            className="text-xs text-blue-600 hover:underline mb-1 block">
            ← Back to {venue?.venue_name || `Venue #${id}`}
          </button>
          <h1 className="text-2xl font-black text-gray-900">
            {venue?.venue_name || `Venue #${id}`} — Live Seat Map
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Updates every {POLL_MS / 1000}s ·{' '}
            {lastUpdated && `Last: ${lastUpdated.toLocaleTimeString('en-GB')}`}
          </p>
        </div>

        {/* Data source badge */}
        <div className={`flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-semibold ${
          seatmap.data_source === 'CAMERA'
            ? 'bg-red-50 border-red-200 text-red-700'
            : 'bg-amber-50 border-amber-200 text-amber-700'
        }`}>
          <span className={`w-2 h-2 rounded-full animate-pulse ${
            seatmap.data_source === 'CAMERA' ? 'bg-red-500' : 'bg-amber-400'
          }`} />
          {seatmap.data_source === 'CAMERA' ? 'LIVE · AI Camera' : 'MOCK · Simulated Data'}
        </div>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <StatCard label="Total Seats" value={seatmap.total_seats} color="blue" />
        <StatCard label="Occupied" value={seatmap.occupied_seats} color="red" />
        <StatCard label="Free" value={seatmap.free_seats} color="emerald" />
        <StatCard label="Occupancy" value={`${occupancyPct}%`} color={occupancyPct >= 80 ? 'red' : occupancyPct >= 50 ? 'amber' : 'emerald'} />
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-100 rounded-full h-3 mb-6 overflow-hidden">
        <div
          className={`h-3 rounded-full transition-all duration-700 ${
            occupancyPct >= 80 ? 'bg-red-500' : occupancyPct >= 50 ? 'bg-amber-400' : 'bg-emerald-500'
          }`}
          style={{ width: `${occupancyPct}%` }}
        />
      </div>

      {/* View toggle */}
      <div className="flex gap-2 mb-4">
        {[['grid', 'Seat Grid'], ['camera', 'Camera View'], ['split', 'Split View']].map(([v, label]) => (
          <button key={v} onClick={() => setView(v)}
            className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
              view === v ? 'bg-blue-900 text-white' : 'bg-white border border-gray-200 text-gray-600 hover:border-gray-300'
            }`}>
            {label}
          </button>
        ))}
      </div>

      {/* Main content */}
      {view === 'grid' && (
        <div className="card p-6">
          <SeatGrid
            seats={seatmap.seats}
            rows={seatmap.rows}
            cols={seatmap.cols}
            aisleAfterCol={seatmap.aisle_after_col}
            changedIds={changedIds}
          />
        </div>
      )}

      {view === 'camera' && (
        <CameraView
          seats={seatmap.seats}
          dataSource={seatmap.data_source}
          venueName={venue?.venue_name || `Venue #${id}`}
        />
      )}

      {view === 'split' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="card p-4">
            <h2 className="text-sm font-bold text-gray-700 mb-4">Seat Plan</h2>
            <SeatGrid
              seats={seatmap.seats}
              rows={seatmap.rows}
              cols={seatmap.cols}
              aisleAfterCol={seatmap.aisle_after_col}
              changedIds={changedIds}
            />
          </div>
          <div>
            <h2 className="text-sm font-bold text-gray-700 mb-4">Camera Feed</h2>
            <CameraView
              seats={seatmap.seats}
              dataSource={seatmap.data_source}
              venueName={venue?.venue_name || `Venue #${id}`}
            />
          </div>
        </div>
      )}

      {/* CCTV pending notice */}
      {seatmap.data_source === 'MOCK' && (
        <div className="mt-6 bg-blue-50 border border-blue-100 rounded-2xl p-4 text-sm text-blue-700">
          <strong>Mock data active.</strong> The seat layout and occupancy patterns shown are
          simulated based on the current timetable. When CCTV cameras are connected and
          the inference loop starts, this page will automatically switch to live AI-detected
          data — no changes needed.
        </div>
      )}
    </Layout>
  )
}

function StatCard({ label, value, color }) {
  const colors = {
    blue: 'bg-blue-50 text-blue-700 border-blue-100',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-100',
    red: 'bg-red-50 text-red-700 border-red-100',
    amber: 'bg-amber-50 text-amber-700 border-amber-100',
  }
  return (
    <div className={`card p-4 border ${colors[color] ?? colors.blue}`}>
      <p className="text-2xl font-black">{value}</p>
      <p className="text-xs font-medium mt-1 opacity-70">{label}</p>
    </div>
  )
}
