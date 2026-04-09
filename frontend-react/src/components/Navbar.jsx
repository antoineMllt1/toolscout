import { useMemo, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { useApplications } from '../context/ApplicationContext'
import { useSearch } from '../context/SearchContext'

export default function Navbar({ page, onNavigate }) {
  const { user, logout } = useAuth()
  const { applications } = useApplications()
  const { hasActiveSearch, isRunning, total, tool } = useSearch()
  const [menuOpen, setMenuOpen] = useState(false)

  const navItems = useMemo(() => ([
    { id: 'search', label: 'Recherche' },
    { id: 'history', label: 'Runs' },
    ...(user ? [{ id: 'cv', label: 'CV Studio' }] : []),
    ...(user ? [{ id: 'dashboard', label: 'Cockpit' }] : []),
  ]), [user])

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <button className="brand" onClick={() => onNavigate('search')}>
          <span className="brand-mark">TS</span>
          <span>
            <strong>ToolScout</strong>
            <small>Student search cockpit</small>
          </span>
        </button>

        <nav className="topbar-nav" aria-label="Primary">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`topbar-link ${page === item.id ? 'is-active' : ''}`}
              onClick={() => onNavigate(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="topbar-meta">
          {hasActiveSearch && (
            <div className={`topbar-status ${isRunning ? 'is-running' : ''}`}>
              <span className="status-dot" />
              <span>{isRunning ? `Recherche en cours - ${tool}` : `${total} annonces - ${tool}`}</span>
            </div>
          )}

          {user ? (
            <div className="account-menu">
              <button className="account-trigger" onClick={() => setMenuOpen((open) => !open)}>
                <span className="account-avatar">{(user.name || user.email).slice(0, 2).toUpperCase()}</span>
                <span className="account-copy">
                  <strong>{user.name || 'Compte'}</strong>
                  <small>{applications.length} candidatures</small>
                </span>
              </button>

              {menuOpen && (
                <div className="account-popover">
                  <button
                    onClick={() => {
                      onNavigate('cv')
                      setMenuOpen(false)
                    }}
                  >
                    Ouvrir CV Studio
                  </button>
                  <button
                    onClick={() => {
                      onNavigate('dashboard')
                      setMenuOpen(false)
                    }}
                  >
                    Ouvrir le cockpit
                  </button>
                  <button
                    onClick={() => {
                      logout()
                      setMenuOpen(false)
                      onNavigate('search')
                    }}
                  >
                    Se deconnecter
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button className="topbar-ghost" onClick={() => onNavigate('auth')}>
              Connexion
            </button>
          )}
        </div>
      </div>
    </header>
  )
}
