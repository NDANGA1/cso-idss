// api/forecast.js — forecast API calls

import { api } from './client.js'

export const forecastApi = {
  campus24h: () => api.get('/forecast/campus/24h').then(r => r.data ?? []),
  campus7days: () => api.get('/forecast/campus/7days').then(r => r.data ?? []),
  venue24h: (id) => api.get(`/forecast/venue/${id}/24h`).then(r => r.data ?? []),
  peaks: () => api.get('/forecast/peaks'),
  modelInfo: () => api.get('/forecast/model/info'),
  retrain: () => api.post('/forecast/retrain'),
}
