// api/venues.js — venue API calls

import { api } from './client.js'

export const venuesApi = {
  getLive: () => api.get('/venues/live'),
  getSummary: () => api.get('/venues/summary'),
  getVenue: (id) => api.get(`/venues/${id}/live`),
  getSchedule: (id, day) => api.get(`/venues/${id}/schedule${day ? `?day=${day}` : ''}`).then(r => r.schedule ?? []),
  getForecast: (id, day) => api.get(`/venues/${id}/forecast${day ? `?day=${day}` : ''}`).then(r => r.forecast ?? []),
  search: (params) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => { if (v !== '' && v !== null && v !== undefined) q.append(k, v) })
    return api.get(`/venues/search?${q}`).then(r => r.results ?? r)
  },
  updateOccupancy: (id, payload) => api.post(`/venues/${id}/occupancy`, payload),
  deleteVenue: (id) => api.delete(`/venues/${id}`),
  createVenue: (payload) => api.post('/venues/', payload),
}
