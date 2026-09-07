// App.jsx — root component, sets up routing
// I define all the page routes here and wrap everything in context providers.

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext.jsx'
import { AlarmProvider, useAlarms } from './context/AlarmContext.jsx'
import AlarmAlert from './components/AlarmAlert.jsx'
import Dashboard from './pages/Dashboard.jsx'
import LiveVenues from './pages/LiveVenues.jsx'
import Search from './pages/Search.jsx'
import VenueDetail from './pages/VenueDetail.jsx'
import MyAlarms from './pages/MyAlarms.jsx'
import Login from './pages/Login.jsx'
import CreateBooking from './pages/staff/CreateBooking.jsx'
import MyBookings from './pages/staff/MyBookings.jsx'
import VenueLayout from './pages/VenueLayout.jsx'
import Analytics from './pages/Analytics.jsx'
import Forecast from './pages/Forecast.jsx'
import ManageBookings from './pages/admin/ManageBookings.jsx'
import ManageVenues from './pages/admin/ManageVenues.jsx'

function AppRoutes() {
  const { activeAlert, snooze } = useAlarms()
  return (
    <>
      <AlarmAlert alarm={activeAlert} onSnooze={snooze} />
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/venues" element={<LiveVenues />} />
        <Route path="/venues/:id" element={<VenueDetail />} />
        <Route path="/search" element={<Search />} />
        <Route path="/alarms" element={<MyAlarms />} />
        <Route path="/login" element={<Login />} />
        <Route path="/staff/book" element={<CreateBooking />} />
        <Route path="/staff/bookings" element={<MyBookings />} />
        <Route path="/venues/:id/layout" element={<VenueLayout />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/forecast" element={<Forecast />} />
        <Route path="/admin/bookings" element={<ManageBookings />} />
        <Route path="/admin/venues" element={<ManageVenues />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AlarmProvider>
          <AppRoutes />
        </AlarmProvider>
      </BrowserRouter>
    </AuthProvider>
  )
}
