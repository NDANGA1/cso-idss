// Forecast.jsx
// Shows predicted occupancy across the day for a selected venue.
// I pull hourly averages from the forecast API.

import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../components/Layout.jsx'
import { forecastApi } from '../api/forecast.js'

// ── Shared SVG chart components (same pattern as Analytics.jsx) ───────────────

function LineChart({ data, valueKey = 'predicted_pct', labelKey = 'hour_label', color = '#6366f1', height = 200, bookingKey = null }) {
  if (!data || data.length === 0) return <Empty />
  const vals = data.map(d => d[valueKey] ?? null)
  const defined = vals.filter(v => v !== null)
  if (!defined.length) return <Empty />

  const max = Math.max(...defined, 10)
  const W = 600, H = height
  const padL = 38, padR = 12, padT = 12, padB = 28
  const w = W - padL - padR
  const h = H - padT - padB

  const xs = data.map((_, i) => padL + (i / Math.max(data.length - 1, 1)) * w)
  const ys = vals.map(v => v === null ? null : padT + h - (v / max) * h)

  let pathD = ''
  let areaD = ''
  let inArea = false
  vals.forEach((v, i) => {
    if (v !== null) {
      pathD += pathD === '' ? `M ${xs[i]} ${ys[i]} ` : `L ${xs[i]} ${ys[i]} `
      if (!inArea) { areaD += `M ${xs[i]} ${padT + h} L ${xs[i]} ${ys[i]} `; inArea = true }
      else areaD += `L ${xs[i]} ${ys[i]} `
    } else if (inArea) {
      areaD += `L ${xs[i - 1]} ${padT + h} Z `; inArea = false
    }
  })
  if (inArea) { const l = vals.length - 1; areaD += `L ${xs[l]} ${padT + h} Z` }

  const step = data.length <= 12 ? 1 : data.length <= 24 ? 2 : Math.ceil(data.length / 10)
  const gridLines = [0, 25, 50, 75, 100].filter(v => v <= max + 5)
  const gid = `grad${color.replace(/[^a-z0-9]/gi, '')}`

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height }}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.2" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {gridLines.map(g => {
        const gy = padT + h - (g / max) * h
        return <g key={g}>
          <line x1={padL} y1={gy} x2={padL + w} y2={gy} stroke="#e5e7eb" strokeWidth="1" />
          <text x={padL - 4} y={gy + 4} textAnchor="end" fontSize="9" fill="#9ca3af">{g}%</text>
        </g>
      })}
      {/* Booking shading */}
      {bookingKey && data.map((d, i) => {
        if (!d[bookingKey]) return null
        const x0 = xs[i] - (xs[1] - xs[0]) / 2
        const bw = xs[1] - xs[0]
        return <rect key={i} x={x0} y={padT} width={bw} height={h} fill="#ef4444" opacity="0.06" />
      })}
      <path d={areaD} fill={`url(#${gid})`} />
      <path d={pathD} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />
      {data.length <= 24 && vals.map((v, i) => v !== null && (
        <circle key={i} cx={xs[i]} cy={ys[i]} r="3" fill={color}
          opacity={bookingKey && data[i][bookingKey] ? 1 : 0.7} />
      ))}
      {data.map((d, i) => i % step === 0 && (
        <text key={i} x={xs[i]} y={H - 6} textAnchor="middle" fontSize="9" fill="#9ca3af">
          {d[labelKey]}
        </text>
      ))}
    </svg>
  )
}

function Empty() {
  return <div className="flex items-center justify-center h-28 text-gray-400 text-sm">No data yet</div>
}

function InsightCard({ label, value, sub, accent = 'indigo' }) {
  const colors = {
    indigo: 'border-indigo-200 bg-indigo-50 text-indigo-800',
    red:    'border-red-200 bg-red-50 text-red-800',
    emerald:'border-emerald-200 bg-emerald-50 text-emerald-800',
    amber:  'border-amber-200 bg-amber-50 text-amber-800',
  }
  return (
    <div className={`border rounded-xl px-4 py-3 ${colors[accent]}`}>
      <p className="text-xs font-medium opacity-70 mb-0.5">{label}</p>
      <p className="text-lg font-bold leading-tight">{value ?? '—'}</p>
      {sub && <p className="text-xs opacity-60 mt-0.5">{sub}</p>}
    </div>
  )
}

