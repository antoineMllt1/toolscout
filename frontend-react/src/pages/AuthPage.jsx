import { useState } from 'react'
import { useAuth } from '../context/AuthContext'

export default function AuthPage({ onSuccess }) {
  const { login, register } = useAuth()
  const [mode, setMode] = useState('login')   // login | register
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
      if (mode === 'login') {
        await login(email, password)
      } else {
        await register(email, password, name)
      }
      onSuccess?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: '#EEF2F7' }}>
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div
            className="w-12 h-12 rounded-2xl flex items-center justify-center text-white text-xl font-bold mx-auto mb-3"
            style={{ background: 'linear-gradient(135deg, #6B9BC8, #7BBFAA)' }}
          >
            T
          </div>
          <h1 className="text-2xl font-bold" style={{ color: '#2C3E50' }}>ToolScout</h1>
          <p className="text-sm mt-1" style={{ color: '#7A90A4' }}>
            {mode === 'login' ? 'Connectez-vous à votre compte' : 'Créez votre compte'}
          </p>
        </div>

        <div
          className="rounded-2xl border p-8"
          style={{ background: '#fff', borderColor: '#D6DFF0' }}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="block text-sm font-medium mb-1.5" style={{ color: '#5A6B7B' }}>
                  Prénom / Nom
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="Jean Dupont"
                  className="w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:ring-2 transition-shadow"
                  style={{ borderColor: '#D6DFF0', color: '#2C3E50' }}
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium mb-1.5" style={{ color: '#5A6B7B' }}>
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="vous@exemple.com"
                required
                className="w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:ring-2 transition-shadow"
                style={{ borderColor: '#D6DFF0', color: '#2C3E50' }}
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1.5" style={{ color: '#5A6B7B' }}>
                Mot de passe
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder={mode === 'register' ? 'Minimum 6 caractères' : '••••••••'}
                required
                className="w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:ring-2 transition-shadow"
                style={{ borderColor: '#D6DFF0', color: '#2C3E50' }}
              />
            </div>

            {error && (
              <div
                className="rounded-xl border px-4 py-2.5 text-sm"
                style={{ background: '#FEF0E8', borderColor: '#F5C6A8', color: '#B05A2A' }}
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-xl text-white text-sm font-semibold transition-opacity disabled:opacity-60"
              style={{ background: 'linear-gradient(135deg, #6B9BC8, #7BBFAA)' }}
            >
              {loading ? 'Chargement…' : mode === 'login' ? 'Se connecter' : 'Créer le compte'}
            </button>
          </form>

          <div className="mt-5 text-center">
            <button
              onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}
              className="text-sm underline"
              style={{ color: '#9AABB8' }}
            >
              {mode === 'login'
                ? "Pas encore de compte ? S'inscrire"
                : 'Déjà un compte ? Se connecter'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
