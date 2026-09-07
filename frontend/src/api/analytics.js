// api/analytics.js — analytics API calls

import { api } from './client.js'

export const analyticsApi = {
  snapshot: () => api.post('/analytics/snapshot'),
  daily: () => api.get('/analytics/daily').then(r => r.data ?? []),
  weekly: () => api.get('/analytics/weekly').then(r => r.data ?? []),
  venues: (days = 7) => api.get(`/analytics/venues/occupancy?days=${days}`).then(r => r.data ?? []),
  distribution: (days = 1) => api.get(`/analytics/distribution?days=${days}`),
  insights: (days = 7) => api.get(`/analytics/insights?days=${days}`),
}