function Card({ title, children, action }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-800">{title}</h3>
        {action}
      </div>
      {children}
    </div>
  )
}

function ModelBadge({ info }) {
  if (!info) return null
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className={`w-2 h-2 rounded-full ${info.model_ready ? 'bg-emerald-500' : 'bg-amber-400'}`} />
      <span className="text-gray-500">
        {info.model_ready
          ? `${info.algorithm} · ${info.training_rows.toLocaleString()} training rows`
          : 'Model not ready — not enough data'}
      </span>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Forecast() {
  const navigate = useNavigate()
  const [campus24h, setCampus24h] = useState([])
  const [campus7d, setCampus7d] = useState([])
  const [peaks, setPeaks] = useState(null)
  const [modelInfo, setModelInfo] = useState(null)
  const [venueId, setVenueId] = useState('')
  const [venueData, setVenueData] = useState([])
  const [venueLoading, setVenueLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [retraining, setRetraining] = useState(false)
  const refreshTimer = useRef(null)

  const fetchAll = useCallback(async () => {
    try {
      const [h24, d7, pk, info] = await Promise.all([
        forecastApi.campus24h(),
        forecastApi.campus7days(),
        forecastApi.peaks(),
        forecastApi.modelInfo(),
      ])
      setCampus24h(h24)
      setCampus7d(d7)
      setPeaks(pk)
      setModelInfo(info)
      setLastUpdated(new Date())
    } catch (e) {
      console.error('Forecast fetch error', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    refreshTimer.current = setInterval(fetchAll, 10 * 60 * 1000) // refresh every 10 min
    return () => clearInterval(refreshTimer.current)
  }, [fetchAll])

  const loadVenueForecast = async (id) => {
    if (!id) return
    setVenueLoading(true)
    try {
      const data = await forecastApi.venue24h(id)
      setVenueData(data)
    } catch {
      setVenueData([])
    } finally {
      setVenueLoading(false)
    }
  }

  const handleRetrain = async () => {
    setRetraining(true)
    try {
      await forecastApi.retrain()
      await fetchAll()
    } finally {
      setRetraining(false)
    }
  }

  const updStr = lastUpdated?.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

        {/* Header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Forecast</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              AI-predicted occupancy — RandomForest trained on {modelInfo?.training_rows?.toLocaleString() ?? '…'} historical readings
            </p>
            {modelInfo && <div className="mt-1"><ModelBadge info={modelInfo} /></div>}
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            {updStr && <span className="text-xs text-gray-400">Updated {updStr}</span>}
            <button onClick={fetchAll}
              className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1.5 rounded-lg transition-colors">
              Refresh
            </button>
            <button onClick={handleRetrain} disabled={retraining}
              className="text-xs border border-indigo-300 text-indigo-700 hover:bg-indigo-50 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50">
              {retraining ? 'Retraining…' : 'Retrain Model'}
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center h-64 gap-3 text-gray-400">
            <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
            <p className="text-sm">Loading forecasts…</p>
            {modelInfo && !modelInfo.model_ready && (
              <p className="text-xs text-amber-500">Model is training in the background — data will appear shortly</p>
            )}
          </div>
        ) : (
          <>
            {/* Peak prediction insight cards */}
            {peaks && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <InsightCard
                  label="Busiest Hour (Next 7 Days)"
                  value={peaks.busiest_hour ?? '—'}
                  sub={peaks.busiest_hour_pct != null ? `predicted ${peaks.busiest_hour_pct}%` : null}
                  accent="red"
                />
                <InsightCard
                  label="Busiest Day (Next 7 Days)"
                  value={peaks.busiest_day ?? '—'}
                  sub={peaks.busiest_day_pct != null ? `predicted ${peaks.busiest_day_pct}%` : null}
                  accent="amber"
                />
                <InsightCard
                  label="Busiest Venue Tomorrow"
                  value={peaks.busiest_venue_tomorrow ?? '—'}
                  sub={peaks.busiest_venue_tomorrow_pct != null ? `predicted ${peaks.busiest_venue_tomorrow_pct}%` : null}
                  accent="indigo"
                />
                <InsightCard
                  label="Quietest Venue Tomorrow"
                  value={peaks.quietest_venue_tomorrow ?? '—'}
                  sub={peaks.quietest_venue_tomorrow_pct != null ? `predicted ${peaks.quietest_venue_tomorrow_pct}%` : null}
                  accent="emerald"
                />
              </div>
            )}

            {/* Campus 24h + 7-day forecasts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card title="Campus Occupancy — Next 24 Hours">
                <LineChart
                  data={campus24h}
                  valueKey="predicted_pct"
                  labelKey="hour_label"
                  color="#6366f1"
                  height={200}
                />
                <p className="text-xs text-gray-400 mt-2">
                  Predicted avg % across all venues · shaded slots have active bookings
                </p>
              </Card>

              <Card title="Campus Occupancy — Next 7 Days">
                <LineChart
                  data={campus7d}
                  valueKey="predicted_pct"
                  labelKey="day_label"
                  color="#f59e0b"
                  height={200}
                />
                <p className="text-xs text-gray-400 mt-2">
                  Predicted avg % during 08:00–19:00 active window
                </p>
              </Card>
            </div>

            {/* Per-venue 24h forecast */}
            <Card title="Per-Venue 24-Hour Forecast">
              <div className="flex items-center gap-3 mb-4 flex-wrap">
                <input
                  type="number"
                  min="1"
                  placeholder="Enter Venue ID"
                  value={venueId}
                  onChange={e => setVenueId(e.target.value)}
                  className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm w-36 focus:outline-none focus:ring-2 focus:ring-indigo-300"
                />
                <button
                  onClick={() => loadVenueForecast(venueId)}
                  disabled={!venueId || venueLoading}
                  className="text-sm bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-4 py-1.5 rounded-lg transition-colors"
                >
                  {venueLoading ? 'Loading…' : 'Load Forecast'}
                </button>
                {venueId && (
                  <button
                    onClick={() => navigate(`/venues/${venueId}`)}
                    className="text-sm text-indigo-600 hover:underline"
                  >
                    View live →
                  </button>
                )}
              </div>

              {venueData.length > 0 ? (
                <>
                  <LineChart
                    data={venueData}
                    valueKey="predicted_pct"
                    labelKey="hour_label"
                    color="#10b981"
                    height={200}
                    bookingKey="booking_active"
                  />
                  <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
                    <span className="flex items-center gap-1">
                      <span className="w-4 h-3 bg-red-400 opacity-20 inline-block rounded-sm" />
                      Booked slot
                    </span>
                    <span>Green dot = predicted occupancy %. Red shading = timetabled booking.</span>
                  </div>
                </>
              ) : (
                <div className="flex items-center justify-center h-28 text-gray-400 text-sm">
                  Enter a venue ID above to see its 24-hour forecast
                </div>
              )}
            </Card>

            {/* Model info card */}
            <Card title="About the Forecast Model">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm text-gray-600">
                <div className="space-y-2">
                  <p><span className="font-medium text-gray-800">Algorithm:</span> {modelInfo?.algorithm ?? '—'}</p>
                  <p><span className="font-medium text-gray-800">Training data:</span> {modelInfo?.training_rows?.toLocaleString() ?? '—'} occupancy readings</p>
                  <p><span className="font-medium text-gray-800">Last trained:</span> {modelInfo?.model_trained_at
                    ? new Date(modelInfo.model_trained_at).toLocaleString()
                    : 'Not yet trained'}</p>
                </div>
                <div className="space-y-2">
                  <p className="font-medium text-gray-800">Features used:</p>
                  <ul className="list-disc list-inside text-xs space-y-0.5 text-gray-500">
                    {(modelInfo?.features ?? []).map(f => <li key={f}>{f}</li>)}
                  </ul>
                  <p className="text-xs text-gray-400 pt-1">Target: {modelInfo?.target ?? 'occupancy_pct'}</p>
                </div>
              </div>
              <p className="text-xs text-gray-400 border-t border-gray-100 pt-3 mt-3">
                {modelInfo?.note}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                When live camera data replaces mock data, this model will automatically improve — same table, same schema, same features.
              </p>
            </Card>
          </>
        )}
      </div>
    </Layout>
  )
}
