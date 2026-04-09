import { useState } from 'react'
import { useAuth } from '../context/AuthContext'

const AUTH_BENEFITS = [
  {
    title: 'Recherche persistante',
    text: 'Un scraping continue meme si tu changes de page, et le run reste restaurable ensuite.',
  },
  {
    title: 'CV cible par annonce',
    text: 'La base template est deja la pour brancher des variantes CV, lettre et score de match.',
  },
  {
    title: 'CRM de postulation',
    text: 'Tu gardes un pipeline clair entre cartes a relire, candidatures envoyees et entretiens.',
  },
]

export default function AuthPage({ onSuccess }) {
  const { login, register } = useAuth()
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'login') await login(email, password)
      else await register(email, password, name)
      onSuccess?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-layout">
        <article className="auth-showcase fade-stagger" style={{ '--index': 0 }}>
          <div className="auth-brand">
            <div className="brand-mark" style={{ width: 40, height: 40, borderRadius: 11, background: 'var(--brand-gradient)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15, fontWeight: 800, color: 'white', boxShadow: 'var(--shadow-brand)' }}>
              S
            </div>
            <div className="brand-logo-text">
              <strong>StageAI</strong>
              <small>Student workspace</small>
            </div>
          </div>

          <div className="hero-copy">
            <p className="eyebrow is-light">Premium workspace</p>
            <h1 className="auth-display">Trouve ton stage, prépare ton CV, pilote tes candidatures.</h1>
            <p className="lede is-light">
              Un seul espace pour chercher des offres, preparer un CV cible par poste et suivre chaque candidature
              jusqu'a la reponse finale.
            </p>
          </div>

          <ul className="auth-feature-list">
            {AUTH_BENEFITS.map((item) => (
              <li key={item.title}>
                <strong>{item.title}</strong>
                <span>{item.text}</span>
              </li>
            ))}
          </ul>
        </article>

        <section className="auth-panel auth-form-panel fade-stagger" style={{ '--index': 1 }}>
          <div className="auth-mode-switch" role="tablist" aria-label="Authentication mode">
            <button
              type="button"
              className={`auth-mode-chip ${mode === 'login' ? 'is-active' : ''}`}
              onClick={() => setMode('login')}
            >
              Connexion
            </button>
            <button
              type="button"
              className={`auth-mode-chip ${mode === 'register' ? 'is-active' : ''}`}
              onClick={() => setMode('register')}
            >
              Creation
            </button>
          </div>

          <div className="auth-copy">
            <p className="eyebrow">{mode === 'login' ? 'Connexion' : 'Creation de compte'}</p>
            <h2>{mode === 'login' ? 'Recupere tes runs et ton pipeline.' : 'Active ton cockpit candidat.'}</h2>
            <p className="panel-note">
              {mode === 'login'
                ? 'Reprends tes recherches, veilles et candidatures la ou tu les as laissees.'
                : 'Le compte sert a garder tes veilles, ton CRM et tes futures variantes CV dans la duree.'}
            </p>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            {mode === 'register' && (
              <label className="field-stack">
                <span>Nom affiche</span>
                <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Prenom Nom" />
              </label>
            )}

            <label className="field-stack">
              <span>Email</span>
              <input
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                type="email"
                placeholder="toi@exemple.com"
              />
            </label>

            <label className="field-stack">
              <span>Mot de passe</span>
              <input
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                type="password"
                placeholder="Minimum 6 caracteres"
              />
            </label>

            {error && <div className="feedback-box danger">{error}</div>}

            <button className="primary-button" type="submit" disabled={loading}>
              {loading ? 'Chargement...' : mode === 'login' ? 'Entrer dans le cockpit' : 'Creer le compte'}
            </button>
          </form>

          <p className="auth-footer">
            {mode === 'login'
              ? "Pas encore de compte ? Passe en creation pour sauvegarder tes futures veilles."
              : 'Tu as deja un compte ? Reviens en connexion pour reprendre ton espace.'}
          </p>
        </section>
      </section>
    </main>
  )
}
