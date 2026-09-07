// Analytics.jsx
// The analytics dashboard — I show occupancy trends, peak hours
// and utilisation breakdown using recharts.

import { useEffect, useState, useRef, useCallback } from 'react'
import Layout from '../components/Layout.jsx'
import { analyticsApi } from '../api/analytics.js'

// ── Inline SVG chart components ──────────────────────────────────────────────

function LineChart({ data, valueKey = 'avg_occupancy_pct', labelKey = 'label', color = '#10b981', height = 200 }) {
  if (!data || data.length === 0) return <Empty />
  const vals = data.map(d => d[valueKey] ?? null)
  const defined = vals.filter(v => v !== null)
  if (!defined.length) return <Empty />

  const max = Math.max(...defined, 10)
  const W = 600, H = height
  const padL = 38, padR = 12, padT = 12, padB = 28
  const w = W - padL - padR
  const h = H - padT - padB

  const xs = data.map((_, i) => padL + (i / (data.length - 1)) * w)
  const ys = vals.map(v => v === null ? null : padT + h - (v / max) * h)

  // Build polyline from defined segments
  let pathD = ''
  let areaD = ''
  let segStart = null
  vals.forEach((v, i) => {
    if (v !== null) {
      if (segStart === null) {
        pathD += `M ${xs[i]} ${ys[i]} `
        segStart = i
      } else {
        pathD += `L ${xs[i]} ${ys[i]} `
      }
    } else {
      segStart = null
    }
  })

  // Area path (fill under line)
  let inSeg = false
  vals.forEach((v, i) => {
    if (v !== null) {
      if (!inSeg) {
        areaD += `M ${xs[i]} ${padT + h} L ${xs[i]} ${ys[i]} `
        inSeg = true
      } else {
        areaD += `L ${xs[i]} ${ys[i]} `
      }
    } else if (inSeg) {
      areaD += `L ${xs[i - 1]} ${padT + h} Z `
      inSeg = false
    }
  })
  if (inSeg) {
    const last = vals.length - 1
    areaD += `L ${xs[last]} ${padT + h} Z`
  }

  // Y grid lines
  const gridLines = [0, 25, 50, 75, 100].filter(v => v <= max + 5)

  // X label thinning for readability
  const step = data.length <= 12 ? 1 : data.length <= 24 ? 2 : Math.ceil(data.length / 10)

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height }}>
      <defs>
        <linearGradient id={`grad-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>

      {/* Grid */}
      {gridLines.map(g => {
        const gy = padT + h - (g / max) * h
        return (
          <g key={g}>
            <line x1={padL} y1={gy} x2={padL + w} y2={gy} stroke="#e5e7eb" strokeWidth="1" />
            <text x={padL - 4} y={gy + 4} textAnchor="end" fontSize="9" fill="#9ca3af">{g}%</text>
          </g>
        )
      })}

      {/* Area */}
      <path d={areaD} fill={`url(#grad-${color.replace('#', '')})`} />

      {/* Line */}
      <path d={pathD} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />

      {/* Dots for small datasets */}
      {data.length <= 24 && vals.map((v, i) => v !== null && (
        <circle key={i} cx={xs[i]} cy={ys[i]} r="3" fill={color} />
      ))}

      {/* X labels */}
      {data.map((d, i) => i % step === 0 && (
        <text key={i} x={xs[i]} y={H - 6} textAnchor="middle" fontSize="9" fill="#9ca3af">
          {d[labelKey]}
        </text>
      ))}
    </svg>
  )
}

