import { useState } from 'react'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ApplicationProvider } from './context/ApplicationContext'
import SearchPage from './pages/SearchPage'
import HistoryPage from './pages/HistoryPage'
import DashboardPage from './pages/DashboardPage'
import AuthPage from './pages/AuthPage'
import Navbar from './components/Navbar'
import './index.css'

function AppInner() {
  const { loading } = useAuth()
  const [page, setPage] = useState('search')
  const [historySearch, setHistorySearch] = useState(null)

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#EEF2F7' }}>
        <div className="w-10 h-10 rounded-2xl animate-pulse" style={{ background: 'linear-gradient(135deg, #6B9BC8, #7BBFAA)' }} />
      </div>
    )
  }

  if (page === 'auth') {
    return <AuthPage onSuccess={() => setPage('search')} />
  }

  function goToSearch(searchId) {
    setHistorySearch(searchId)
    setPage('search')
  }

  return (
    <div className="min-h-screen" style={{ background: '#EEF2F7' }}>
      <Navbar page={page} setPage={setPage} />
      {page === 'search' && (
        <SearchPage initialSearchId={historySearch} onClearInitial={() => setHistorySearch(null)} />
      )}
      {page === 'history' && <HistoryPage onOpen={goToSearch} />}
      {page === 'dashboard' && <DashboardPage />}
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <ApplicationProvider>
        <AppInner />
      </ApplicationProvider>
    </AuthProvider>
  )
}
