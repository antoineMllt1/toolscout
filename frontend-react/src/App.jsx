import { startTransition, useEffect, useState } from 'react'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ApplicationProvider } from './context/ApplicationContext'
import { FavoritesProvider } from './context/FavoritesContext'
import { SearchProvider, useSearch } from './context/SearchContext'
import SearchPage from './pages/SearchPage'
import HistoryPage from './pages/HistoryPage'
import DashboardPage from './pages/DashboardPage'
import AuthPage from './pages/AuthPage'
import CvStudioPage from './pages/CvStudioPage'
import InterviewLabPage from './pages/InterviewLabPage'
import CareerOpsPage from './pages/CareerOpsPage'
import Navbar from './components/Navbar'
import './index.css'

const PAGE_STORAGE_KEY = 'ts_active_page_v2'

function AppInner() {
  const { loading } = useAuth()
  const { openSearch } = useSearch()
  const [page, setPage] = useState(() => localStorage.getItem(PAGE_STORAGE_KEY) || 'search')

  useEffect(() => {
    localStorage.setItem(PAGE_STORAGE_KEY, page)
  }, [page])

  const navigate = (nextPage) => {
    startTransition(() => {
      setPage(nextPage)
    })
  }

  const openHistorySearch = (searchId) => {
    openSearch(searchId)
    navigate('search')
  }

  if (loading) {
    return (
      <div className="app-loading-shell">
        <div className="app-loading-mark" />
        <p style={{ color: 'var(--muted)', fontSize: '13px' }}>Chargement…</p>
      </div>
    )
  }

  if (page === 'auth') {
    return <AuthPage onSuccess={() => navigate('search')} />
  }

  return (
    <div className="app-layout">
      <Navbar page={page} onNavigate={navigate} />
      <div className="app-content">
        {page === 'search' && <SearchPage onNavigate={navigate} />}
        {page === 'history' && <HistoryPage onOpen={openHistorySearch} />}
        {page === 'dashboard' && <DashboardPage onNavigate={navigate} />}
        {page === 'cv' && <CvStudioPage onNavigate={navigate} />}
        {page === 'interview' && <InterviewLabPage onNavigate={navigate} />}
        {page === 'ops' && <CareerOpsPage onNavigate={navigate} />}
      </div>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <FavoritesProvider>
        <ApplicationProvider>
          <SearchProvider>
            <AppInner />
          </SearchProvider>
        </ApplicationProvider>
      </FavoritesProvider>
    </AuthProvider>
  )
}