function BarChart({ data, valueKey = 'avg_occupancy_pct', labelKey = 'venue_name', color = '#3b82f6', height = 280 }) {
  if (!data || data.length === 0) return <Empty />
  const vals = data.map(d => d[valueKey] ?? 0)
  const max = Math.max(...vals, 10)
  const W = 700, H = height
  const padL = 10, padR = 10, padT = 12, padB = 80
  const w = W - padL - padR
  const h = H - padT - padB

  const barW = Math.max(6, Math.floor(w / data.length) - 2)
  const gap = Math.floor(w / data.length)

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height }}>
      {/* Grid */}
      {[0, 25, 50, 75, 100].filter(v => v <= max + 5).map(g => {
        const gy = padT + h - (g / max) * h
        return (
          <g key={g}>
            <line x1={padL} y1={gy} x2={padL + w} y2={gy} stroke="#e5e7eb" strokeWidth="1" />
            <text x={padL - 2} y={gy + 4} textAnchor="start" fontSize="8" fill="#9ca3af">{g}%</text>
          </g>
        )
      })}

      {/* Bars */}
      {data.map((d, i) => {
        const bx = padL + i * gap + (gap - barW) / 2
        const bh = (vals[i] / max) * h
        const by = padT + h - bh
        const peakH = d.peak_occupancy_pct ? (d.peak_occupancy_pct / max) * h : null
        return (
          <g key={i}>
            {/* Peak indicator */}
            {peakH && (
              <line x1={bx} y1={padT + h - peakH} x2={bx + barW} y2={padT + h - peakH}
                stroke="#ef4444" strokeWidth="1.5" strokeDasharray="3,2" />
            )}
            <rect x={bx} y={by} width={barW} height={bh} fill={color} rx="2" opacity="0.85" />
            {/* Label rotated */}
            <text
              x={bx + barW / 2}
              y={padT + h + 6}
              textAnchor="end"
              fontSize="8"
              fill="#6b7280"
              transform={`rotate(-45, ${bx + barW / 2}, ${padT + h + 6})`}
            >
              {d[labelKey]?.substring(0, 14) ?? ''}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

function PieChart({ green = 0, full = 0, red = 0, size = 180 }) {
  const total = green + full + red || 1
  const toRad = pct => (pct / total) * 2 * Math.PI
  const cx = size / 2, cy = size / 2, r = size * 0.38

  function slice(startAngle, value, fill) {
    if (value === 0) return null
    const angle = toRad(value)
    const endAngle = startAngle + angle
    const x1 = cx + r * Math.sin(startAngle)
    const y1 = cy - r * Math.cos(startAngle)
    const x2 = cx + r * Math.sin(endAngle)
    const y2 = cy - r * Math.cos(endAngle)
    const large = angle > Math.PI ? 1 : 0
    return `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`
  }

  let angle = 0
  const slices = [
    { val: green, fill: '#10b981', label: 'Available' },
    { val: full, fill: '#ef4444', label: 'Full' },
    { val: red, fill: '#b91c1c', label: 'Booked' },
  ]

  return (
    <div className="flex items-center gap-6">
      <svg viewBox={`0 0 ${size} ${size}`} style={{ width: size, height: size, flexShrink: 0 }}>
        {slices.map((s, i) => {
          const d = slice(angle, s.val, s.fill)
          angle += toRad(s.val)
          return d ? <path key={i} d={d} fill={s.fill} stroke="white" strokeWidth="1.5" /> : null
        })}
        <circle cx={cx} cy={cy} r={r * 0.48} fill="white" />
        <text x={cx} y={cy - 6} textAnchor="middle" fontSize="14" fontWeight="bold" fill="#111827">
          {total}
        </text>
        <text x={cx} y={cy + 10} textAnchor="middle" fontSize="8" fill="#6b7280">readings</text>
      </svg>
      <div className="flex flex-col gap-2 text-sm">
        {slices.map((s, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-sm flex-shrink-0" style={{ background: s.fill }} />
            <span className="text-gray-700">{s.label}</span>
            <span className="font-semibold text-gray-900 ml-auto pl-4">
              {total > 0 ? Math.round(s.val / total * 100) : 0}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function Empty() {
  return (
    <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
      No data yet — readings accumulate over time
    </div>
  )
}

function InsightCard({ label, value, sub, accent = 'emerald' }) {
  const colors = {
    emerald: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    red: 'border-red-200 bg-red-50 text-red-800',
    blue: 'border-blue-200 bg-blue-50 text-blue-800',
    amber: 'border-amber-200 bg-amber-50 text-amber-800',
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

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Analytics() {
  const [daily, setDaily] = useState([])
  const [weekly, setWeekly] = useState([])
  const [venues, setVenues] = useState([])
  const [dist, setDist] = useState(null)
  const [insights, setInsights] = useState(null)
  const [venueDays, setVenueDays] = useState(7)
  const [distDays, setDistDays] = useState(1)
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState(null)
  const snapshotTimer = useRef(null)

  const fetchAll = useCallback(async () => {
    try {
      const [d, w, v, di, ins] = await Promise.all([
        analyticsApi.daily(),
        analyticsApi.weekly(),
        analyticsApi.venues(venueDays),
        analyticsApi.distribution(distDays),
        analyticsApi.insights(7),
      ])
      setDaily(d)
      setWeekly(w)
      setVenues(v)
      setDist(di)
      setInsights(ins)
      setLastUpdated(new Date())
    } catch (e) {
      console.error('Analytics fetch error', e)
    } finally {
      setLoading(false)
    }
  }, [venueDays, distDays])

  // Take a snapshot then refresh data
  const takeSnapshot = useCallback(async () => {
    try { await analyticsApi.snapshot() } catch {}
    fetchAll()
  }, [fetchAll])

  useEffect(() => {
    takeSnapshot()
    // Poll every 5 min: snapshot + refresh
    snapshotTimer.current = setInterval(takeSnapshot, 5 * 60 * 1000)
    return () => clearInterval(snapshotTimer.current)
  }, [takeSnapshot])

  // Re-fetch when filter changes (no new snapshot needed)
  useEffect(() => {
    if (!loading) fetchAll()
  }, [venueDays, distDays]) // eslint-disable-line react-hooks/exhaustive-deps

  const updStr = lastUpdated
    ? lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : null

  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
            <p className="text-sm text-gray-500 mt-0.5">Campus occupancy trends — mock data, same schema as live cameras</p>
          </div>
          <div className="flex items-center gap-3">
            {updStr && <span className="text-xs text-gray-400">Updated {updStr}</span>}
            <button
              onClick={takeSnapshot}
              className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg transition-colors"
            >
              Refresh
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-64 text-gray-400">Loading analytics…</div>
        ) : (
          <>
            {/* Peak insights row */}
            {insights && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <InsightCard
                  label="Peak Hour"
                  value={insights.peak_hour ?? '—'}
                  sub={insights.peak_hour_pct != null ? `avg ${insights.peak_hour_pct}% occupancy` : null}
                  accent="blue"
                />
                <InsightCard
                  label="Peak Day"
                  value={insights.peak_day ?? '—'}
                  sub={insights.peak_day_pct != null ? `avg ${insights.peak_day_pct}%` : null}
                  accent="amber"
                />
                <InsightCard
                  label="Busiest Venue"
                  value={insights.busiest_venue ?? '—'}
                  sub={insights.busiest_pct != null ? `avg ${insights.busiest_pct}%` : null}
                  accent="red"
                />
                <InsightCard
                  label="Quietest Venue"
                  value={insights.quietest_venue ?? '—'}
                  sub={insights.quietest_pct != null ? `avg ${insights.quietest_pct}%` : null}
                  accent="emerald"
                />
              </div>
            )}

            {/* Daily + Weekly line charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card title="Daily Campus Occupancy (Today, Hourly)">
                <LineChart
                  data={daily}
                  valueKey="avg_occupancy_pct"
                  labelKey="label"
                  color="#3b82f6"
                  height={200}
                />
                <p className="text-xs text-gray-400 mt-2">Average % of seats occupied per hour across all venues</p>
              </Card>

              <Card title="Weekly Campus Occupancy (Last 7 Days)">
                <LineChart
                  data={weekly}
                  valueKey="avg_occupancy_pct"
                  labelKey="label"
                  color="#10b981"
                  height={200}
                />
                <p className="text-xs text-gray-400 mt-2">Average daily occupancy across all venues</p>
              </Card>
            </div>

            {/* Venue bar chart */}
            <Card
              title={`Venue Occupancy Comparison (Last ${venueDays} days)`}
              action={
                <select
                  value={venueDays}
                  onChange={e => setVenueDays(Number(e.target.value))}
                  className="text-xs border border-gray-200 rounded-lg px-2 py-1 text-gray-600"
                >
                  <option value={1}>Today</option>
                  <option value={7}>7 days</option>
                  <option value={14}>14 days</option>
                  <option value={30}>30 days</option>
                </select>
              }
            >
              <div className="overflow-x-auto">
                <BarChart
                  data={venues}
                  valueKey="avg_occupancy_pct"
                  labelKey="venue_name"
                  color="#6366f1"
                  height={280}
                />
              </div>
              <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
                <span className="flex items-center gap-1">
                  <span className="w-6 border-t-2 border-dashed border-red-400 inline-block" />
                  Peak reading
                </span>
                <span>Bar = average occupancy %. Sorted by avg desc.</span>
              </div>
            </Card>

            {/* Pie + distribution */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card
                title={`State Distribution (Last ${distDays === 1 ? 'Day' : distDays + ' Days'})`}
                action={
                  <select
                    value={distDays}
                    onChange={e => setDistDays(Number(e.target.value))}
                    className="text-xs border border-gray-200 rounded-lg px-2 py-1 text-gray-600"
                  >
                    <option value={1}>Today</option>
                    <option value={7}>7 days</option>
                  </select>
                }
              >
                {dist ? (
                  <>
                    <PieChart green={dist.GREEN} full={dist.FULL} red={dist.RED} size={170} />
                    <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
                      <div className="bg-emerald-50 rounded-lg py-2">
                        <p className="font-bold text-emerald-700 text-base">{dist.green_pct}%</p>
                        <p className="text-emerald-600">Available</p>
                      </div>
                      <div className="bg-red-50 rounded-lg py-2">
                        <p className="font-bold text-red-600 text-base">{dist.full_pct}%</p>
                        <p className="text-red-500">Full</p>
                      </div>
                      <div className="bg-red-100 rounded-lg py-2">
                        <p className="font-bold text-red-800 text-base">{dist.red_pct}%</p>
                        <p className="text-red-700">Booked</p>
                      </div>
                    </div>
                  </>
                ) : <Empty />}
              </Card>

              <Card title="About This Data">
                <div className="space-y-3 text-sm text-gray-600">
                  <p>
                    All readings stored in <code className="bg-gray-100 px-1 rounded text-xs">occupancy_readings</code> table
                    with a unified schema — <strong>identical whether data comes from mock or live cameras</strong>.
                  </p>
                  <p>
                    The system records a snapshot every <strong>15 minutes</strong> during seeding, and every
                    <strong> 4 minutes</strong> from live polls. Camera data is always recorded immediately.
                  </p>
                  <p>
                    Each reading stores: venue, timestamp, occupied count, total seats, occupancy %, availability state,
                    data source (MOCK/CAMERA), and booking status.
                  </p>
                  <p className="text-xs text-gray-400 pt-2 border-t border-gray-100">
                    Forecasting and prediction features will consume this same table — no migration needed when cameras are connected.
                  </p>
                </div>
              </Card>
            </div>
          </>
        )}
      </div>
    </Layout>
  )
}
