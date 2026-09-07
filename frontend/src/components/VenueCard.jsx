// VenueCard.jsx — card component for each venue on the dashboard

import { useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import StatusBadge from './StatusBadge.jsx'

const TILE_COLORS = {
  GREEN: 'bg-emerald-500 hover:bg-emerald-600',
  FULL:  'bg-red-500   hover:bg-red-600',
  RED:   'bg-red-700   hover:bg-red-800',
}

export default function VenueCard({ venue, onAlarm }) {
  const navigate = useNavigate()
  const [hovered, setHovered] = useState(false)
  const [popAbove, setPopAbove] = useState(true)
  const tileRef = useRef(null)
  const clickTimer = useRef(null)

  const handleMouseEnter = useCallback(() => {
    if (tileRef.current) {
      const rect = tileRef.current.getBoundingClientRect()
      // if less than 280px above the tile, pop downward instead
      setPopAbove(rect.top > 280)
    }
    setHovered(true)
  }, [])

  const state = venue.availability_state   // GREEN | FULL | RED
  const isGreen = state === 'GREEN'
  const isRed   = state === 'RED'
  const hasPhysical  = venue.physical_occupancy_pct != null
  const isOvercrowded = venue.is_overcrowded

  // Double-click navigates; single click is ignored (hover shows details)
  const handleClick = () => {
    if (clickTimer.current) {
      clearTimeout(clickTimer.current)
      clickTimer.current = null
      navigate(`/venues/${venue.venue_id}`)
    } else {
      clickTimer.current = setTimeout(() => { clickTimer.current = null }, 280)
    }
  }

  return (
    <div
      className="relative"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={() => setHovered(false)}
    >
      {/* ── Compact coloured tile ── */}
      <div
        ref={tileRef}
        onClick={handleClick}
        title="Double-click to open"
        className={`
          ${TILE_COLORS[state] ?? TILE_COLORS.RED}
          rounded-xl px-3 py-3 h-16 flex flex-col justify-between
          cursor-pointer select-none transition-colors
        `}
      >
        <p className="text-white font-bold text-sm leading-tight truncate">{venue.venue_name}</p>
        <p className="text-white/70 text-xs font-medium">
          {isGreen
            ? `${venue.free_seats} free · ${venue.availability_percentage}%`
            : isRed
              ? `Booked · ${venue.physical_occupied_seats ?? venue.current_occupancy}/${venue.capacity}`
              : `Full · ${venue.physical_occupied_seats ?? venue.current_occupancy}/${venue.capacity}`
          }
        </p>
      </div>

      {/* ── Expanded popover on hover ── */}
      {hovered && (
        <div
          className={`absolute z-50 left-0 w-72 ${popAbove ? 'bottom-[calc(100%+6px)]' : 'top-[calc(100%+6px)]'}
                     bg-white rounded-2xl shadow-2xl border border-gray-100
                     flex flex-col gap-3 p-4 pointer-events-auto`}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
        >
          {/* Header */}
          <div className="flex items-start justify-between gap-2">
            <div>
              <h3 className="font-bold text-gray-900 text-base leading-tight">{venue.venue_name}</h3>
              <p className="text-xs text-gray-500 mt-0.5">
                {venue.data_mode === 'LIVE' ? 'AI Camera' : 'Timetable'}
                {' · '}
                <span className="italic">double-click to open</span>
              </p>
            </div>
            <StatusBadge state={state} size="sm" />
          </div>

          {/* Stats */}
          <div className="flex items-center justify-between text-sm">
            <div className="text-center">
              <p className={`text-lg font-bold ${isGreen ? 'text-emerald-600' : 'text-amber-600'}`}>
                {venue.free_seats}
              </p>
              <p className="text-xs text-gray-500">{isGreen ? 'free seats' : 'empty seats'}</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-bold text-gray-700">{venue.capacity}</p>
              <p className="text-xs text-gray-500">capacity</p>
            </div>
            <div className="text-center">
              <p className={`text-lg font-bold ${isGreen ? 'text-emerald-600' : 'text-red-500'}`}>
                {isGreen ? `${venue.availability_percentage}%` : isRed ? 'Booked' : 'Full'}
              </p>
              <p className="text-xs text-gray-500">{isGreen ? 'available' : 'status'}</p>
            </div>
          </div>

          {/* Physical occupancy bar */}
          {!isGreen && hasPhysical && (
            <div className={`border rounded-lg px-3 py-2 ${isOvercrowded ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-100'}`}>
              <div className="flex items-center justify-between mb-1">
                <span className={`text-xs font-semibold ${isOvercrowded ? 'text-red-700' : 'text-amber-700'}`}>
                  {isOvercrowded ? `OVERCROWDED +${venue.overcrowding_count}` : 'Actual occupancy'}
                </span>
                <span className={`text-xs font-bold ${isOvercrowded ? 'text-red-800' : 'text-amber-800'}`}>
                  {venue.physical_occupied_seats}/{venue.capacity} · {venue.physical_occupancy_pct}%
                </span>
              </div>
              <div className={`h-1.5 rounded-full overflow-hidden ${isOvercrowded ? 'bg-red-100' : 'bg-amber-100'}`}>
                <div
                  className={`h-full rounded-full transition-all ${isOvercrowded ? 'bg-red-500' : 'bg-amber-500'}`}
                  style={{ width: `${Math.min(100, venue.physical_occupancy_pct)}%` }}
                />
              </div>
            </div>
          )}

          {/* Expected free time */}
          {!isGreen && venue.expected_free_time && (
            <p className="text-xs text-red-600 bg-red-50 rounded-lg px-3 py-1.5">
              Free at {new Date(venue.expected_free_time).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}
              {venue.current_holder && ` · ${venue.current_holder}`}
            </p>
          )}

          {/* Alarm button */}
          {!isGreen && (
            <button
              onClick={(e) => { e.stopPropagation(); onAlarm?.(venue) }}
              className="w-full text-xs font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-lg py-1.5 transition-colors">
              Set Alarm (notify when free)
            </button>
          )}
        </div>
      )}
    </div>
  )
}
