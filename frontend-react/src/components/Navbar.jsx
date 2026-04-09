import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { useApplications } from '../context/ApplicationContext'

export default function Navbar({ page, setPage }) {
  const { user, logout } = useAuth()
  const { applications } = useApplications()
  const [menuOpen, setMenuOpen] = useState(false)

  const savedCount = applications.length

  const navLinks = [
    { id: 'search',    label: 'Recherche' },
    { id: 'history',   label: 'Historique' },
    ...(user ? [{ id: 'dashboard', label: `Mes candidatures${savedCount > 0 ? ` (${savedCount})` : ''}` }] : []),
  ]

  return (
    <nav
      className="sticky top-0 z-50 border-b"
      style={{ background: 'rgba(238,242,247,0.92)', backdropFilter: 'blur(12px)', borderColor: '#D6DFF0' }}
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6 flex items-center justify-between h-14">
        {/* Logo */}
        <button
          onClick={() => setPage('search')}
          className="flex items-center gap-2 font-bold text-lg tracking-tight"
          style={{ color: '#4A7DB5' }}
        >
          <span
            className="w-7 h-7 rounded-lg flex items-center justify-center text-white text-sm font-bold"
            style={{ background: 'linear-gradient(135deg, #6B9BC8, #7BBFAA)' }}
          >
            T
          </span>
          ToolScout
        </button>

        {/* Nav links */}
        <div className="flex items-center gap-1">
          {navLinks.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setPage(id)}
              className="px-4 py-1.5 rounded-full text-sm font-medium transition-all"
              style={
                page === id
                  ? { background: '#6B9BC8', color: '#fff' }
                  : { color: '#6B7B90' }
              }
            >
              {label}
            </button>
          ))}
        </div>

        {/* Auth section */}
        <div className="relative">
          {user ? (
            <div>
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm font-medium transition-all hover:shadow-sm"
                style={{ background: '#fff', borderColor: '#D6DFF0', color: '#2C3E50' }}
              >
                <span
                  className="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0"
                  style={{ background: 'linear-gradient(135deg, #6B9BC8, #7BBFAA)' }}
                >
                  {(user.name || user.email)[0].toUpperCase()}
                </span>
                <span className="hidden sm:block max-w-[120px] truncate">
                  {user.name || user.email}
                </span>
                <svg className="w-3 h-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {menuOpen && (
                <div
                  className="absolute right-0 mt-2 w-48 rounded-2xl border shadow-lg overflow-hidden z-50"
                  style={{ background: '#fff', borderColor: '#D6DFF0' }}
                >
                  <div className="px-4 py-3 border-b" style={{ borderColor: '#EEF2F7' }}>
                    <p className="text-xs font-semibold" style={{ color: '#2C3E50' }}>{user.name || 'Mon compte'}</p>
                    <p className="text-xs truncate" style={{ color: '#9AABB8' }}>{user.email}</p>
                  </div>
                  <button
                    onClick={() => { setPage('dashboard'); setMenuOpen(false) }}
                    className="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 transition-colors"
                    style={{ color: '#2C3E50' }}
                  >
                    📋 Mes candidatures
                  </button>
                  <button
                    onClick={() => { logout(); setMenuOpen(false); setPage('search') }}
                    className="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 transition-colors border-t"
                    style={{ color: '#9B2E2E', borderColor: '#EEF2F7' }}
                  >
                    Se déconnecter
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button
              onClick={() => setPage('auth')}
              className="px-4 py-1.5 rounded-full text-sm font-medium border transition-all hover:shadow-sm"
              style={{ background: '#fff', borderColor: '#D6DFF0', color: '#6B7B90' }}
            >
              Connexion
            </button>
          )}
        </div>
      </div>
    </nav>
  )
}
