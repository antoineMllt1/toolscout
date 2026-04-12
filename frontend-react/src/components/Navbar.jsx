import { useAuth } from '../context/AuthContext'
import { useApplications } from '../context/ApplicationContext'
import { useSearch } from '../context/SearchContext'

const IconSearch = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="8.5" cy="8.5" r="5.5" />
    <path d="M17 17l-3.5-3.5" />
  </svg>
)

const IconHeart = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 16.5S2.5 12 2.5 6.5a4 4 0 0 1 7.5-2 4 4 0 0 1 7.5 2C17.5 12 10 16.5 10 16.5z" />
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
    <path d="M3 10L10 3l7 7" />
    <path d="M5 8.5V17h4v-4h2v4h4V8.5" />
  </svg>
)

const IconHome = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 8.5L10 3l7 5.5V17H3z" />
    <path d="M8 17v-5h4v5" />
  </svg>
)

const IconHistory = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3.5 10a6.5 6.5 0 1 0 2-4.67" />
    <path d="M3 4v4h4" />
    <path d="M10 6.5v4l2.5 1.5" />
  </svg>
)

const IconSpark = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 2.5l1.85 5.65L17.5 10l-5.65 1.85L10 17.5l-1.85-5.65L2.5 10l5.65-1.85L10 2.5z" />
  </svg>
)

const IconOrbit = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="10" cy="10" r="2" />
    <path d="M10 2.5c3.7 0 6.7 3.36 6.7 7.5S13.7 17.5 10 17.5 3.3 14.14 3.3 10 6.3 2.5 10 2.5z" />
    <path d="M4.2 6.1c3.2-1.86 7.63-1.24 9.9 1.55 2.27 2.78 1.58 7.23-1.55 9.93" />
  </svg>
)

const IconUser = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="10" cy="6.5" r="3" />
    <path d="M4 17a6 6 0 0 1 12 0" />
  </svg>
)

const IconLogout = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M7 3H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h3" />
    <path d="M13 14l3-4-3-4" />
    <path d="M7 10h9" />
  </svg>
)

export default function Navbar({ page, onNavigate }) {
  const { user, logout } = useAuth()
  const { applications } = useApplications()
  const { hasActiveSearch, isRunning, total, tool } = useSearch()

  const navSections = [
    {
      label: 'StudentHub',
      items: [
        ...(user ? [{ id: 'home', label: 'Accueil', icon: <IconHome /> }] : []),
        ...(user ? [{ id: 'profile', label: 'Profil', icon: <IconUser /> }] : []),
        { id: 'search', label: 'Recherche', icon: <IconSearch /> },
        ...(user ? [{ id: 'favorites', label: 'Favoris', icon: <IconHeart /> }] : []),
        ...(user ? [{ id: 'cv', label: 'CV Studio', icon: <IconCV /> }] : []),
        ...(user ? [{ id: 'dashboard', label: 'Candidatures', icon: <IconDashboard /> }] : []),
        ...(user ? [{ id: 'interview', label: 'Entretien', icon: <IconSpark /> }] : []),
        ...(user ? [{ id: 'history', label: 'Historique', icon: <IconHistory /> }] : []),
      ],
    },
  ]

  return (
    <aside className="sidebar">
      <button className="sidebar-logo" onClick={() => onNavigate(user ? 'home' : 'search')}>
        <div className="sidebar-logo-mark">
          <svg viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 2L3 7v11h5v-5h4v5h5V7L10 2z" />
          </svg>
        </div>
        <div className="sidebar-logo-text">
          <strong>StudentHub</strong>
          <small>career platform</small>
        </div>
      </button>

      <nav className="sidebar-nav">
        {navSections.map((section) =>
          section.items.length ? (
            <div key={section.label} className="sidebar-nav-group">
              <span className="sidebar-section-label">{section.label}</span>
              {section.items.map((item) => (
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
            </div>
          ) : null,
        )}
      </nav>

      {hasActiveSearch && (
        <div className={`sidebar-status-pill ${isRunning ? 'is-running' : ''}`}>
          <span className="status-dot" />
          <span>
            {isRunning
              ? `Scraping ${tool || ''}...`
              : `${total} offre${total !== 1 ? 's' : ''} - ${tool || ''}`}
          </span>
        </div>
      )}

      {user && (
        <div className="sidebar-insight-card">
          <p className="eyebrow is-light">Espace perso</p>
          <strong>{tool ? `Focus ${tool}` : 'Mon avancement'}</strong>
          <p>
            {hasActiveSearch
              ? `Dernier run: ${total} carte${total !== 1 ? 's' : ''} a traiter.`
              : 'Profil, favoris, CV et candidatures restent relies dans le meme espace.'}
          </p>
        </div>
      )}

      <div className="sidebar-footer">
        {user ? (
          <div className="sidebar-user">
            <div className="sidebar-user-avatar">
              {(user.name || user.email).slice(0, 2).toUpperCase()}
            </div>
            <div className="sidebar-user-info">
              <strong>{user.name || 'Mon compte'}</strong>
              <small>{applications.length} candidature{applications.length !== 1 ? 's' : ''}</small>
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
