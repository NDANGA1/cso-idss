// api/alarms.js — alarm API calls

import { api } from './client.js'

export const alarmsApi = {
  list: () => api.get('/alarms/'),
  create: (venue_id, note) => api.post('/alarms/', { venue_id, note }),
  delete: (id) => api.delete(`/alarms/${id}`),
}
