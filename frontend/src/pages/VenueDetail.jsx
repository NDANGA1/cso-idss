// VenueDetail.jsx
// Shows live occupancy for a single venue with a step chart.
// I also render the weekly timetable and let users set alarms from here.

import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import Layout from '../components/Layout.jsx'
import StatusBadge from '../components/StatusBadge.jsx'
import OccupancyGauge from '../components/OccupancyGauge.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import { venuesApi } from '../api/venues.js'
import { alarmsApi } from '../api/alarms.js'
import { useAuth } from '../context/AuthContext.jsx'

const DAYS = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']
const MAX_POINTS = 120  // rolling window — 2 min at 1 s tick

function todayName() {
  return DAYS[new Date().getDay() === 0 ? 6 : new Date().getDay() - 1]
}

/* ── Forex-style Live Occupancy Chart ───────────────────────────────────── */
function LiveOccupancyChart({ venueId, capacity }) {
  const [points, setPoints] = useState([])
  const [hover, setHover]   = useState(null)   // { i, x, y } — crosshair index
  const [demo, setDemo]     = useState(false)
  const svgRef  = useRef(null)
  const timerRef = useRef(null)
  const demoRef  = useRef({ v: 20, t: 0 })

  const pushPoint = useCallback(v => {
    setPoints(prev => {
      const next = [...prev, { t: new Date(), v }]
      return next.length > MAX_POINTS ? next.slice(next.length - MAX_POINTS) : next
    })
  }, [])

  // Live tick — real API data every 1 s
  const tick = useCallback(async () => {
    try {
      const data  = await venuesApi.getVenue(venueId)
      const value = data.physical_occupied_seats ?? data.current_occupancy ?? 0
      pushPoint(value)
    } catch (_) {}
  }, [venueId, pushPoint])

  // Demo tick — random walk that visibly rises & falls every second
  const demoTick = useCallback(() => {
    const cap = capacity || 60
    const s   = demoRef.current
    s.t++
    // Every ~8 s inject a big swing so the graph is obviously moving
    const swing = s.t % 8 === 0
      ? (Math.random() > 0.5 ? 1 : -1) * Math.floor(Math.random() * 8 + 4)
      : (Math.random() > 0.5 ? 1 : -1) * Math.floor(Math.random() * 3)
    s.v = Math.max(0, Math.min(cap, s.v + swing))
    pushPoint(s.v)
  }, [capacity, pushPoint])

  useEffect(() => {
    if (demo) {
      demoRef.current.t = 0
      timerRef.current = setInterval(demoTick, 1000)
    } else {
      tick()
      timerRef.current = setInterval(tick, 1000)
    }
    return () => clearInterval(timerRef.current)
  }, [demo, tick, demoTick])

  // ── dimensions ─────────────────────────────────────────────────────────────
  const W   = 700
  const H   = 220
  const PL  = 8      // left  — no y-labels on left (forex puts them on right)
  const PR  = 58     // right — y-labels + price tag
  const PT  = 16
  const PB  = 28
  const iW  = W - PL - PR
  const iH  = H - PT - PB
  const cap = capacity || 60

  // ── scale ──────────────────────────────────────────────────────────────────
  const vals    = points.map(p => p.v)
  const dMin    = vals.length ? Math.min(...vals) : 0
  const dMax    = vals.length ? Math.max(...vals) : cap
  const margin  = Math.max(1, Math.ceil((dMax - dMin) * 0.18))
  const yMin    = Math.max(0, dMin - margin)
  const yMax    = Math.max(yMin + 1, Math.min(cap + margin, dMax + margin))
  const yRange  = yMax - yMin

  const toX = i  => PL + (i / Math.max(points.length - 1, 1)) * iW
  const toY = v  => PT + iH - ((v - yMin) / yRange) * iH
  const fromSvgX = px => {
    const idx = Math.round(((px - PL) / iW) * (points.length - 1))
    return Math.max(0, Math.min(points.length - 1, idx))
  }

  // ── step path with per-segment colouring (green↑ red↓ same=last) ──────────
  const segments = []  // [{d, color}]
  if (points.length >= 2) {
    for (let i = 1; i < points.length; i++) {
      const x0 = toX(i-1).toFixed(1), y0 = toY(points[i-1].v).toFixed(1)
      const x1 = toX(i).toFixed(1),   y1 = toY(points[i].v).toFixed(1)
      const up = points[i].v > points[i-1].v
      const dn = points[i].v < points[i-1].v
      const color = up ? '#26a69a' : dn ? '#ef5350' : '#94a3b8'
      // horizontal to next x at prev y, then vertical to new y
      segments.push({ d: `M${x0},${y0} L${x1},${y0} L${x1},${y1}`, color })
    }
  }

  // unified area fill (gradient under whole line)
  const buildAreaPath = () => {
    if (points.length < 2) return ''
    let d = `M${toX(0).toFixed(1)},${toY(points[0].v).toFixed(1)}`
    for (let i = 1; i < points.length; i++) {
      d += ` L${toX(i).toFixed(1)},${toY(points[i-1].v).toFixed(1)} L${toX(i).toFixed(1)},${toY(points[i].v).toFixed(1)}`
    }
    const bot = (PT + iH).toFixed(1)
    d += ` L${toX(points.length-1).toFixed(1)},${bot} L${PL},${bot} Z`
    return d
  }

  const current  = points.length ? points[points.length - 1].v : 0
  const prev     = points.length > 1 ? points[points.length - 2].v : current
  const delta    = current - prev
  const isUp     = delta > 0
  const isDown   = delta < 0
  const tickColor = isUp ? '#26a69a' : isDown ? '#ef5350' : '#94a3b8'
  const pct      = Math.round((current / cap) * 100)

  // ── y-axis ticks (right side) ──────────────────────────────────────────────
  const yTicks = Array.from({ length: 6 }, (_, i) => +(yMin + (yRange / 5) * i).toFixed(0))

  // ── x-axis labels ──────────────────────────────────────────────────────────
  const xTickIdxs = points.length >= 2
    ? [0, Math.floor(points.length * 0.25), Math.floor(points.length * 0.5),
       Math.floor(points.length * 0.75), points.length - 1]
        .filter((v, i, a) => a.indexOf(v) === i)
    : []

  // ── hover handler ──────────────────────────────────────────────────────────
  const onMouseMove = e => {
    const svg  = svgRef.current
    if (!svg || points.length < 2) return
    const rect = svg.getBoundingClientRect()
    const px   = (e.clientX - rect.left) * (W / rect.width)
    const i    = fromSvgX(px)
    setHover({ i, x: toX(i), y: toY(points[i].v) })
  }
  const onMouseLeave = () => setHover(null)

  const hp = hover !== null ? points[hover.i] : null

  return (
    <div style={{ background: '#0f1923', borderRadius: 12, padding: '16px 12px 12px', fontFamily: 'monospace' }}>

      {/* ── header ─────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 12 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: '#94a3b8', fontSize: 11, letterSpacing: 1, textTransform: 'uppercase' }}>
              Live Occupancy · 1 s tick
            </span>
            {demo && (
              <span style={{ background: '#f97316', color: '#fff', fontSize: 9, fontWeight: 700,
                             padding: '1px 6px', borderRadius: 4, letterSpacing: 1 }}>
                DEMO
              </span>
            )}
            <button
              onClick={() => { setPoints([]); setDemo(d => !d) }}
              style={{ marginLeft: 4, fontSize: 10, padding: '2px 8px', borderRadius: 4, border: 'none',
                       cursor: 'pointer', fontFamily: 'monospace', fontWeight: 700,
                       background: demo ? '#26a69a' : '#1e2d3d', color: demo ? '#fff' : '#64748b' }}
            >
              {demo ? ' LIVE' : ' DEMO'}
            </button>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 4 }}>
            <span style={{ fontSize: 32, fontWeight: 900, color: tickColor, lineHeight: 1 }}>{current}</span>
            <span style={{ fontSize: 13, color: tickColor }}>
              {delta > 0 ? ` +${delta}` : delta < 0 ? ` ${delta}` : '─ 0'}
            </span>
            <span style={{ fontSize: 11, color: '#475569' }}>people</span>
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 11, color: '#475569' }}>capacity</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#f97316' }}>{cap}</div>
          <div style={{ fontSize: 11, color: pct >= 90 ? '#ef5350' : pct >= 60 ? '#f97316' : '#26a69a', marginTop: 2 }}>
            {pct}% full
          </div>
        </div>
      </div>

      {/* ── chart ──────────────────────────────────────────────────────────── */}
      {points.length < 2 ? (
        <div style={{ height: H, display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: '#334155', fontSize: 12 }}>
          Collecting data… <span style={{ marginLeft: 6, animation: 'pulse 1s infinite' }}></span>
        </div>
      ) : (
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          style={{ width: '100%', height: H, display: 'block', cursor: 'crosshair' }}
          onMouseMove={onMouseMove}
          onMouseLeave={onMouseLeave}
        >
          <defs>
            <linearGradient id={`og-${venueId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor={tickColor} stopOpacity="0.18" />
              <stop offset="100%" stopColor={tickColor} stopOpacity="0.01" />
            </linearGradient>
          </defs>

          {/* background */}
          <rect x={PL} y={PT} width={iW} height={iH} fill="#0f1923" />

          {/* grid lines */}
          {yTicks.map(v => (
            <line key={v}
              x1={PL} y1={toY(v)} x2={PL + iW} y2={toY(v)}
              stroke="#1e2d3d" strokeWidth="1"
            />
          ))}
          {xTickIdxs.map(i => (
            <line key={i}
              x1={toX(i)} y1={PT} x2={toX(i)} y2={PT + iH}
              stroke="#1e2d3d" strokeWidth="1"
            />
          ))}

          {/* area fill */}
          <path d={buildAreaPath()} fill={`url(#og-${venueId})`} />

          {/* capacity line */}
          {cap >= yMin && cap <= yMax && (
            <>
              <line
                x1={PL} y1={toY(cap)} x2={PL + iW} y2={toY(cap)}
                stroke="#f97316" strokeWidth="1" strokeDasharray="5 3" opacity="0.6"
              />
              <rect x={PL + iW} y={toY(cap) - 8} width={PR - 2} height={16} fill="#f97316" rx="3" />
              <text x={PL + iW + 4} y={toY(cap) + 4} fontSize="10" fill="#fff" fontWeight="700">
                CAP {cap}
              </text>
            </>
          )}

          {/* step segments — coloured per direction */}
          {segments.map((s, i) => (
            <path key={i} d={s.d} fill="none" stroke={s.color} strokeWidth="1.5" strokeLinejoin="round" />
          ))}

          {/* current price horizontal dashed line */}
          <line
            x1={PL} y1={toY(current)} x2={PL + iW} y2={toY(current)}
            stroke={tickColor} strokeWidth="1" strokeDasharray="3 3" opacity="0.5"
          />

          {/* right-side price tag */}
          <rect x={PL + iW} y={toY(current) - 10} width={PR - 2} height={20} fill={tickColor} rx="3" />
          <text x={PL + iW + 4} y={toY(current) + 5} fontSize="12" fill="#fff" fontWeight="900">
            {current}
          </text>

          {/* live pulse dot at rightmost point */}
          <circle cx={toX(points.length - 1)} cy={toY(current)} r="3.5" fill={tickColor} />
          <circle cx={toX(points.length - 1)} cy={toY(current)} r="7" fill={tickColor} opacity="0.15" />

          {/* y-axis labels (right) */}
          {yTicks.map(v => (
            <text key={v} x={PL + iW + 4} y={toY(v) + 4} fontSize="9" fill="#475569">
              {v}
            </text>
          ))}

          {/* x-axis labels */}
          {xTickIdxs.map(i => (
            <text key={i} x={toX(i)} y={H - 6} textAnchor="middle" fontSize="9" fill="#334155">
              {points[i].t.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </text>
          ))}

          {/* ── crosshair ── */}
          {hover !== null && hp && (
            <>
              {/* vertical line */}
              <line x1={hover.x} y1={PT} x2={hover.x} y2={PT + iH}
                stroke="#64748b" strokeWidth="1" strokeDasharray="3 3" />
              {/* horizontal line */}
              <line x1={PL} y1={hover.y} x2={PL + iW} y2={hover.y}
                stroke="#64748b" strokeWidth="1" strokeDasharray="3 3" />
              {/* dot on line */}
              <circle cx={hover.x} cy={hover.y} r="4" fill="#fff" stroke={tickColor} strokeWidth="2" />
              {/* tooltip box */}
              {(() => {
                const bx = hover.x > W * 0.6 ? hover.x - 120 : hover.x + 10
                const by = hover.y > H * 0.6 ? hover.y - 52 : hover.y + 8
                return (
                  <g>
                    <rect x={bx} y={by} width={112} height={44} fill="#1e2d3d" rx="5"
                      stroke="#334155" strokeWidth="1" />
                    <text x={bx + 8} y={by + 16} fontSize="10" fill="#94a3b8">
                      {hp.t.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </text>
                    <text x={bx + 8} y={by + 34} fontSize="14" fontWeight="900" fill={tickColor}>
                      {hp.v} people
                    </text>
                  </g>
                )
              })()}
            </>
          )}
        </svg>
      )}

      {/* ── footer ─────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 10, color: '#334155' }}>
        <span style={{ color: '#26a69a' }}> increasing</span>
        <span>{points.length} readings · {MAX_POINTS} max · auto-scale Y</span>
        <span style={{ color: '#ef5350' }}> decreasing</span>
      </div>
    </div>
  )
}

export default function VenueDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()

  const [venue, setVenue] = useState(null)
  const [schedule, setSchedule] = useState([])
  const [selectedDay, setSelectedDay] = useState(todayName())
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState('')
  const [lastRefresh, setLastRefresh] = useState(null)

  const fetchVenue = useCallback(async () => {
    try {
      const v = await venuesApi.getVenue(id)
      setVenue(v)
      setLastRefresh(new Date())
    } catch (e) {
      console.error(e)
    }
  }, [id])

  const fetchSchedule = useCallback(async () => {
    try {
      const s = await venuesApi.getSchedule(id, selectedDay)
      setSchedule(s)
    } catch (e) {
      console.error(e)
    }
  }, [id, selectedDay])

  useEffect(() => {
    setLoading(true)
    fetchVenue().finally(() => setLoading(false))
    const t = setInterval(fetchVenue, 15_000)
    return () => clearInterval(t)
  }, [fetchVenue])

  useEffect(() => {
    fetchSchedule()
  }, [fetchSchedule])

  const handleAlarm = async () => {
    if (!user) { navigate('/login'); return }
    try {
      await alarmsApi.create(Number(id), `Notify me when ${venue?.venue_name} is free`)
      setToast('Alarm set! You will be notified when this venue becomes available.')
    } catch (e) {
      setToast(e.message)
    }
    setTimeout(() => setToast(''), 4000)
  }

  if (loading) return <Layout><LoadingSpinner message="Loading venue..." /></Layout>
  if (!venue) return <Layout><p className="text-center py-20 text-gray-400">Venue not found.</p></Layout>

  const isRed = venue.availability_state === 'RED'     // booked
  const isFull = venue.availability_state === 'FULL'   // unbooked but physically full
  const isUnavailable = isRed || isFull

  return (
    <Layout>
      {toast && (
        <div className="fixed top-20 right-4 z-50 bg-blue-700 text-white text-sm font-medium px-4 py-3 rounded-xl shadow-lg max-w-xs">
          {toast}
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-6">
        <div>
          <button onClick={() => navigate(-1)} className="text-xs text-blue-600 hover:underline mb-2 block">
            ← Back
          </button>
          <h1 className="text-2xl font-black text-gray-900">{venue.venue_name}</h1>
          <p className="text-sm text-gray-500 mt-1">
            Capacity: {venue.capacity} seats ·
            Mode: <span className="font-medium">{venue.data_mode === 'LIVE' ? 'AI Camera (LIVE)' : 'Timetable-based'}</span>
            {lastRefresh && (
              <span className="ml-2 text-xs text-gray-400">
                · updated {lastRefresh.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            )}
          </p>
        </div>
        <div className="flex flex-col items-end gap-3">
          <StatusBadge state={venue.availability_state} size="lg" />
          <Link to={`/venues/${id}/layout`}
            className="bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors">
            Live Seat Map
          </Link>
          {isUnavailable && (
            <button onClick={handleAlarm}
              className="bg-blue-900 hover:bg-blue-800 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors">
              Set Alarm
            </button>
          )}
        </div>
      </div>

      {/* Physical occupancy / overcrowding banner */}
      {isUnavailable && venue.physical_occupancy_pct != null && (
        <div className={`mb-4 border rounded-2xl px-4 py-3 ${
          venue.is_overcrowded
            ? 'bg-red-50 border-red-300'
            : 'bg-amber-50 border-amber-200'
        }`}>
          <div className="flex items-center justify-between mb-2">
            <div>
              <p className={`text-xs font-bold uppercase tracking-wide ${venue.is_overcrowded ? 'text-red-800' : 'text-amber-800'}`}>
                {venue.is_overcrowded
                  ? `OVERCROWDED — ${venue.overcrowding_count} people over capacity`
                  : 'Actual Physical Occupancy'}
              </p>
              <p className={`text-xs mt-0.5 ${venue.is_overcrowded ? 'text-red-600' : 'text-amber-600'}`}>
                {venue.is_overcrowded
                  ? `Room is full. ${venue.overcrowding_count} extra people beyond the ${venue.capacity} seat capacity.`
                  : 'Venue is booked (unavailable to reserve) but here\'s how full it really is:'}
              </p>
            </div>
            <span className={`text-2xl font-black ${venue.is_overcrowded ? 'text-red-700' : 'text-amber-700'}`}>
              {venue.physical_occupancy_pct}%
            </span>
          </div>
          <div className={`h-2 rounded-full overflow-hidden ${venue.is_overcrowded ? 'bg-red-100' : 'bg-amber-100'}`}>
            <div
              className={`h-full rounded-full transition-all ${venue.is_overcrowded ? 'bg-red-500' : 'bg-amber-500'}`}
              style={{ width: '100%' }}
            />
          </div>
          <p className={`text-xs mt-1.5 font-medium ${venue.is_overcrowded ? 'text-red-700' : 'text-amber-700'}`}>
            {venue.physical_occupied_seats} of {venue.capacity} seats physically occupied
            {venue.physical_data_source === 'CAMERA' ? ' · live camera data' : ' · timetable estimate'}
          </p>
        </div>
      )}

      {/* Stats + Gauge */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="sm:col-span-2 grid grid-cols-2 sm:grid-cols-3 gap-4">
          <StatBox
            label={isUnavailable ? 'Empty Seats' : 'Free Seats'}
            value={venue.free_seats}
            color={isUnavailable ? 'amber' : 'emerald'}
          />
          <StatBox label="Capacity" value={venue.capacity} color="blue" />
          <StatBox
            label={isUnavailable ? 'Status' : 'Availability'}
            value={isRed ? 'Booked' : isFull ? 'Full' : `${venue.availability_percentage}%`}
            color={isUnavailable ? 'red' : 'emerald'}
          />
          {venue.physical_occupancy_pct != null && (
            <StatBox label="Occupied %" value={`${venue.physical_occupancy_pct}%`} color="amber" />
          )}
          {venue.physical_occupied_seats != null && (
            <StatBox label="People in Room" value={venue.physical_occupied_seats} color="amber" />
          )}
          {venue.expected_free_time && (
            <div className="col-span-2 bg-amber-50 border border-amber-100 rounded-2xl p-4">
              <p className="text-xs font-semibold text-amber-700 mb-0.5">Expected Free Time</p>
              <p className="text-lg font-bold text-amber-800">
                {new Date(venue.expected_free_time).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}
              </p>
              {venue.current_holder && <p className="text-xs text-amber-600 mt-0.5">{venue.current_holder}</p>}
            </div>
          )}
        </div>
        <div className="flex flex-col items-center justify-center p-4 card gap-2">
          <OccupancyGauge percentage={venue.availability_percentage} size={130} />
          {isUnavailable && venue.physical_occupancy_pct != null && (
            <div className="text-center">
              <p className="text-xs text-gray-400">booking availability</p>
              <p className="text-xs font-semibold text-amber-600">{venue.physical_occupancy_pct}% physically occupied</p>
            </div>
          )}
        </div>
      </div>

      {/* Day selector */}
      <div className="flex gap-2 overflow-x-auto pb-1 mb-4">
        {DAYS.map(d => (
          <button key={d} onClick={() => setSelectedDay(d)}
            className={`flex-shrink-0 px-4 py-2 rounded-full text-xs font-medium transition-colors ${
              selectedDay === d
                ? 'bg-blue-900 text-white'
                : 'bg-white border border-gray-200 text-gray-600 hover:border-gray-300'
            }`}>
            {d.charAt(0) + d.slice(1, 3).toLowerCase()}
          </button>
        ))}
      </div>

      {/* Schedule */}
      <div className="card p-4 mb-4">
        <h2 className="font-bold text-gray-800 mb-3 text-sm">Schedule — {selectedDay.charAt(0) + selectedDay.slice(1).toLowerCase()}</h2>
        {schedule.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-6">No bookings on this day.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-2 pr-3 font-semibold text-gray-500">Start</th>
                  <th className="text-left py-2 pr-3 font-semibold text-gray-500">End</th>
                  <th className="text-left py-2 pr-3 font-semibold text-gray-500">Course</th>
                  <th className="text-left py-2 pr-3 font-semibold text-gray-500">Lecturer</th>
                  <th className="text-left py-2 font-semibold text-gray-500">Type</th>
                </tr>
              </thead>
              <tbody>
                {schedule.map((b, i) => (
                  <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 pr-3 font-mono">{b.start_time}</td>
                    <td className="py-2 pr-3 font-mono">{b.end_time}</td>
                    <td className="py-2 pr-3 font-medium">{b.course_code || '—'}</td>
                    <td className="py-2 pr-3 text-gray-500">{b.lecturer || '—'}</td>
                    <td className="py-2">
                      <span className={`px-2 py-0.5 rounded-full font-medium ${
                        b.session_type === 'LECTURE'
                          ? 'bg-blue-50 text-blue-700'
                          : b.session_type === 'LAB'
                          ? 'bg-purple-50 text-purple-700'
                          : 'bg-gray-100 text-gray-600'
                      }`}>
                        {b.session_type || 'BOOKING'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Live Occupancy Chart */}
      <LiveOccupancyChart
        venueId={id}
        capacity={venue.capacity}
        state={venue.availability_state}
      />
    </Layout>
  )
}

function StatBox({ label, value, color }) {
  const colors = {
    emerald: 'text-emerald-700 bg-emerald-50 border-emerald-100',
    red: 'text-red-700 bg-red-50 border-red-100',
    blue: 'text-blue-700 bg-blue-50 border-blue-100',
    gray: 'text-gray-700 bg-gray-50 border-gray-100',
    amber: 'text-amber-700 bg-amber-50 border-amber-100',
  }
  return (
    <div className={`card p-4 border ${colors[color]}`}>
      <p className="text-2xl font-black">{value}</p>
      <p className="text-xs font-medium mt-1 opacity-70">{label}</p>
    </div>
  )
}
