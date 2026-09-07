// api/seatmap.js — seatmap API calls

import { api } from './client.js'

export const seatmapApi = {
  get: (venueId) => api.get(`/venues/${venueId}/seatmap`),
  updateStates: (venueId, states) =>
    api.post(`/venues/${venueId}/seatmap/states`, { states }),
  saveLayout: (venueId, layout) =>
    api.post(`/venues/${venueId}/seatmap/layout`, layout),
}
