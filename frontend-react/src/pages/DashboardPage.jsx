import { useEffect, useMemo, useState } from 'react'
import TagInput from '../components/TagInput'
import AppPageHeader from '../components/AppPageHeader'
import { useApplications } from '../context/ApplicationContext'
import { useAuth } from '../context/AuthContext'
import { useFavorites } from '../context/FavoritesContext'

const KANBAN_COLUMNS = [
  {
    key: 'saved',
    label: 'A qualifier',
    note: 'Cartes a relire',
    matcher: (app) => app.status === 'saved',
  },
  {
    key: 'applied',
    label: 'Postule',
    note: 'Dossiers envoyes',
    matcher: (app) => app.status === 'applied',
  },
  {
    key: 'interview',
    label: 'Entretien',
    note: 'Suivi en cours',
    matcher: (app) => app.status === 'interview',
  },
  {
    key: 'closed',
    label: 'Clos',
    note: 'Offres ou refus',
    matcher: (app) => ['offer', 'rejected'].includes(app.status),
  },
]

const CADENCE_LABELS = {
  daily: 'Tous les jours',
  every_3_days: 'Tous les 3 jours',
  weekly: 'Chaque semaine',
}

const CV_TEMPLATE_STORAGE_KEY = 'sh_cv_preferred_template_v1'

function ApplicationMiniCard({ app, onAdvance, onDelete }) {
  const nextStatus = app.status === 'saved'
    ? 'applied'
    : app.status === 'applied'
      ? 'interview'
      : app.status === 'interview'
        ? 'offer'
        : null

  return (
    <article className="mini-app-card">
      <div>
        <p className="eyebrow">{app.source || 'Source'}</p>
        <h4>{app.job_title}</h4>
        <p>{app.company_name || 'Entreprise non precisee'}</p>
      </div>

      <div className="mini-app-meta">
        {app.location && <span className="inline-badge">{app.location}</span>}
        {app.contract_type && <span className="inline-badge">{app.contract_type}</span>}
      </div>

      <div className="mini-app-actions">
        <a className="text-action" href={app.job_url} target="_blank" rel="noreferrer">
          Ouvrir
        </a>
        {nextStatus && (
          <button className="text-action" onClick={() => onAdvance(app.id, nextStatus)}>
            Etape suivante
          </button>
        )}
        <button className="text-action danger" onClick={() => onDelete(app.id)}>
          Retirer
        </button>
      </div>
    </article>
  )
}

function formatLatestRun(watchlist) {
  if (!watchlist.latest_run) return 'Aucun run encore lance.'

  const matched = watchlist.latest_run.matched_results || 0
  const total = watchlist.latest_run.total_results || 0
  return `Dernier run: ${matched} match${matched > 1 ? 's' : ''} cibles sur ${total} annonce${total > 1 ? 's' : ''}.`
}

