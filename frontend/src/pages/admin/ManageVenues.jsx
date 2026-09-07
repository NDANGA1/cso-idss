// ManageVenues.jsx — admin CRUD for venues

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../../components/Layout.jsx'
import LoadingSpinner from '../../components/LoadingSpinner.jsx'
import { venuesApi } from '../../api/venues.js'
import { useAuth } from '../../context/AuthContext.jsx'

const ADMIN_ROLES = ['ADMIN', 'TIMETABLER']

export default function ManageVenues() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [venues, setVenues] = useState([])
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState({ msg: '', ok: true })
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ name: '', capacity: '' })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!user) { navigate('/login'); return }
    if (!ADMIN_ROLES.includes(user.role)) { navigate('/'); return }
    fetchVenues()
  }, [user])

  const fetchVenues = async () => {
    setLoading(true)
    try {
      const data = await venuesApi.getLive()
      setVenues(data)
    } catch (e) { showToast(e.message, false) }
    finally { setLoading(false) }
  }

  const showToast = (msg, ok = true) => {
    setToast({ msg, ok })
    setTimeout(() => setToast({ msg: '', ok: true }), 3000)
  }

  const handleDelete = async (id, name) => {
    if (!confirm(`Delete venue "${name}"? This will also remove all its bookings.`)) return
    try {
      await venuesApi.deleteVenue(id)
      setVenues(prev => prev.filter(v => v.venue_id !== id))
      showToast(`"${name}" deleted.`)
    } catch (e) { showToast(e.message, false) }
  }

  const handleAdd = async (e) => {
    e.preventDefault()
    if (!form.name.trim()) return
    setSaving(true)
    try {
      await venuesApi.createVenue({ name: form.name.trim(), capacity: Number(form.capacity) || 60, total_seats: Number(form.capacity) || 60 })
      showToast(`Venue "${form.name}" created.`)
      setForm({ name: '', capacity: '' })
      setShowAdd(false)
      fetchVenues()
    } catch (e) { showToast(e.message, false) }
    finally { setSaving(false) }
  }

  if (loading) return <Layout><LoadingSpinner message="Loading venues..." /></Layout>

  const filtered = venues.filter(v => !search || v.venue_name.toLowerCase().includes(search.toLowerCase()))

  return (
    <Layout>
      {toast.msg && (
        <div className={`fixed top-20 right-4 z-50 text-white text-sm font-medium px-4 py-3 rounded-xl shadow-lg ${toast.ok ? 'bg-blue-700' : 'bg-red-600'}`}>
          {toast.msg}
        </div>
      )}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-black text-gray-900">Manage Venues</h1>
          <p className="text-sm text-gray-500 mt-1">{venues.length} venues total</p>
        </div>
        <button onClick={() => setShowAdd(!showAdd)}
          className="bg-blue-900 hover:bg-blue-800 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors">
          + Add Venue
        </button>
      </div>

      {/* Add venue form */}
      {showAdd && (
        <form onSubmit={handleAdd} className="card p-5 mb-6 flex flex-col sm:flex-row gap-3 items-end">
          <div className="flex-1">
            <label className="block text-xs font-semibold text-gray-600 mb-1">Venue Name *</label>
            <input type="text" required placeholder="e.g. LH 101"
              value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div className="w-32">
            <label className="block text-xs font-semibold text-gray-600 mb-1">Capacity</label>
            <input type="number" min="1" placeholder="60"
              value={form.capacity} onChange={e => setForm(f => ({ ...f, capacity: e.target.value }))}
              className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div className="flex gap-2">
            <button type="submit" disabled={saving}
              className="bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors disabled:opacity-60">
              {saving ? 'Saving...' : 'Save'}
            </button>
            <button type="button" onClick={() => setShowAdd(false)}
              className="bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-semibold px-4 py-2.5 rounded-xl transition-colors">
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Search */}
      <input type="text" placeholder="Search venues..."
        value={search} onChange={e => setSearch(e.target.value)}
        className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-blue-500" />

      {/* Venue list */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {['ID', 'Name', 'Capacity', 'Status', 'Data Mode', ''].map(h => (
                  <th key={h} className="text-left text-xs font-semibold text-gray-500 px-4 py-3 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map(v => (
                <tr key={v.venue_id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-gray-400 text-xs">#{v.venue_id}</td>
                  <td className="px-4 py-3 font-medium text-gray-800">{v.venue_name}</td>
                  <td className="px-4 py-3 text-gray-600">{v.capacity}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${
                      v.availability_state === 'GREEN' ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      : v.availability_state === 'RED' ? 'bg-red-50 text-red-700 border-red-200'
                      : 'bg-amber-50 text-amber-700 border-amber-200'
                    }`}>
                      {v.availability_state}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">{v.data_mode}</td>
                  <td className="px-4 py-3 whitespace-nowrap flex gap-2">
                    <button onClick={() => navigate(`/venues/${v.venue_id}`)}
                      className="text-xs font-medium text-blue-600 hover:bg-blue-50 px-3 py-1.5 rounded-lg transition-colors">
                      View
                    </button>
                    {user.role === 'ADMIN' && (
                      <button onClick={() => handleDelete(v.venue_id, v.venue_name)}
                        className="text-xs font-medium text-red-600 hover:bg-red-50 px-3 py-1.5 rounded-lg transition-colors">
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
  )
}
