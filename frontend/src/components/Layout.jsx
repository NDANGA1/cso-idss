// Layout.jsx — wraps page content with navbar and padding

import Navbar from './Navbar.jsx'

export default function Layout({ children }) {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6">
        {children}
      </main>
      <footer className="text-center text-xs text-gray-400 py-4 border-t border-gray-100">
        CSO-IDSS · Institute of Finance Management · Real-Time Campus Space System
      </footer>
    </div>
  )
}