export default function DashboardPage({ onNavigate }) {
  const { user, authFetch } = useAuth()
  const { favorites } = useFavorites()
  const { applications, updateStatus, removeApplication } = useApplications()
  const [watchlists, setWatchlists] = useState([])
  const [companyPortals, setCompanyPortals] = useState([])
  const [templates, setTemplates] = useState([])
  const [profile, setProfile] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [watchForm, setWatchForm] = useState({
    name: '',
    tools: ['Power BI'],
    roles: ['Data Analyst'],
    cadence: 'daily',
    active: true,
  })

  useEffect(() => {
    if (!user) return
    void loadWatchlists()
    void loadCompanyPortals()
    void loadTemplates()
    void loadProfile()
  }, [user])

  async function loadWatchlists() {
    const response = await authFetch('/api/watchlists')
    if (!response.ok) return
    setWatchlists(await response.json())
  }

  async function loadTemplates() {
    const response = await fetch('/api/cv/templates')
    if (!response.ok) return
    setTemplates(await response.json())
  }

  async function loadCompanyPortals() {
    const response = await authFetch('/api/company-portals')
    if (!response.ok) return
    setCompanyPortals(await response.json())
  }

  async function loadProfile() {
    const response = await authFetch('/api/cv/profile')
    if (!response.ok) return
    setProfile(await response.json())
  }

  async function createWatchlist(event) {
    event.preventDefault()
    setSubmitting(true)
    try {
      const response = await authFetch('/api/watchlists', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(watchForm),
      })
      if (!response.ok) return
      setWatchForm({
        name: '',
        tools: [],
        roles: [],
        cadence: 'daily',
        active: true,
      })
      await loadWatchlists()
    } finally {
      setSubmitting(false)
    }
  }

  async function toggleWatchlist(watchlist) {
    await authFetch(`/api/watchlists/${watchlist.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active: !watchlist.active }),
    })
    await loadWatchlists()
  }

  async function runWatchlistNow(watchlistId) {
    await authFetch(`/api/watchlists/${watchlistId}/run`, { method: 'POST' })
    await loadWatchlists()
  }

  async function deleteWatchlist(watchlistId) {
    await authFetch(`/api/watchlists/${watchlistId}`, { method: 'DELETE' })
    await loadWatchlists()
  }

  const board = useMemo(
    () =>
      KANBAN_COLUMNS.map((column) => ({
        ...column,
        items: applications.filter(column.matcher),
      })),
    [applications],
  )

  const trackedCount = applications.length
  const activeWatchlists = watchlists.filter((watchlist) => watchlist.active).length
  const favoriteCompanies = companyPortals.filter((portal) => portal.favorite)
  const interviewCount = applications.filter((app) => app.status === 'interview').length
  const nextReviewCard = applications.find((app) => app.status === 'saved') || applications[0] || null

  function useTemplate(templateSlug) {
    try {
      localStorage.setItem(CV_TEMPLATE_STORAGE_KEY, templateSlug)
    } catch {
      // ignore storage failures
    }
    onNavigate('cv')
  }

  if (!user) {
    return (
      <main className="dashboard-page">
        <section className="empty-panel fade-stagger" style={{ '--index': 0 }}>
          <p className="eyebrow">Compte requis</p>
          <h3>Connecte-toi pour suivre tes candidatures, lancer des veilles et preparer des CV cibles.</h3>
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
        eyebrow="Student cockpit"
        title="Pipeline candidatures"
        description={
          nextReviewCard
            ? `Focus actuel: ${nextReviewCard.job_title} chez ${nextReviewCard.company_name || 'Entreprise'}.`
            : 'Recherche, suivi candidature, veille et base CV vivent dans le meme cockpit.'
        }
        actions={
          <>
            <button className="primary-button" onClick={() => onNavigate('search')}>
              Revenir aux annonces
            </button>
            <button className="secondary-button" onClick={() => onNavigate('history')}>
              Voir les runs
            </button>
          </>
        }
        stats={[
          { label: 'Candidatures suivies', value: trackedCount, tone: 'tone-blue' },
          { label: 'Veilles actives', value: activeWatchlists, tone: 'tone-green' },
          { label: 'Entretiens', value: interviewCount, tone: 'tone-yellow' },
          { label: 'Templates CV', value: templates.length },
          { label: 'Cartes a relire', value: board.find((column) => column.key === 'saved')?.items.length || 0 },
          { label: 'Favoris jobs', value: favorites.length },
        ]}
      />

      <section className="dashboard-grid">
        <div className="dashboard-main-column">
          <section className="panel-shell fade-stagger" style={{ '--index': 5 }}>
            <div className="panel-head">
              <div>
                <p className="eyebrow">Pipeline</p>
                <h2>CRM de candidature</h2>
              </div>
              <p className="panel-note">Chaque colonne reste legere pour pouvoir trier vite, puis approfondir au bon moment.</p>
            </div>

            <div className="kanban-grid">
              {board.map((column) => (
                <section key={column.key} className="kanban-column">
                  <header>
                    <div>
                      <h3>{column.label}</h3>
                      <small>{column.note}</small>
                    </div>
                    <small>{column.items.length}</small>
                  </header>

                  <div className="kanban-stack">
                    {column.items.length === 0 ? (
                      <div className="kanban-empty">Aucune carte</div>
                    ) : (
                      column.items.map((app) => (
                        <ApplicationMiniCard
                          key={app.id}
                          app={app}
                          onAdvance={updateStatus}
                          onDelete={removeApplication}
                        />
                      ))
                    )}
                  </div>
                </section>
              ))}
            </div>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 6 }}>
            <div className="panel-head">
              <div>
                <p className="eyebrow">Profil candidat</p>
                <h2>Base CV + portfolio</h2>
              </div>
              <p className="panel-note">Point de depart pour centraliser ton CV master, ton portfolio et tes versions ciblees.</p>
            </div>

            <div className="template-grid">
              {templates.map((template) => (
                <article key={template.slug} className="template-card">
                  <p className="eyebrow">{template.family}</p>
                  <h3>{template.name}</h3>
                  <p>{template.description}</p>
                  <div className="template-meta">
                    <span className="inline-badge">{template.style}</span>
                    <span className="inline-badge">{template.engine}</span>
                    <span className="inline-badge">Backend-ready</span>
                  </div>
                  <div className="template-actions">
                    <button className="text-action" onClick={() => useTemplate(template.slug)}>
                      Utiliser ce template
                    </button>
                    <button className="text-action" onClick={() => onNavigate('cv')}>
                      Ouvrir CV Studio
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </div>

        <div className="dashboard-side-column">
          <section className="panel-shell fade-stagger" style={{ '--index': 7 }}>
            <div className="panel-head">
              <div>
                <p className="eyebrow">Readiness</p>
                <h2>Etat du profil</h2>
              </div>
            </div>

            <div className="candidate-brief-card">
              <p className="eyebrow">Lecture rapide</p>
              <h3>{profile?.application_plan?.readiness_score ?? 0}% pret</h3>
              <p>{profile?.candidate_brief?.summary || 'Complete ton profil candidat pour faire remonter les bons signaux.'}</p>
              <div className="coach-chip-row">
                <span className="inline-badge">{profile?.target_roles?.length || 0} role(s)</span>
                <span className="inline-badge">{profile?.projects?.length || 0} projet(s)</span>
                <span className="inline-badge">{profile?.student_guidance?.story_starters?.length || 0} stories</span>
              </div>
              <button className="text-action" onClick={() => onNavigate('cv')}>
                Ouvrir le profil candidat
              </button>
              <button className="text-action" onClick={() => onNavigate('interview')}>
                Lancer l'interview lab
              </button>
              <button className="text-action" onClick={() => onNavigate('ops')}>
                Ouvrir career ops
              </button>
            </div>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 8 }}>
            <div className="panel-head">
              <div>
                <p className="eyebrow">Favoris</p>
                <h2>Priorites du moment</h2>
              </div>
            </div>

            <div className="watchlist-stack">
              <article className="watchlist-card">
                <div className="watchlist-head">
                  <div>
                    <h3>Jobs favoris</h3>
                    <p>{favorites.length} annonce(s) en shortlist</p>
                  </div>
                </div>
                <div className="watchlist-meta">
                  {favorites.slice(0, 3).map((favorite) => (
                    <span key={favorite.id} className="inline-badge">
                      {favorite.company_name || 'Entreprise'} - {favorite.job_title || 'Role'}
                    </span>
                  ))}
                </div>
                <div className="watchlist-actions">
                  <button className="text-action" onClick={() => onNavigate('ops')}>
                    Ouvrir les favoris
                  </button>
                </div>
              </article>

              <article className="watchlist-card">
                <div className="watchlist-head">
                  <div>
                    <h3>Societes suivies</h3>
                    <p>{favoriteCompanies.length} favorite(s) et {companyPortals.length} veille(s) au total</p>
                  </div>
                </div>
                <div className="watchlist-meta">
                  {favoriteCompanies.slice(0, 4).map((portal) => (
                    <span key={portal.id} className="inline-badge">
                      {portal.company_name}
                    </span>
                  ))}
                </div>
                <div className="watchlist-actions">
                  <button className="text-action" onClick={() => onNavigate('ops')}>
                    Ouvrir la veille societe
                  </button>
                </div>
              </article>
            </div>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 9 }}>
            <div className="panel-head">
              <div>
                <p className="eyebrow">Veille</p>
                <h2>Planifier une surveillance</h2>
              </div>
            </div>

            <form className="watchlist-form" onSubmit={createWatchlist}>
              <label className="field-stack">
                <span>Nom de la veille</span>
                <input
                  value={watchForm.name}
                  onChange={(event) => setWatchForm((prev) => ({ ...prev, name: event.target.value }))}
                  placeholder="Alternance analytics France"
                />
              </label>

              <TagInput
                label="Outils surveilles"
                placeholder="Ajoute plusieurs outils"
                value={watchForm.tools}
                onChange={(tools) => setWatchForm((prev) => ({ ...prev, tools }))}
              />

              <TagInput
                label="Roles cibles"
                placeholder="Data analyst, BI intern, growth ops"
                value={watchForm.roles}
                onChange={(roles) => setWatchForm((prev) => ({ ...prev, roles }))}
              />

              <label className="field-stack">
                <span>Frequence</span>
                <select
                  value={watchForm.cadence}
                  onChange={(event) => setWatchForm((prev) => ({ ...prev, cadence: event.target.value }))}
                >
                  <option value="daily">Tous les jours</option>
                  <option value="every_3_days">Tous les 3 jours</option>
                  <option value="weekly">Chaque semaine</option>
                </select>
              </label>

              <button className="primary-button" type="submit" disabled={submitting || !watchForm.tools.length}>
                {submitting ? 'Creation...' : 'Creer la veille'}
              </button>
              <p className="panel-note">Le scheduling est pret. Le canal Slack sera branche ensuite.</p>
            </form>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 10 }}>
            <div className="panel-head">
              <div>
                <p className="eyebrow">Runs planifies</p>
                <h2>Veilles existantes</h2>
              </div>
            </div>

            <div className="watchlist-stack">
              {watchlists.length === 0 ? (
                <div className="kanban-empty">Aucune veille pour le moment.</div>
              ) : (
                watchlists.map((watchlist) => (
                  <article key={watchlist.id} className="watchlist-card">
                    <div className="watchlist-head">
                      <div>
                        <h3>{watchlist.name}</h3>
                        <p>{watchlist.tools.join(', ')}</p>
                      </div>
                      <span className={`inline-badge ${watchlist.active ? 'is-selected' : ''}`}>
                        {watchlist.active ? 'Active' : 'Pause'}
                      </span>
                    </div>

                    <div className="watchlist-meta">
                      <span className="inline-badge">{CADENCE_LABELS[watchlist.cadence] || watchlist.cadence}</span>
                      {(watchlist.roles || []).map((role) => (
                        <span key={role} className="inline-badge">{role}</span>
                      ))}
                    </div>

                    <p className="panel-note">{formatLatestRun(watchlist)}</p>

                    <div className="watchlist-actions">
                      <button className="text-action" onClick={() => runWatchlistNow(watchlist.id)}>
                        Lancer maintenant
                      </button>
                      <button className="text-action" onClick={() => toggleWatchlist(watchlist)}>
                        {watchlist.active ? 'Mettre en pause' : 'Reactiver'}
                      </button>
                      <button className="text-action danger" onClick={() => deleteWatchlist(watchlist.id)}>
                        Supprimer
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
          </section>
        </div>
      </section>
    </main>
  )
}
