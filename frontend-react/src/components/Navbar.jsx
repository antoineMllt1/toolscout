import { useAuth } from '../context/AuthContext'
import { useApplications } from '../context/ApplicationContext'
import { useSearch } from '../context/SearchContext'

const IconSearch = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="8.5" cy="8.5" r="5.5" />
    <path d="M17 17l-3.5-3.5" />
  </svg>
)

const IconHistory = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 4v6l3.5 2" />
    <path d="M3.34 7a7.5 7.5 0 1 0 .7-2.08M3 3v4h4" />
  </svg>
)

const IconCV = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <rect x="4" y="2" width="12" height="16" rx="2" />
    <path d="M8 7h4M7 10.5h6M7 13.5h4" />
  </svg>
)

const IconDashboard = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="2" width="7" height="7" rx="1.5" />
    <rect x="11" y="2" width="7" height="7" rx="1.5" />
    <rect x="2" y="11" width="7" height="7" rx="1.5" />
    <rect x="11" y="11" width="7" height="7" rx="1.5" />
  </svg>
)

const IconInterview = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h7A2.5 2.5 0 0 1 16 5.5v5A2.5 2.5 0 0 1 13.5 13H10l-3.5 3v-3h0A2.5 2.5 0 0 1 4 10.5z" />
    <path d="M8 7.5h4M8 10h2.5" />
  </svg>
)

const IconOps = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 10h4M12 10h4M10 4v4M10 12v4" />
    <circle cx="10" cy="10" r="7" />
  </svg>
)

const IconLogout = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M7 3H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h3" />
    <path d="M13 14l3-4-3-4" />
    <path d="M7 10h9" />
  </svg>
)

const IconBrand = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 10 L10 5 L15 10 L10 15 Z" fill="currentColor" stroke="none" />
    <circle cx="10" cy="10" r="2.5" fill="white" stroke="none" />
  </svg>
)

export default function Navbar({ page, onNavigate }) {
  const { user, logout } = useAuth()
  const { applications } = useApplications()
  const { hasActiveSearch, isRunning, total, tool } = useSearch()

  const navItems = [
    { id: 'search', label: 'Recherche', icon: <IconSearch /> },
    { id: 'history', label: 'Historique', icon: <IconHistory /> },
    ...(user ? [{ id: 'cv', label: 'Profil', icon: <IconCV /> }] : []),
    ...(user ? [{ id: 'interview', label: 'Interview', icon: <IconInterview /> }] : []),
    ...(user ? [{ id: 'ops', label: 'Career Ops', icon: <IconOps /> }] : []),
    ...(user ? [{ id: 'dashboard', label: 'Cockpit', icon: <IconDashboard /> }] : []),
  ]

  return (
    <aside className="sidebar">
      <button className="sidebar-logo" onClick={() => onNavigate('search')}>
        <div className="sidebar-logo-mark">
          <IconBrand />
        </div>
        <div className="sidebar-logo-text">
          <strong>StageAI</strong>
          <small>student ops</small>
        </div>
      </button>

      <nav className="sidebar-nav">
        <span className="sidebar-section-label">Menu</span>
        {navItems.map((item) => (
          <button
            key={item.id}
            className={`sidebar-link ${page === item.id ? 'is-active' : ''}`}
            onClick={() => onNavigate(item.id)}
          >
            <span className="sidebar-link-icon">{item.icon}</span>
            <span className="sidebar-link-label">{item.label}</span>
            {item.id === 'dashboard' && applications.length > 0 && (
              <span className="sidebar-link-badge">{applications.length}</span>
            )}
          </button>
        ))}
      </nav>

      {hasActiveSearch && (
        <div className={`sidebar-status-pill ${isRunning ? 'is-running' : ''}`}>
          <span className="status-dot" />
          <span>{isRunning ? `Scraping ${tool || ''}...` : `${total} annonce${total !== 1 ? 's' : ''} - ${tool || ''}`}</span>
        </div>
      )}

      <div className="sidebar-footer">
        {user ? (
          <div className="sidebar-user">
            <div className="sidebar-user-avatar">
              {(user.name || user.email).slice(0, 2).toUpperCase()}
            </div>
            <div className="sidebar-user-info">
              <strong>{user.name || 'Compte'}</strong>
              <small>{applications.length} candidatures</small>
            </div>
            <button
              className="sidebar-logout"
              onClick={() => {
                logout()
                onNavigate('search')
              }}
              title="Se deconnecter"
            >
              <IconLogout />
            </button>
          </div>
        ) : (
          <button className="sidebar-cta" onClick={() => onNavigate('auth')}>
            Connexion / Inscription
          </button>
        )}
      </div>
    </aside>
  )
}
