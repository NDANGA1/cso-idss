// AlarmContext.jsx
// Polls the alarms API every 30s and triggers the alarm popup
// when a triggered alarm is detected.

import { createContext, useContext } from 'react'
import { useAlarmWatcher } from '../hooks/useAlarmWatcher.js'
import { useAuth } from './AuthContext.jsx'

const AlarmContext = createContext(null)

export function AlarmProvider({ children }) {
  const { user } = useAuth()
  const watcher = useAlarmWatcher(!!user)
  return <AlarmContext.Provider value={watcher}>{children}</AlarmContext.Provider>
}

export const useAlarms = () => useContext(AlarmContext)
