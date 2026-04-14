import { useAuth } from '../context/AuthContext'

const NAV = [
  {
    id: 'search',
    label: 'Discover',
    hint: 'Search jobs across all sources',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M10.5 10.5L13.5 13.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    id: 'cv',
    label: 'CV Studio',
    hint: 'Generate a tailored CV',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <rect x="2.5" y="1.5" width="11" height="13" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M5 5.5h6M5 8h6M5 10.5h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    id: 'candidatures',
    label: 'Applications',
    hint: 'Track and prep your candidatures',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M3 3h10v10H3z" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M6 6.5l1.5 1.5L10 5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M5.5 10h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    id: 'profile',
    label: 'Profile',
    hint: 'Build your candidate base profile',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="5.5" r="2.5" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M3 13c0-2.761 2.239-4 5-4s5 1.239 5 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
]

export default function Layout({ page, onNavigate, children }) {
  const { user, logout } = useAuth()

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar__brand">
          <div className="sidebar__mark">SH</div>
          <div>
            <div className="sidebar__name">StudentHub</div>
            <div className="sidebar__tagline">Recruiter Copilot</div>
          </div>
        </div>

        <nav className="sidebar__nav">
          {NAV.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`sidebar__link ${page === item.id ? 'is-active' : ''}`}
              onClick={() => onNavigate(item.id)}
              title={item.hint}
            >
              <span style={{ opacity: page === item.id ? 1 : 0.55, flexShrink: 0 }}>
                {item.icon}
              </span>
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar__user">
          <div className="sidebar__avatar">
            {(user?.name || user?.email || 'U')[0].toUpperCase()}
          </div>
          <div className="sidebar__user-info">
            <div className="sidebar__user-name">{user?.name || 'Student'}</div>
            <div className="sidebar__user-email">{user?.email}</div>
          </div>
          <button type="button" className="sidebar__signout" onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="main">
        {children}
      </main>
    </div>
  )
}
