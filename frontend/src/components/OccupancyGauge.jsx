// OccupancyGauge.jsx — circular gauge showing occupancy percentage

export default function OccupancyGauge({ percentage, size = 120 }) {
  const radius = (size - 16) / 2
  const circumference = 2 * Math.PI * radius
  const pct = Math.min(100, Math.max(0, percentage))
  // Gauge goes from red (0%) to green (100%)
  const offset = circumference - (pct / 100) * circumference
  const color = pct >= 70 ? '#10b981' : pct >= 30 ? '#f59e0b' : '#ef4444'

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="#e5e7eb" strokeWidth={8} />
        <circle cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={color} strokeWidth={8}
          strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.6s ease' }} />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-xl font-bold" style={{ color }}>{pct}%</span>
        <span className="text-xs text-gray-500">free</span>
      </div>
    </div>
  )
}
