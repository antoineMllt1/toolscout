import { startTransition, useEffect, useState } from 'react'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ApplicationProvider } from './context/ApplicationContext'
import { FavoritesProvider } from './context/FavoritesContext'
import { SearchProvider, useSearch } from './context/SearchContext'
import SearchPage from './pages/SearchPage'
import DashboardPage from './pages/DashboardPage'
import AuthPage from './pages/AuthPage'
import CvStudioPage from './pages/CvStudioPage'
import FavoritesPage from './pages/FavoritesPage'
import HistoryPage from './pages/HistoryPage'
import InterviewLabPage from './pages/InterviewLabPage'
import CareerOpsPage from './pages/CareerOpsPage'
import HomePage from './pages/HomePage'
import ProfilePage from './pages/ProfilePage'
import Navbar from './components/Navbar'
import AppTopbar from './components/AppTopbar'
import './index.css'

const PAGE_STORAGE_KEY = 'sh_active_page_v1'

function AppInner() {
  const { loading, user } = useAuth()
  const { openSearch } = useSearch()
  const [page, setPage] = useState(() => localStorage.getItem(PAGE_STORAGE_KEY) || 'search')
  const [pendingJob, setPendingJob] = useState(null)

  useEffect(() => {
    localStorage.setItem(PAGE_STORAGE_KEY, page)
  }, [page])

  useEffect(() => {
    const stored = localStorage.getItem(PAGE_STORAGE_KEY)
    if (!stored) {
      setPage(user ? 'home' : 'search')
    }
  }, [user])

  const navigate = (nextPage) => {
    startTransition(() => {
      setPage(nextPage)
    })
  }

  const restoreSearchFromHistory = (searchId) => {
    openSearch(searchId)
    startTransition(() => {
      setPage('search')
    })
  }

  // Navigate to CV Studio with a pre-selected job
  const generateCvForJob = (job) => {
    setPendingJob(job)
    startTransition(() => {
      setPage('cv')
    })
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
    return <AuthPage onSuccess={() => navigate('home')} />
  }

  return (
    <div className="app-layout">
      <Navbar page={page} onNavigate={navigate} />
      <div className="app-content">
        {page !== 'auth' && <AppTopbar page={page} onNavigate={navigate} />}
        {page === 'home' && <HomePage onNavigate={navigate} />}
        {page === 'search' && (
          <SearchPage onNavigate={navigate} onGenerateCv={generateCvForJob} />
        )}
        {page === 'favorites' && (
          <FavoritesPage onNavigate={navigate} onGenerateCv={generateCvForJob} />
        )}
        {page === 'dashboard' && <DashboardPage onNavigate={navigate} />}
        {page === 'history' && <HistoryPage onOpen={restoreSearchFromHistory} />}
        {page === 'cv' && (
          <CvStudioPage onNavigate={navigate} pendingJob={pendingJob} onClearPendingJob={() => setPendingJob(null)} />
        )}
        {page === 'interview' && <InterviewLabPage onNavigate={navigate} />}
        {page === 'ops' && <CareerOpsPage onNavigate={navigate} />}
        {page === 'profile' && <ProfilePage onNavigate={navigate} />}
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
