// api/auth.js — login and registration API calls

import { api } from './client.js'

export const authApi = {
  login: (email, password) => api.post('/auth/login', { email, password }),
  register: (name, email, password, role = 'STUDENT') =>
    api.post('/auth/register', { name, email, password, role }),
  me: () => api.get('/auth/me'),
}
