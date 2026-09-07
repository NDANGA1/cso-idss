// CreateBooking.jsx — lets staff create bookings for venues

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../../components/Layout.jsx'
import { bookingsApi } from '../../api/bookings.js'
import { venuesApi } from '../../api/venues.js'
import { useAuth } from '../../context/AuthContext.jsx'

const DAYS = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']

// Roles that must use a specific date (one-time only)
const ONE_TIME_ONLY = ['LECTURER', 'IFMSO']
// Roles that can create recurring slots
const CAN_RECUR = ['TIMETABLER', 'ADMIN']

export default function CreateBooking() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [venues, setVenues] = useState([])
  const [form, setForm] = useState({
    venue_id: '',
    course_code: '',
    course_name: '',
    booking_date: '',   // specific date for one-time
    day_of_week: '',    // used when recurring (timetabler)
    start_time: '',
    end_time: '',
    recurring: false,   // timetabler toggle
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    if (!user) { navigate('/login'); return }
    if (user.role === 'STUDENT') { navigate('/'); return }
    venuesApi.getLive().then(data => setVenues(data)).catch(console.error)
  }, [user])

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const isRecurring = CAN_RECUR.includes(user?.role) && form.recurring
  const mustUseDate = ONE_TIME_ONLY.includes(user?.role)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')

    if (!form.venue_id) { setError('Select a venue.'); return }
    if (!form.start_time || !form.end_time) { setError('Set start and end times.'); return }
    if (form.start_time >= form.end_time) { setError('End time must be after start time.'); return }

    if (isRecurring && !form.day_of_week) { setError('Select a day of week for recurring booking.'); return }
    if (!isRecurring && !form.booking_date) { setError('Select a specific date.'); return }

    setLoading(true)
    try {
      const payload = {
        venue_id: Number(form.venue_id),
        course_code: form.course_code || null,
        course_name: form.course_name || null,
        start_time: form.start_time,
        end_time: form.end_time,
      }
      if (isRecurring) {
        payload.day_of_week = form.day_of_week
      } else {
        payload.booking_date = form.booking_date
      }

      await bookingsApi.create(payload)
      setSuccess('Booking created successfully!')
      setForm(f => ({ ...f, course_code: '', course_name: '', booking_date: '', start_time: '', end_time: '' }))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  if (!user) return null

  return (
    <Layout>
      <div className="max-w-xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-black text-gray-900">Create Booking</h1>
          <p className="text-sm text-gray-500 mt-1">
            {mustUseDate
              ? 'One-time booking — automatically released after end time.'
              : 'Create a recurring weekly slot or a one-time manual override.'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="card p-6 flex flex-col gap-5">

          {/* Recurring toggle — timetabler/admin only */}
          {CAN_RECUR.includes(user.role) && (
            <div className="flex items-center justify-between bg-blue-50 rounded-xl px-4 py-3">
              <div>
                <p className="text-sm font-semibold text-blue-900">Recurring weekly slot</p>
                <p className="text-xs text-blue-600">Persists every week until manually deleted</p>
              </div>
              <button type="button"
                onClick={() => set('recurring', !form.recurring)}
                className={`relative w-12 h-6 rounded-full transition-colors ${form.recurring ? 'bg-blue-600' : 'bg-gray-300'}`}>
                <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${form.recurring ? 'translate-x-7' : 'translate-x-1'}`} />
              </button>
            </div>
          )}

          {/* Venue */}
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">Venue *</label>
            <select required value={form.venue_id} onChange={e => set('venue_id', e.target.value)}
              className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="">Select a venue...</option>
              {venues.map(v => (
                <option key={v.venue_id} value={v.venue_id}>
                  {v.venue_name} (cap. {v.capacity}) — {v.availability_state}
                </option>
              ))}
            </select>
          </div>

          {/* Date or day selector */}
          {isRecurring ? (
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Day of Week *</label>
              <select required value={form.day_of_week} onChange={e => set('day_of_week', e.target.value)}
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                <option value="">Select day...</option>
                {DAYS.map(d => <option key={d} value={d}>{d.charAt(0) + d.slice(1).toLowerCase()}</option>)}
              </select>
            </div>
          ) : (
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Date *</label>
              <input type="date" required
                min={new Date().toISOString().split('T')[0]}
                value={form.booking_date} onChange={e => set('booking_date', e.target.value)}
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              {form.booking_date && (
                <p className="text-xs text-gray-400 mt-1">
                  {new Date(form.booking_date + 'T00:00:00').toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
                </p>
              )}
            </div>
          )}

          {/* Time range */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Start Time *</label>
              <input type="time" required value={form.start_time} onChange={e => set('start_time', e.target.value)}
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">End Time *</label>
              <input type="time" required value={form.end_time} onChange={e => set('end_time', e.target.value)}
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
          </div>

          {/* Course / purpose info */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Course Code</label>
              <input type="text" placeholder="e.g. CSE3204"
                value={form.course_code} onChange={e => set('course_code', e.target.value)}
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Purpose / Course Name</label>
              <input type="text" placeholder="e.g. Database Systems"
                value={form.course_name} onChange={e => set('course_name', e.target.value)}
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
              {error}
            </div>
          )}
          {success && (
            <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm rounded-xl px-4 py-3">
              {success}
            </div>
          )}

          <div className="flex gap-3">
            <button type="submit" disabled={loading}
              className="flex-1 bg-blue-900 hover:bg-blue-800 text-white font-bold rounded-xl py-3 text-sm transition-colors disabled:opacity-60">
              {loading ? 'Creating...' : 'Create Booking'}
            </button>
            <button type="button" onClick={() => navigate('/staff/bookings')}
              className="px-5 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-xl py-3 text-sm transition-colors">
              My Bookings
            </button>
          </div>
        </form>

        {/* Info box */}
        <div className="mt-4 bg-amber-50 border border-amber-100 rounded-2xl p-4 text-xs text-amber-800">
          {mustUseDate ? (
            <>
              <strong>One-time booking:</strong> this venue will be marked RED from your start time
              to end time on the selected date only. It releases automatically.
            </>
          ) : isRecurring ? (
            <>
              <strong>Recurring slot:</strong> this booking will repeat every{' '}
              {form.day_of_week ? form.day_of_week.charAt(0) + form.day_of_week.slice(1).toLowerCase() : 'selected day'}{' '}
              permanently. Delete it from My Bookings when no longer needed.
            </>
          ) : (
            <>
              <strong>One-time override:</strong> marks the venue RED on the selected date only,
              then releases automatically after end time.
            </>
          )}
        </div>
      </div>
    </Layout>
  )
}
