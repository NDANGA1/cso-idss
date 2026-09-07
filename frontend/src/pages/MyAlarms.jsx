// MyAlarms.jsx — shows and manages alarms the user has set

import { useNavigate, Link } from 'react-router-dom'
import Layout from '../components/Layout.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import EmptyState from '../components/EmptyState.jsx'
import { alarmsApi } from '../api/alarms.js'
import { useAuth } from '../context/AuthContext.jsx'
import { useAlarms } from '../context/AlarmContext.jsx'
import { useEffect, useState } from 'react'

export default function MyAlarms() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { alarms, setAlarms } = useAlarms()
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState('')

  useEffect(() => {
    if (!user) { navigate('/login'); return }
    setLoading(false)
  }, [user])

  const handleDelete = async (id) => {
    try {
      await alarmsApi.delete(id)
      setAlarms(prev => prev.filter(a => a.id !== id))
      setToast('Alarm removed.')
    } catch (e) {
      setToast(e.message)
    }
    setTimeout(() => setToast(''), 3000)
  }

  if (loading) return <Layout><LoadingSpinner message="Loading alarms..." /></Layout>

  const waiting = alarms.filter(a => !a.triggered)
  const triggered = alarms.filter(a => a.triggered)

  return (
    <Layout>
      {toast && (
        <div className="fixed top-20 right-4 z-50 bg-blue-700 text-white text-sm font-medium px-4 py-3 rounded-xl shadow-lg">
          {toast}
        </div>
      )}

      <div className="mb-6">
        <h1 className="text-2xl font-black text-gray-900">My Alarms</h1>
        <p className="text-sm text-gray-500 mt-1">
          Checked every 10 seconds · rings + vibrates when a RED venue goes GREEN
        </p>
      </div>

      {alarms.length === 0 ? (
        <EmptyState
          title="No alarms set"
          message="Browse venues and tap 'Set Alarm' on any occupied space to get notified when it's free."
          action={{ label: 'Browse Live Venues', onClick: () => navigate('/venues') }}
        />
      ) : (
        <div className="flex flex-col gap-6">

          {/* Triggered */}
          {triggered.length > 0 && (
            <section>
              <div className="flex items-center gap-2 mb-3">
                <span className="w-2.5 h-2.5 bg-emerald-500 rounded-full" />
                <h2 className="text-sm font-bold text-gray-700">Triggered — venue is FREE ({triggered.length})</h2>
              </div>
              <div className="flex flex-col gap-3">
                {triggered.map(a => (
                  <AlarmRow key={a.id} alarm={a} onDelete={handleDelete} />
                ))}
              </div>
            </section>
          )}

          {/* Waiting */}
          {waiting.length > 0 && (
            <section>
              <div className="flex items-center gap-2 mb-3">
                <span className="w-2.5 h-2.5 bg-amber-400 rounded-full animate-pulse" />
                <h2 className="text-sm font-bold text-gray-700">Waiting for venue ({waiting.length})</h2>
              </div>
              <div className="flex flex-col gap-3">
                {waiting.map(a => (
                  <AlarmRow key={a.id} alarm={a} onDelete={handleDelete} />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </Layout>
  )
}

function AlarmRow({ alarm: a, onDelete }) {
  return (
    <div className={`card p-4 flex items-start justify-between gap-4 border-l-4 transition-colors ${
      a.triggered ? 'border-l-emerald-500 bg-emerald-50/40' : 'border-l-amber-400'
    }`}>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${
            a.triggered
              ? 'bg-emerald-100 text-emerald-700'
              : 'bg-amber-100 text-amber-700'
          }`}>
            {a.triggered ? 'TRIGGERED' : 'WAITING'}
          </span>
          <span className="text-xs text-gray-400">Venue #{a.venue_id}</span>
        </div>

        <p className="text-sm font-medium text-gray-800 leading-tight">
          {a.note || 'Notify me when this venue is free'}
        </p>

        {a.triggered && a.triggered_at && (
          <p className="text-xs text-emerald-600 mt-1 font-medium">
            Fired at {new Date(a.triggered_at).toLocaleString('en-GB', {
              hour: '2-digit', minute: '2-digit', second: '2-digit',
              day: '2-digit', month: 'short'
            })}
          </p>
        )}

        <p className="text-xs text-gray-400 mt-1">
          Set on {new Date(a.created_at).toLocaleDateString('en-GB', {
            day: '2-digit', month: 'short', year: 'numeric'
          })}
        </p>
      </div>

      <button
        onClick={() => onDelete(a.id)}
        className="flex-shrink-0 text-xs font-medium text-red-500 hover:text-red-700 hover:bg-red-50 px-3 py-1.5 rounded-lg transition-colors">
        Remove
      </button>
    </div>
  )
}
