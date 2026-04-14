import { useState } from 'react'
import { useAuth } from '../context/AuthContext'

const FEATURES = [
  'Search across WTTJ, Indeed, LinkedIn, and JobTeaser at once',
  'AI selects your best experiences for each role and rewrites them',
  'Interview prep dossier: questions, STAR stories, portfolio ideas',
]

export default function AuthPage() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'login') await login(email, password)
      else await register(email, password, name)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function switchMode() {
    setMode(mode === 'login' ? 'register' : 'login')
    setError('')
  }

  return (
    <div className="auth-shell">
      <div className="auth-left">
        <div className="auth-left__logo">StudentHub</div>

        <h1 className="auth-left__headline">
          Find the role. Build the case. Walk in prepared.
        </h1>
        <p className="auth-left__sub">
          One focused tool for students who want a targeted CV and real interview prep — not a generic application.
        </p>

        <div className="auth-left__features">
          {FEATURES.map((text) => (
            <div key={text} className="auth-feature">
              <div className="auth-feature__dot" />
              <div className="auth-feature__text">{text}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="auth-right">
        <div className="auth-form">
          <h2 className="auth-form__title">
            {mode === 'login' ? 'Welcome back' : 'Create your account'}
          </h2>
          <p className="auth-form__sub">
            {mode === 'login'
              ? 'Sign in to continue where you left off.'
              : 'Free to use. No credit card required.'}
          </p>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
            {mode === 'register' && (
              <div className="field-stack">
                <div className="field-label">Full name</div>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  placeholder="Marie Dupont"
                  autoComplete="name"
                />
              </div>
            )}

            <div className="field-stack">
              <div className="field-label">Email address</div>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="marie@example.com"
                autoComplete="email"
              />
            </div>

            <div className="field-stack">
              <div className="field-label">Password</div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              />
            </div>

            {error && (
              <div className="callout callout--error">{error}</div>
            )}

            <button
              type="submit"
              className="btn"
              disabled={loading}
              style={{ marginTop: 'var(--s2)', width: '100%' }}
            >
              {loading
                ? 'One moment...'
                : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <p style={{ textAlign: 'center', marginTop: 'var(--s5)', fontSize: '0.875rem', color: 'var(--ink-3)' }}>
            {mode === 'login' ? "No account yet? " : "Already have an account? "}
            <button
              type="button"
              onClick={switchMode}
              style={{
                color: 'var(--brand-ink)', fontWeight: 600,
                background: 'none', border: 'none', cursor: 'pointer',
                padding: 0, fontSize: 'inherit',
              }}
            >
              {mode === 'login' ? 'Sign up' : 'Sign in'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
