import { useEffect, useMemo, useState } from 'react'
import AppPageHeader from '../components/AppPageHeader'
import ProfileAssistant from '../components/ProfileAssistant'
import TagInput from '../components/TagInput'
import { useAuth } from '../context/AuthContext'

const EMPTY_PROFILE = {
  full_name: '',
  headline: '',
  email: '',
  phone: '',
  location: '',
  website: '',
  linkedin: '',
  github: '',
  portfolio_url: '',
  summary: '',
  target_roles: [],
  skills: [],
  languages: [],
  certifications: [],
  experience: [],
  projects: [],
  education: [],
}

export default function ProfilePage({ onNavigate }) {
  const { user, authFetch } = useAuth()
  const [profile, setProfile] = useState(EMPTY_PROFILE)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [importing, setImporting] = useState(false)
  const [feedback, setFeedback] = useState('')

  useEffect(() => {
    if (!user) return
    void loadProfile()
  }, [user])

  async function loadProfile() {
    const response = await authFetch('/api/cv/profile')
    if (!response.ok) return
    setProfile({ ...EMPTY_PROFILE, ...(await response.json()) })
  }

  async function saveProfile() {
    setSaving(true)
    setFeedback('')
    try {
      const response = await authFetch('/api/cv/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      })
      if (!response.ok) throw new Error('Impossible de sauvegarder le profil')
      setProfile({ ...EMPTY_PROFILE, ...(await response.json()) })
      setFeedback('Profil sauvegarde.')
    } catch (error) {
      setFeedback(error.message)
    } finally {
      setSaving(false)
    }
  }

  async function uploadCvFile(event) {
    const file = event.target.files?.[0]
    if (!file) return
    setUploading(true)
    setFeedback('')
    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await authFetch('/api/cv/upload', { method: 'POST', body: formData })
      if (!response.ok) throw new Error('Import CV impossible')
      const data = await response.json()
      setProfile({ ...EMPTY_PROFILE, ...(data.profile || {}) })
      setFeedback('CV importe et profil enrichi.')
    } catch (error) {
      setFeedback(error.message)
    } finally {
      setUploading(false)
      event.target.value = ''
    }
  }

  async function importPortfolio() {
    if (!profile.portfolio_url?.trim()) {
      setFeedback('Ajoute une URL de portfolio avant de lancer la synchronisation.')
      return
    }
    setImporting(true)
    setFeedback('')
    try {
      const response = await authFetch('/api/cv/portfolio/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ portfolio_url: profile.portfolio_url }),
      })
      if (!response.ok) throw new Error('Synchronisation portfolio impossible')
      const data = await response.json()
      setProfile({ ...EMPTY_PROFILE, ...(data.profile || {}) })
      setFeedback('Portfolio synchronise.')
    } catch (error) {
      setFeedback(error.message)
    } finally {
      setImporting(false)
    }
  }

  const profileCompletion = useMemo(() => {
    const score = [
      Boolean(profile.full_name),
      Boolean(profile.headline),
      Boolean(profile.summary),
      (profile.target_roles || []).length > 0,
      (profile.skills || []).length > 0,
      (profile.experience || []).length > 0,
      (profile.projects || []).length > 0,
      Boolean(profile.portfolio_url),
    ].filter(Boolean).length
    return Math.round((score / 8) * 100)
  }, [profile])

  if (!user) {
    return (
      <main className="dashboard-page">
        <section className="empty-panel">
          <p className="eyebrow">Compte requis</p>
          <h3>Connecte-toi pour construire ton profil personnel.</h3>
          <button className="primary-button" onClick={() => onNavigate('auth')}>
            Ouvrir la connexion
          </button>
        </section>
      </main>
    )
  }

  return (
    <main className="dashboard-page">
      <AppPageHeader
        eyebrow="Profil"
        title="Base candidat"
        description="Ton profil central StudentHub: ce que tu vises, ce que tu sais faire et ce que le produit peut reutiliser dans les CV et entretiens."
        actions={
          <>
            <button className="primary-button" onClick={saveProfile} disabled={saving}>
              {saving ? 'Sauvegarde...' : 'Sauvegarder'}
            </button>
            <button className="secondary-button" onClick={() => onNavigate('cv')}>
              Ouvrir CV Studio
            </button>
          </>
        }
        stats={[
          { label: 'Completion', value: `${profileCompletion}%`, tone: 'tone-blue' },
          { label: 'Experiences', value: profile.experience.length, tone: 'tone-green' },
          { label: 'Projets', value: profile.projects.length, tone: 'tone-yellow' },
          { label: 'Roles cibles', value: profile.target_roles.length },
        ]}
      />

      {feedback ? <div className="feedback-box info">{feedback}</div> : null}

      <section className="profile-shell-grid">
        <div className="dashboard-main-column">
          <section className="home-highlight-grid">
            <article className="home-highlight-card">
              <p className="eyebrow">Cap</p>
              <h3>{(profile.target_roles || []).slice(0, 2).join(', ') || 'A definir'}</h3>
              <p>Le type de role que tu veux viser doit etre clair avant de generer des CV cibles.</p>
            </article>
            <article className="home-highlight-card">
              <p className="eyebrow">Preuves</p>
              <h3>{profile.experience.length + profile.projects.length} signal{profile.experience.length + profile.projects.length > 1 ? 's' : ''} forts</h3>
              <p>Experiences et projets sont la vraie matiere premiere des candidatures reussies.</p>
            </article>
            <article className="home-highlight-card">
              <p className="eyebrow">Sources</p>
              <h3>{profile.portfolio_url ? 'Portfolio relie' : 'Portfolio manquant'}</h3>
              <p>Le portfolio et les imports servent a enrichir ton profil sans te faire tout retaper a la main.</p>
            </article>
          </section>

          <ProfileAssistant profile={profile} setProfile={setProfile} onSave={saveProfile} saving={saving} />

          <section className="panel-shell">
            <div className="panel-head">
              <div>
                <p className="eyebrow">Infos de base</p>
                <h2>Identite et cible</h2>
              </div>
            </div>
            <div className="cv-basics-grid">
              <label className="field-stack"><span>Nom complet</span><input value={profile.full_name} onChange={(event) => setProfile((prev) => ({ ...prev, full_name: event.target.value }))} /></label>
              <label className="field-stack"><span>Headline</span><input value={profile.headline} onChange={(event) => setProfile((prev) => ({ ...prev, headline: event.target.value }))} /></label>
              <label className="field-stack"><span>Email</span><input value={profile.email} onChange={(event) => setProfile((prev) => ({ ...prev, email: event.target.value }))} /></label>
              <label className="field-stack"><span>Telephone</span><input value={profile.phone} onChange={(event) => setProfile((prev) => ({ ...prev, phone: event.target.value }))} /></label>
              <label className="field-stack"><span>Localisation</span><input value={profile.location} onChange={(event) => setProfile((prev) => ({ ...prev, location: event.target.value }))} /></label>
              <label className="field-stack"><span>Portfolio URL</span><input value={profile.portfolio_url} onChange={(event) => setProfile((prev) => ({ ...prev, portfolio_url: event.target.value }))} placeholder="https://..." /></label>
            </div>

            <label className="field-stack" style={{ padding: '0 20px 16px' }}>
              <span>Resume</span>
              <textarea rows={4} value={profile.summary} onChange={(event) => setProfile((prev) => ({ ...prev, summary: event.target.value }))} />
            </label>

            <div className="cv-tag-grid">
              <TagInput label="Roles cibles" placeholder="Data analyst intern, Product ops intern" value={profile.target_roles} onChange={(target_roles) => setProfile((prev) => ({ ...prev, target_roles }))} />
              <TagInput label="Competences" placeholder="SQL, Power BI, Python" value={profile.skills} onChange={(skills) => setProfile((prev) => ({ ...prev, skills }))} />
              <TagInput label="Langues" placeholder="French C2, English C1" value={profile.languages} onChange={(languages) => setProfile((prev) => ({ ...prev, languages }))} />
              <TagInput label="Certifications" placeholder="PL-300, Google Analytics" value={profile.certifications} onChange={(certifications) => setProfile((prev) => ({ ...prev, certifications }))} />
            </div>
          </section>
        </div>

        <aside className="dashboard-side-column">
          <section className="panel-shell">
            <div className="panel-head">
              <div>
                <p className="eyebrow">Imports</p>
                <h2>Documents et portfolio</h2>
              </div>
            </div>
            <div className="profile-capture-shell">
              <label className="field-stack">
                <span>Importer un CV</span>
                <input
                  type="file"
                  accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
                  onChange={uploadCvFile}
                  disabled={uploading}
                />
              </label>
              <button className="secondary-button" type="button" onClick={importPortfolio} disabled={importing}>
                {importing ? 'Synchronisation...' : 'Synchroniser le portfolio'}
              </button>
              <div className="profile-capture-card">
                <p className="eyebrow">Etat rapide</p>
                <h3>{profile.portfolio_url ? 'Portfolio renseigne' : 'Portfolio manquant'}</h3>
                <p>{profile.experience.length} experiences, {profile.projects.length} projets, {profile.education.length} formations.</p>
              </div>
            </div>
          </section>

          <section className="profile-summary-card">
            <p className="eyebrow">Usage dans StudentHub</p>
            <h3>Ce profil alimente tout</h3>
            <p>Recherche qualifiee, generation de CV cibles, suivi de candidature et preparation entretien reutilisent cette base.</p>
          </section>
        </aside>
      </section>
    </main>
  )
}
