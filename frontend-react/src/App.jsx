import { startTransition, useState } from 'react'
import { AuthProvider, useAuth } from './context/AuthContext'
import { SearchProvider } from './context/SearchContext'
import { FavoritesProvider } from './context/FavoritesContext'
import { ApplicationProvider } from './context/ApplicationContext'
import Layout from './components/Layout'
import AuthPage from './pages/AuthPage'
import SearchPage from './pages/SearchPage'
import CvStudioPage from './pages/CvStudioPage'
import CandidaturesPage from './pages/CandidaturesPage'
import ProfilePage from './pages/ProfilePage'
import './index.css'

function AppInner() {
  const { user, loading } = useAuth()
  const [page, setPage] = useState(() => localStorage.getItem('sh_page') || 'search')
  const [pendingJob, setPendingJob] = useState(null)

  function navigate(nextPage) {
    startTransition(() => {
      setPage(nextPage)
      localStorage.setItem('sh_page', nextPage)
    })
  }

  function generateCvForJob(job) {
    setPendingJob(job)
    navigate('cv')
  }

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--bg)' }}>
      <div className="spinner spinner--lg" />
    </div>
  )

  if (!user) return <AuthPage />

  return (
    <Layout page={page} onNavigate={navigate}>
      {page === 'search' && <SearchPage onGenerateCv={generateCvForJob} />}
      {page === 'cv' && (
        <CvStudioPage
          pendingJob={pendingJob}
          onClearPendingJob={() => setPendingJob(null)}
        />
      )}
      {page === 'candidatures' && <CandidaturesPage />}
      {page === 'profile' && <ProfilePage />}
    </Layout>
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
