// CameraView.jsx
// Shows the camera feed with seat ROI overlays.
// I display person count and per-seat occupancy badges on top of the feed.

export default function CameraView({ seats = [], dataSource = 'MOCK', venueName = '' }) {
  const W = 640
  const H = 360

  const occupiedSeats = seats.filter(s => s.occupied)

  return (
    <div className="rounded-2xl overflow-hidden bg-gray-900 shadow-xl relative">
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-950">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full animate-pulse ${dataSource === 'CAMERA' ? 'bg-red-500' : 'bg-amber-400'}`} />
          <span className="text-xs font-mono text-gray-300">
            {dataSource === 'CAMERA' ? 'LIVE · CCTV' : 'MOCK · SIMULATED'}
          </span>
        </div>
        <span className="text-xs font-mono text-gray-400">{venueName}</span>
        <span className="text-xs font-mono text-gray-400">
          {new Date().toLocaleTimeString('en-GB')}
        </span>
      </div>

      {/* Camera frame */}
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ background: '#111' }}>

        {/* Mock background — simulated camera scene */}
        <rect x="0" y="0" width={W} height={H} fill="#1a1a2e" />
        {/* Floor */}
        <rect x="0" y="0" width={W} height={H * 0.25} fill="#16213e" />
        {/* Front wall (bottom) */}
        <rect x="0" y={H * 0.85} width={W} height={H * 0.15} fill="#0f3460" />
        {/* Board at bottom — front of room */}
        <rect x={W * 0.15} y={H * 0.87} width={W * 0.7} height={H * 0.08} fill="#e2e8f0" rx={2} />
        <text x={W * 0.5} y={H * 0.935} textAnchor="middle" fontSize={10} fill="#64748b">WHITEBOARD</text>
        {/* Scan lines for CCTV feel */}
        {Array.from({ length: 18 }).map((_, i) => (
          <line key={i} x1={0} y1={i * 20} x2={W} y2={i * 20}
            stroke="rgba(255,255,255,0.015)" strokeWidth={1} />
        ))}

        {/* Seat ROI bounding boxes */}
        {seats.map(seat => {
          if (!seat.roi) return null
          const x = seat.roi.x * W
          const y = seat.roi.y * H
          const w = seat.roi.w * W
          const h = seat.roi.h * H
          const occupied = seat.occupied

          return (
            <g key={seat.id}>
              <rect
                x={x} y={y} width={w} height={h}
                fill={occupied ? 'rgba(239,68,68,0.15)' : 'rgba(16,185,129,0.15)'}
                stroke={occupied ? '#ef4444' : '#10b981'}
                strokeWidth={1.5}
                rx={2}
              />
              {/* Seat ID label */}
              <rect x={x} y={y - 13} width={w * 0.8} height={12} fill={occupied ? '#ef4444' : '#10b981'} rx={2} />
              <text x={x + 3} y={y - 3} fontSize={8} fill="white" fontFamily="monospace" fontWeight="bold">
                {seat.id}
              </text>
              {/* Person silhouette for occupied seats */}
              {occupied && (
                <ellipse cx={x + w / 2} cy={y + h * 0.35} rx={w * 0.2} ry={h * 0.25}
                  fill="rgba(239,68,68,0.3)" stroke="#ef4444" strokeWidth={1} />
              )}
            </g>
          )
        })}

        {/* Person count overlay */}
        <rect x={8} y={H - 36} width={160} height={28} fill="rgba(0,0,0,0.7)" rx={4} />
        <text x={16} y={H - 18} fontSize={13} fill="white" fontFamily="monospace" fontWeight="bold">
          {`People: ${occupiedSeats.length} / ${seats.length}`}
        </text>

        {/* MOCK watermark */}
        {dataSource === 'MOCK' && (
          <text x={W - 8} y={H - 8} textAnchor="end" fontSize={9}
            fill="rgba(251,191,36,0.6)" fontFamily="monospace" fontWeight="bold">
            MOCK DATA — AWAITING CCTV
          </text>
        )}

        {/* Corner timestamp */}
        <text x={W - 8} y={16} textAnchor="end" fontSize={9}
          fill="rgba(255,255,255,0.5)" fontFamily="monospace">
          {new Date().toLocaleString('en-GB')}
        </text>
      </svg>

      {/* Stats strip */}
      <div className="flex items-center justify-around px-4 py-2 bg-gray-950 text-xs font-mono">
        <span className="text-emerald-400">{seats.filter(s => !s.occupied).length} EMPTY</span>
        <span className="text-red-400">{occupiedSeats.length} OCCUPIED</span>
        <span className="text-gray-400">
          {seats.length ? Math.round(occupiedSeats.length / seats.length * 100) : 0}% FULL
        </span>
      </div>
    </div>
  )
}
