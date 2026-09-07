// api/bookings.js — booking API calls

import { api } from './client.js'

export const bookingsApi = {
  my: () => api.get('/bookings/my'),
  list: (params = {}) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => { if (v) q.append(k, v) })
    return api.get(`/bookings/?${q}`)
  },
  all: (params = {}) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => { if (v) q.append(k, v) })
    return api.get(`/bookings/all?${q}`)
  },
  create: (payload) => api.post('/bookings/', payload),
  cancel: (id) => api.delete(`/bookings/${id}`),
}
