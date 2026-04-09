import { startTransition, useEffect, useState } from 'react'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ApplicationProvider } from './context/ApplicationContext'
import { SearchProvider, useSearch } from './context/SearchContext'
import SearchPage from './pages/SearchPage'
import HistoryPage from './pages/HistoryPage'
import DashboardPage from './pages/DashboardPage'
import AuthPage from './pages/AuthPage'
import CvStudioPage from './pages/CvStudioPage'
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
        <p>Chargement de votre dashboard.</p>
      </div>
    )
  }

  if (page === 'auth') {
    return <AuthPage onSuccess={() => navigate('search')} />
  }

  return (
    <div className="app-shell">
      <Navbar page={page} onNavigate={navigate} />
      {page === 'search' && <SearchPage onNavigate={navigate} />}
      {page === 'history' && <HistoryPage onOpen={openHistorySearch} />}
      {page === 'dashboard' && <DashboardPage onNavigate={navigate} />}
      {page === 'cv' && <CvStudioPage onNavigate={navigate} />}
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <ApplicationProvider>
        <SearchProvider>
          <AppInner />
        </SearchProvider>
      </ApplicationProvider>
    </AuthProvider>
  )
}
