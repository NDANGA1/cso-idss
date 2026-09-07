// AlarmAlert.jsx — pops up when a venue the user set an alarm for goes free

import { useEffect, useState } from 'react'

/**
 * Full-screen alarm modal that rings until the user snoozes.
 * Props:
 *   alarm  — the triggered alarm object
 *   onSnooze — callback to stop sound + close
 */
export default function AlarmAlert({ alarm, onSnooze }) {
  const [pulse, setPulse] = useState(true)

  // Alternate the pulse ring colour for visual urgency
  useEffect(() => {
    const t = setInterval(() => setPulse(p => !p), 600)
    return () => clearInterval(t)
  }, [])

  if (!alarm) return null

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.85)' }}>

      {/* Pulsing ring behind the card */}
      <div className={`absolute w-72 h-72 rounded-full transition-all duration-500 ${
        pulse ? 'scale-110 opacity-30' : 'scale-90 opacity-10'
      }`}
        style={{ background: 'radial-gradient(circle, #ef4444, transparent)' }} />

      <div className="relative bg-white rounded-3xl shadow-2xl p-8 max-w-sm w-full text-center">

        {/* Animated bell icon */}
        <div className={`w-20 h-20 mx-auto mb-4 rounded-full flex items-center justify-center transition-colors duration-500 ${
          pulse ? 'bg-red-100' : 'bg-emerald-100'
        }`}>
          <svg className={`w-10 h-10 transition-colors duration-500 ${pulse ? 'text-red-500' : 'text-emerald-500'}`}
            fill="currentColor" viewBox="0 0 24 24">
            <path d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
        </div>

        <div className={`inline-block text-xs font-bold px-3 py-1 rounded-full mb-3 transition-colors duration-500 ${
          pulse ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'
        }`}>
          VENUE NOW AVAILABLE
        </div>

        <h2 className="text-xl font-black text-gray-900 mb-2">
          Your Alarm Fired!
        </h2>

        <p className="text-gray-600 text-sm mb-1">
          {alarm.note || 'A venue you were waiting for is now free.'}
        </p>

        {alarm.triggered_at && (
          <p className="text-xs text-gray-400 mb-6">
            Freed at{' '}
            {new Date(alarm.triggered_at).toLocaleTimeString('en-GB', {
              hour: '2-digit', minute: '2-digit', second: '2-digit'
            })}
          </p>
        )}

        <button
          onClick={onSnooze}
          className={`w-full font-bold rounded-2xl py-4 text-white text-base transition-all duration-300 shadow-lg active:scale-95 ${
            pulse
              ? 'bg-red-500 hover:bg-red-600 shadow-red-200'
              : 'bg-emerald-500 hover:bg-emerald-600 shadow-emerald-200'
          }`}>
          Snooze / Got It
        </button>

        <p className="text-xs text-gray-400 mt-3">
          Alarm will keep ringing until you dismiss it
        </p>
      </div>
    </div>
  )
}
