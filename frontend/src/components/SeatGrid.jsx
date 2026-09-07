// SeatGrid.jsx
// Renders the interactive seat map grid. Each seat is coloured
// green/red based on whether the camera detected someone there.
// I pull seat states from the API and refresh every few seconds.

import { useState } from 'react'

/**
 * SVG seat grid.
 *
 * When seats have ROI data (from calibration), positions each seat according to
 * its real-world camera location so the grid mirrors the actual room layout.
 * Every seat is rendered at a uniform size regardless of ROI dimensions.
 *
 * Falls back to a regular row/col grid when ROI data is absent.
 */
export default function SeatGrid({ seats = [], rows, cols, aisleAfterCol, changedIds = new Set() }) {
  const [tooltip, setTooltip] = useState(null)

  if (!seats.length) return <p className="text-sm text-gray-400 text-center py-8">No seat data.</p>

  const hasROI = seats.some(s => s.roi && s.roi.x != null)

  const SEAT_W = 38
  const SEAT_H = 32

  //
  // MODE A: ROI-based layout (mirrors camera view positions, uniform size)
  //
  if (hasROI) {
    const VW = 640
    const VH = 360
    const PAD = 20

    const totalW = VW + PAD * 2
    const totalH = VH + PAD * 2 + 28

    const seatPos = seats.map(s => {
      const cx = s.roi ? (s.roi.x + s.roi.w / 2) * VW + PAD : 0
      const cy = s.roi ? (s.roi.y + s.roi.h / 2) * VH + PAD : 0
      return { ...s, sx: cx - SEAT_W / 2, sy: cy - SEAT_H / 2 }
    })

    return (
      <div className="relative overflow-x-auto">
        <svg
          viewBox={`0 0 ${totalW} ${totalH}`}
          className="w-full max-w-3xl mx-auto"
          style={{ minWidth: 320 }}
          onMouseLeave={() => setTooltip(null)}
        >
          {/* Room background */}
          <rect x={PAD} y={PAD} width={VW} height={VH}
            fill="#f8fafc" stroke="#e2e8f0" strokeWidth={1} rx={4} />

          {/* Subtle grid lines */}
          {Array.from({ length: 5 }).map((_, i) => (
            <line key={`h${i}`}
              x1={PAD} y1={PAD + (VH / 4) * i}
              x2={PAD + VW} y2={PAD + (VH / 4) * i}
              stroke="#e2e8f0" strokeWidth={0.5} />
          ))}

          {/* Seats positioned by ROI centre, uniform size */}
          {seatPos.map(seat => {
            const occupied = seat.occupied
            const changed  = changedIds.has(seat.id)
            const x = seat.sx, y = seat.sy

            return (
              <g key={seat.id}
                onMouseEnter={() => setTooltip({ seat, x, y })}
                style={{ cursor: 'pointer' }}>
                {changed && (
                  <rect x={x-3} y={y-3} width={SEAT_W+6} height={SEAT_H+6} rx={6}
                    fill="none" stroke={occupied ? '#ef4444' : '#10b981'}
                    strokeWidth={2} opacity={0.5} className="animate-ping" />
                )}
                <rect x={x} y={y} width={SEAT_W} height={SEAT_H} rx={4}
                  fill={occupied ? '#fca5a5' : '#bbf7d0'}
                  stroke={occupied ? '#ef4444' : '#10b981'}
                  strokeWidth={1.5} />
                <rect x={x+3} y={y} width={SEAT_W-6} height={7} rx={2}
                  fill={occupied ? '#ef4444' : '#10b981'} opacity={0.7} />
                <text x={x + SEAT_W/2} y={y + SEAT_H - 7}
                  textAnchor="middle" fontSize={8}
                  fill={occupied ? '#7f1d1d' : '#064e3b'}
                  fontFamily="monospace" fontWeight="600">
                  {seat.id}
                </text>
              </g>
            )
          })}

          {/* Front / Board label */}
          <rect x={PAD + VW*0.2} y={PAD + VH + 6} width={VW*0.6} height={16}
            rx={3} fill="#e2e8f0" />
          <text x={PAD + VW/2} y={PAD + VH + 18}
            textAnchor="middle" fontSize={9} fill="#64748b"
            fontFamily="monospace" fontWeight="600" letterSpacing="2">
            ── FRONT / BOARD ──
          </text>
        </svg>

        <Legend />
        <Tooltip tooltip={tooltip} />
      </div>
    )
  }

  //
  // MODE B: Regular row/col grid (no ROI data)
  //
  const GAP_X   = 6
  const GAP_Y   = 8
  const AISLE   = 24
  const LABEL_W = 28
  const LABEL_H = 22
  const PADDING = 10

  const colX = (col) => {
    const aisle = aisleAfterCol != null && col > aisleAfterCol ? AISLE : 0
    return LABEL_W + PADDING + col * (SEAT_W + GAP_X) + aisle
  }
  const maxRow = Math.max(...seats.map(s => s.row))
  const rowY   = (row) => LABEL_H + PADDING + (maxRow - row) * (SEAT_H + GAP_Y)

  const totalW = LABEL_W + PADDING + cols * (SEAT_W + GAP_X) + (aisleAfterCol != null ? AISLE : 0) + PADDING
  const totalH = LABEL_H + PADDING + rows * (SEAT_H + GAP_Y) + PADDING

  const rowLabels = {}, colLabels = {}
  seats.forEach(s => {
    if (!rowLabels[s.row]) rowLabels[s.row] = s.row_label
    if (!colLabels[s.col]) colLabels[s.col] = s.col_label
  })

  return (
    <div className="relative overflow-x-auto">
      <svg
        viewBox={`0 0 ${totalW} ${totalH}`}
        className="w-full max-w-3xl mx-auto"
        style={{ minWidth: Math.min(totalW, 320) }}
        onMouseLeave={() => setTooltip(null)}
      >
        {Object.entries(colLabels).map(([col, label]) => (
          <text key={`cl-${col}`}
            x={colX(Number(col)) + SEAT_W/2} y={LABEL_H-4}
            textAnchor="middle" fontSize={9} fill="#9ca3af" fontFamily="monospace">
            {label}
          </text>
        ))}
        {Object.entries(rowLabels).map(([row, label]) => (
          <text key={`rl-${row}`}
            x={LABEL_W-4} y={rowY(Number(row)) + SEAT_H/2 + 4}
            textAnchor="end" fontSize={9} fill="#9ca3af" fontFamily="monospace">
            {label}
          </text>
        ))}
        {aisleAfterCol != null && (
          <rect
            x={colX(aisleAfterCol) + SEAT_W + GAP_X/2} y={LABEL_H}
            width={AISLE - GAP_X} height={totalH - LABEL_H - PADDING/2}
            fill="#f3f4f6" rx={3} />
        )}
        {seats.map(seat => {
          const x = colX(seat.col), y = rowY(seat.row)
          const occupied = seat.occupied
          const changed  = changedIds.has(seat.id)
          return (
            <g key={seat.id}
              onMouseEnter={() => setTooltip({ seat, x, y })}
              style={{ cursor: 'pointer' }}>
              {changed && (
                <rect x={x-3} y={y-3} width={SEAT_W+6} height={SEAT_H+6} rx={6}
                  fill="none" stroke={occupied ? '#ef4444' : '#10b981'}
                  strokeWidth={2} opacity={0.5} className="animate-ping" />
              )}
              <rect x={x} y={y} width={SEAT_W} height={SEAT_H} rx={4}
                fill={occupied ? '#fca5a5' : '#bbf7d0'}
                stroke={occupied ? '#ef4444' : '#10b981'} strokeWidth={1.5} />
              <rect x={x+3} y={y} width={SEAT_W-6} height={7} rx={2}
                fill={occupied ? '#ef4444' : '#10b981'} opacity={0.7} />
              <text x={x + SEAT_W/2} y={y + SEAT_H - 7}
                textAnchor="middle" fontSize={8}
                fill={occupied ? '#7f1d1d' : '#064e3b'}
                fontFamily="monospace" fontWeight="600">
                {seat.id}
              </text>
            </g>
          )
        })}
      </svg>
      <div className="text-center text-xs font-semibold text-gray-400 mt-2 mb-1 tracking-widest uppercase">
        ── Front / Board ──
      </div>
      <Legend />
      <Tooltip tooltip={tooltip} />
    </div>
  )
}

function Legend() {
  return (
    <div className="flex items-center justify-center gap-6 mt-4 text-xs text-gray-500">
      <span className="flex items-center gap-1.5">
        <span className="w-4 h-4 rounded bg-emerald-200 border border-emerald-500 inline-block" />
        Empty seat
      </span>
      <span className="flex items-center gap-1.5">
        <span className="w-4 h-4 rounded bg-red-200 border border-red-400 inline-block" />
        Occupied seat
      </span>
    </div>
  )
}

function Tooltip({ tooltip }) {
  if (!tooltip) return null
  return (
    <div className="absolute z-10 pointer-events-none bg-gray-900 text-white text-xs rounded-lg px-3 py-2 shadow-xl"
      style={{ top: 40, left: '50%', transform: 'translateX(-50%)' }}>
      <p className="font-bold">{tooltip.seat.id}</p>
      <p>{tooltip.seat.occupied ? 'Occupied' : 'Empty'}</p>
      <p className="text-gray-400">Confidence: {Math.round((tooltip.seat.confidence ?? 1) * 100)}%</p>
    </div>
  )
}
