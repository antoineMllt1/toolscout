import { useEffect, useMemo, useState } from 'react'
import AppPageHeader from '../components/AppPageHeader'
import TagInput from '../components/TagInput'
import { useAuth } from '../context/AuthContext'
import { useFavorites } from '../context/FavoritesContext'

const CADENCE_LABELS = {
  daily: 'Quotidien',
  every_3_days: 'Tous les 3 jours',
  weekly: 'Hebdo',
}

function formatDate(value) {
  if (!value) return 'Jamais'
  try {
    return new Date(value).toLocaleString('fr-FR', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return value
  }
}

function SectionHeader({ eyebrow, title, note }) {
  return (
    <div className="panel-head">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
      </div>
      {note ? <p className="panel-note">{note}</p> : null}
    </div>
  )
}

function StatCard({ label, value, tone = '' }) {
  return (
    <article className={`summary-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  )
}

export default function CareerOpsPage({ onNavigate }) {
  const { user, authFetch } = useAuth()
  const { favorites, removeFavorite } = useFavorites()
  const [overview, setOverview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [feedback, setFeedback] = useState('')
  const [portalForm, setPortalForm] = useState({
    company_name: '',
    careers_url: '',
    cadence: 'weekly',
    favorite: true,
    notes: '',
    tags: [],
  })
  const [queueForm, setQueueForm] = useState({ label: '', url: '', company_name: '', role_hint: '', notes: '' })
  const [researchForm, setResearchForm] = useState({ company_name: '', source_url: '', role_title: '' })
  const [storyDraft, setStoryDraft] = useState({
    title: '',
    situation: '',
    task: '',
    action: '',
    result: '',
    reflection: '',
    tags: [],
  })
  const [trainingForm, setTrainingForm] = useState({ title: '', input_text: '' })
  const [projectForm, setProjectForm] = useState({ title: '', input_text: '' })

  useEffect(() => {
    if (!user) {
      setLoading(false)
      return
    }
    void loadOverview()
  }, [user])

  async function loadOverview() {
    setLoading(true)
    try {
      const response = await authFetch('/api/ops/overview')
      if (!response.ok) return
      setOverview(await response.json())
    } finally {
      setLoading(false)
    }
  }

  async function createPortal(event) {
    event.preventDefault()
    const response = await authFetch('/api/company-portals', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...portalForm, active: true }),
    })
    if (!response.ok) {
      setFeedback('Impossible d ajouter cette societe.')
      return
    }
    setPortalForm({
      company_name: '',
      careers_url: '',
      cadence: 'weekly',
      favorite: true,
      notes: '',
      tags: [],
    })
    setFeedback('Societe ajoutee a la veille.')
    await loadOverview()
  }

  async function updatePortal(portalId, patch, successMessage = '') {
    const response = await authFetch(`/api/company-portals/${portalId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    })
    if (!response.ok) {
      setFeedback('Mise a jour impossible.')
      return
    }
    if (successMessage) setFeedback(successMessage)
    await loadOverview()
  }

  async function scanPortal(portalId) {
    const response = await authFetch(`/api/company-portals/${portalId}/scan`, { method: 'POST' })
    if (!response.ok) {
      setFeedback('Le scan a echoue.')
      return
    }
    setFeedback('Scan termine.')
    await loadOverview()
  }

  async function deletePortal(portalId) {
    const response = await authFetch(`/api/company-portals/${portalId}`, { method: 'DELETE' })
    if (!response.ok) return
    setFeedback('Societe retiree de la veille.')
    await loadOverview()
  }

  async function updateQueueStatus(itemId, status) {
    await authFetch(`/api/pipeline-queue/${itemId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    })
    await loadOverview()
  }

  async function addQueueItem(event) {
    event.preventDefault()
    const response = await authFetch('/api/pipeline-queue', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...queueForm, status: 'pending' }),
    })
    if (!response.ok) return
    setQueueForm({ label: '', url: '', company_name: '', role_hint: '', notes: '' })
    setFeedback('Element ajoute a la queue.')
    await loadOverview()
  }

  async function addFavoriteToQueue(favorite) {
    const response = await authFetch('/api/pipeline-queue', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        label: `${favorite.company_name || 'Entreprise'} - ${favorite.job_title || 'Role a relire'}`,
        url: favorite.job_url,
        company_name: favorite.company_name,
        role_hint: favorite.job_title,
        notes: favorite.notes || 'Ajoute depuis les favoris.',
        status: 'pending',
      }),
    })
    if (!response.ok) return
    setFeedback('Favori ajoute a la queue.')
    await loadOverview()
  }

  async function watchFavoriteCompany(favorite) {
    const response = await authFetch('/api/company-portals', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_name: favorite.company_name || 'Company to watch',
        careers_url: favorite.job_url,
        favorite: true,
        active: true,
        cadence: 'weekly',
        notes: `Ajoute depuis favori job: ${favorite.job_title || ''}`.trim(),
      }),
    })
    if (!response.ok) {
      setFeedback('Impossible de convertir ce favori en veille societe.')
      return
    }
    setFeedback('Favori converti en veille societe.')
    await loadOverview()
  }

  async function createStory(event) {
    event.preventDefault()
    const response = await authFetch('/api/story-bank', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(storyDraft),
    })
    if (!response.ok) return
    setStoryDraft({
      title: '',
      situation: '',
      task: '',
      action: '',
      result: '',
      reflection: '',
      tags: [],
    })
    setFeedback('Story ajoutee au bank.')
    await loadOverview()
  }

  async function createStoryFromSuggestion(suggestion) {
    const response = await authFetch('/api/story-bank', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(suggestion),
    })
    if (!response.ok) return
    setFeedback('Suggestion convertie en story.')
    await loadOverview()
  }

  async function generateResearch(event) {
    event.preventDefault()
    const response = await authFetch('/api/company-research/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(researchForm),
    })
    if (!response.ok) {
      setFeedback('Impossible de generer la research.')
      return
    }
    setFeedback('Research snapshot genere.')
    await loadOverview()
  }

  async function evaluateTraining(event) {
    event.preventDefault()
    const response = await authFetch('/api/evaluations/training', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(trainingForm),
    })
    if (!response.ok) return
    setTrainingForm({ title: '', input_text: '' })
    setFeedback('Evaluation training ajoutee.')
    await loadOverview()
  }

  async function evaluateProject(event) {
    event.preventDefault()
    const response = await authFetch('/api/evaluations/project', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(projectForm),
    })
    if (!response.ok) return
    setProjectForm({ title: '', input_text: '' })
    setFeedback('Evaluation projet ajoutee.')
    await loadOverview()
  }

  const portals = overview?.company_portals || []
  const portalRuns = overview?.company_portal_runs || []
  const queue = overview?.pipeline_queue || []
  const stories = overview?.story_bank?.items || []
  const storySuggestions = overview?.story_bank?.suggestions || []
  const research = overview?.company_research || []
  const trainingEvaluations = overview?.training_evaluations || []
  const projectEvaluations = overview?.project_evaluations || []
  const favoriteJobs = favorites

  const queueStats = useMemo(() => ({
    pending: queue.filter((item) => item.status === 'pending').length,
    done: queue.filter((item) => item.status === 'done').length,
    skipped: queue.filter((item) => item.status === 'skipped').length,
  }), [queue])

  const portalStats = useMemo(() => ({
    active: portals.filter((portal) => portal.active).length,
    favorites: portals.filter((portal) => portal.favorite).length,
    newJobs: portals.reduce((sum, portal) => sum + (portal.last_delta?.new_jobs_count || 0), 0),
  }), [portals])

  if (!user) {
    return (
      <main className="ops-page">
        <section className="empty-panel">
          <p className="eyebrow">Compte requis</p>
          <h3>Connecte-toi pour piloter la veille societe, les favoris et les briques career ops.</h3>
          <button className="primary-button" onClick={() => onNavigate('auth')}>
            Ouvrir la connexion
          </button>
        </section>
      </main>
    )
  }

  if (loading) {
    return (
      <main className="ops-page">
        <section className="empty-panel">
          <p className="eyebrow">Career ops</p>
          <h3>Chargement du workspace...</h3>
        </section>
      </main>
    )
  }

  return (
    <main className="ops-page">
      <AppPageHeader
        eyebrow="Career ops"
        title="Veille, priorisation et actions"
        description="Suis tes societes cibles, garde les meilleures annonces et transforme les signaux en actions concretes."
        actions={
          <>
            <button className="primary-button" onClick={() => onNavigate('search')}>
              Retour recherche
            </button>
            <button className="secondary-button" onClick={() => onNavigate('dashboard')}>
              Retour cockpit
            </button>
          </>
        }
        stats={[
          { label: 'Societes suivies', value: portals.length, tone: 'tone-blue' },
          { label: 'Favoris jobs', value: favoriteJobs.length, tone: 'tone-green' },
          { label: 'Nouveaux liens', value: portalStats.newJobs, tone: 'tone-yellow' },
        ]}
      />

      {feedback ? <div className="feedback-box info">{feedback}</div> : null}

      <section className="ops-layout">
        <div className="ops-main-column">
          <section className="panel-shell fade-stagger" style={{ '--index': 1 }}>
            <SectionHeader eyebrow="Company watch" title="Veille societe" note="Scan, tags, cadence et priorite." />

            <form className="ops-form-grid" onSubmit={createPortal}>
              <label className="field-stack">
                <span>Entreprise</span>
                <input
                  value={portalForm.company_name}
                  onChange={(event) => setPortalForm((prev) => ({ ...prev, company_name: event.target.value }))}
                />
              </label>
              <label className="field-stack">
                <span>URL de veille</span>
                <input
                  value={portalForm.careers_url}
                  onChange={(event) => setPortalForm((prev) => ({ ...prev, careers_url: event.target.value }))}
                  placeholder="https://company.com/careers"
                />
              </label>
              <label className="field-stack">
                <span>Cadence</span>
                <select
                  value={portalForm.cadence}
                  onChange={(event) => setPortalForm((prev) => ({ ...prev, cadence: event.target.value }))}
                >
                  <option value="daily">Quotidien</option>
                  <option value="every_3_days">Tous les 3 jours</option>
                  <option value="weekly">Hebdo</option>
                </select>
              </label>
              <label className="field-stack">
                <span>Priorite</span>
                <select
                  value={portalForm.favorite ? 'favorite' : 'normal'}
                  onChange={(event) => setPortalForm((prev) => ({ ...prev, favorite: event.target.value === 'favorite' }))}
                >
                  <option value="favorite">Favorite</option>
                  <option value="normal">Normale</option>
                </select>
              </label>
              <label className="field-stack ops-span-2">
                <span>Notes</span>
                <textarea
                  rows={3}
                  value={portalForm.notes}
                  onChange={(event) => setPortalForm((prev) => ({ ...prev, notes: event.target.value }))}
                  placeholder="Pourquoi cette societe compte pour toi."
                />
              </label>
              <div className="ops-span-2">
                <TagInput
                  label="Tags"
                  placeholder="ai, stage, saas, remote"
                  value={portalForm.tags}
                  onChange={(tags) => setPortalForm((prev) => ({ ...prev, tags }))}
                />
              </div>
              <button className="primary-button" type="submit">
                Ajouter la societe
              </button>
            </form>

            <div className="ops-stack">
              {portals.length === 0 ? (
                <div className="cv-empty-slot">Aucune societe suivie pour le moment.</div>
              ) : (
                portals.map((portal) => (
                  <article key={portal.id} className={`coach-card company-watch-card ${portal.favorite ? 'is-favorite' : ''}`}>
                    <div className="portfolio-summary-head">
                      <div>
                        <p className="eyebrow">Societe</p>
                        <h3>{portal.company_name}</h3>
                        <p>{portal.careers_url}</p>
                      </div>
                      <div className="cv-draft-meta">
                        {portal.favorite ? <span className="inline-badge is-selected">Favorie</span> : null}
                        <span className="inline-badge">{CADENCE_LABELS[portal.cadence] || portal.cadence}</span>
                        <span className="inline-badge">{portal.active ? 'Active' : 'Pause'}</span>
                      </div>
                    </div>

                    <div className="coach-chip-row">
                      <span className="inline-badge">Scan {formatDate(portal.last_scan_at)}</span>
                      <span className="inline-badge">Prochain {formatDate(portal.next_scan_at)}</span>
                      <span className="inline-badge">{portal.last_result?.jobs_found?.length || 0} liens</span>
                      {!!portal.last_delta?.new_jobs_count && (
                        <span className="inline-badge is-selected">{portal.last_delta.new_jobs_count} nouveaux</span>
                      )}
                    </div>

                    {portal.notes ? <p>{portal.notes}</p> : null}

                    {(portal.tags || []).length ? (
                      <div className="coach-chip-row">
                        {portal.tags.map((tag) => (
                          <span key={tag} className="inline-badge">{tag}</span>
                        ))}
                      </div>
                    ) : null}

                    {portal.last_delta?.summary ? (
                      <div className="watch-delta-card">
                        <strong>{portal.last_delta.summary}</strong>
                        {(portal.last_delta.new_jobs || []).length ? (
                          <div className="portal-result-list">
                            {portal.last_delta.new_jobs.map((job) => (
                              <a key={job.url} className="text-action" href={job.url} target="_blank" rel="noreferrer">
                                {job.title}
                              </a>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ) : null}

                    {(portal.last_result?.jobs_found || []).length ? (
                      <div className="portal-result-list">
                        {portal.last_result.jobs_found.slice(0, 6).map((job) => (
                          <a key={job.url} className="text-action" href={job.url} target="_blank" rel="noreferrer">
                            {job.title}
                          </a>
                        ))}
                      </div>
                    ) : null}

                    <div className="cv-panel-actions">
                      <button className="secondary-button" type="button" onClick={() => scanPortal(portal.id)}>
                        Scanner
                      </button>
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => updatePortal(portal.id, { favorite: !portal.favorite }, portal.favorite ? 'Societe retiree des favorites.' : 'Societe marquee en favorite.')}
                      >
                        {portal.favorite ? 'Retirer favorite' : 'Mettre favorite'}
                      </button>
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => updatePortal(portal.id, { active: !portal.active }, portal.active ? 'Veille mise en pause.' : 'Veille reactivee.')}
                      >
                        {portal.active ? 'Pause' : 'Reactiver'}
                      </button>
                      <button
                        className="text-action"
                        type="button"
                        onClick={() => setResearchForm({ company_name: portal.company_name, source_url: portal.careers_url, role_title: researchForm.role_title })}
                      >
                        Preparer research
                      </button>
                      <button className="text-action danger" type="button" onClick={() => deletePortal(portal.id)}>
                        Supprimer
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 2 }}>
            <SectionHeader eyebrow="Pipeline" title="Queue d opportunites" note="Empile les liens a traiter, puis fais avancer le flux." />

            <form className="ops-form-grid" onSubmit={addQueueItem}>
              <label className="field-stack">
                <span>Label</span>
                <input
                  value={queueForm.label}
                  onChange={(event) => setQueueForm((prev) => ({ ...prev, label: event.target.value }))}
                  placeholder="Anthropic - AI PM internship"
                />
              </label>
              <label className="field-stack">
                <span>URL</span>
                <input value={queueForm.url} onChange={(event) => setQueueForm((prev) => ({ ...prev, url: event.target.value }))} />
              </label>
              <label className="field-stack">
                <span>Entreprise</span>
                <input value={queueForm.company_name} onChange={(event) => setQueueForm((prev) => ({ ...prev, company_name: event.target.value }))} />
              </label>
              <label className="field-stack">
                <span>Role hint</span>
                <input value={queueForm.role_hint} onChange={(event) => setQueueForm((prev) => ({ ...prev, role_hint: event.target.value }))} />
              </label>
              <label className="field-stack ops-span-2">
                <span>Notes</span>
                <textarea rows={3} value={queueForm.notes} onChange={(event) => setQueueForm((prev) => ({ ...prev, notes: event.target.value }))} />
              </label>
              <button className="primary-button" type="submit">
                Ajouter a la queue
              </button>
            </form>

            <div className="ops-card-grid">
              {queue.map((item) => (
                <article key={item.id} className="coach-card">
                  <p className="eyebrow">{item.company_name || 'Queue item'}</p>
                  <h3>{item.label}</h3>
                  <p>{item.role_hint || item.notes || 'Pas de precision supplementaire.'}</p>
                  <div className="coach-chip-row">
                    <span className="inline-badge">{item.status}</span>
                    <span className="inline-badge">{formatDate(item.created_at)}</span>
                  </div>
                  <div className="cv-panel-actions">
                    <button className="secondary-button" type="button" onClick={() => updateQueueStatus(item.id, 'done')}>
                      Done
                    </button>
                    <button className="secondary-button" type="button" onClick={() => updateQueueStatus(item.id, 'skipped')}>
                      Skip
                    </button>
                    {item.url ? (
                      <a className="text-action" href={item.url} target="_blank" rel="noreferrer">
                        Ouvrir
                      </a>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 3 }}>
            <SectionHeader eyebrow="Deep" title="Research entreprise" note="Produit, culture et risques avant de postuler." />

            <form className="ops-form-grid" onSubmit={generateResearch}>
              <label className="field-stack">
                <span>Entreprise</span>
                <input value={researchForm.company_name} onChange={(event) => setResearchForm((prev) => ({ ...prev, company_name: event.target.value }))} />
              </label>
              <label className="field-stack">
                <span>Source URL</span>
                <input value={researchForm.source_url} onChange={(event) => setResearchForm((prev) => ({ ...prev, source_url: event.target.value }))} placeholder="https://company.com/about" />
              </label>
              <label className="field-stack">
                <span>Role cible</span>
                <input value={researchForm.role_title} onChange={(event) => setResearchForm((prev) => ({ ...prev, role_title: event.target.value }))} />
              </label>
              <button className="primary-button" type="submit">
                Generer le snapshot
              </button>
            </form>

            <div className="ops-stack">
              {research.map((item) => (
                <article key={item.id} className="coach-card">
                  <p className="eyebrow">{item.company_name}</p>
                  <h3>{item.role_title || 'Research snapshot'}</h3>
                  <p>{item.summary}</p>
                  <div className="candidate-brief-grid compact">
                    <article className="candidate-brief-card">
                      <p className="eyebrow">Product</p>
                      <ul className="signal-list">
                        {(item.product_signals || []).map((signal) => (
                          <li key={signal}>{signal}</li>
                        ))}
                      </ul>
                    </article>
                    <article className="candidate-brief-card">
                      <p className="eyebrow">Culture</p>
                      <ul className="signal-list">
                        {(item.culture_signals || []).map((signal) => (
                          <li key={signal}>{signal}</li>
                        ))}
                      </ul>
                    </article>
                    <article className="candidate-brief-card">
                      <p className="eyebrow">Risques</p>
                      <ul className="signal-list">
                        {(item.risks || []).map((signal) => (
                          <li key={signal}>{signal}</li>
                        ))}
                      </ul>
                    </article>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </div>

        <div className="ops-side-column">
          <section className="panel-shell fade-stagger" style={{ '--index': 2 }}>
            <SectionHeader eyebrow="Favorites" title="Jobs favoris" note="Les annonces a ne pas perdre." />

            <div className="candidate-brief-card ops-summary-card">
              <p className="eyebrow">Lecture rapide</p>
              <h3>{portalStats.favorites} societes favorites</h3>
              <p>{portalStats.active} veilles actives et {queueStats.pending} opportunites en attente.</p>
              <div className="coach-chip-row">
                <span className="inline-badge">{favoriteJobs.length} jobs favoris</span>
                <span className="inline-badge">{stories.length} stories</span>
                <span className="inline-badge">{portalRuns.length} scans</span>
              </div>
            </div>

            <div className="ops-stack">
              {favoriteJobs.length === 0 ? (
                <div className="cv-empty-slot">Aucun favori pour le moment.</div>
              ) : (
                favoriteJobs.map((favorite) => (
                  <article key={favorite.id} className="coach-card favorite-job-card">
                    <p className="eyebrow">{favorite.company_name || 'Favori job'}</p>
                    <h3>{favorite.job_title || 'Annonce sauvegardee'}</h3>
                    <p>{favorite.location || favorite.source || 'A completer'}</p>
                    <div className="coach-chip-row">
                      {favorite.source ? <span className="inline-badge">{favorite.source}</span> : null}
                      {favorite.contract_type ? <span className="inline-badge">{favorite.contract_type}</span> : null}
                    </div>
                    <div className="cv-panel-actions">
                      <a className="text-action" href={favorite.job_url} target="_blank" rel="noreferrer">
                        Ouvrir
                      </a>
                      <button className="text-action" type="button" onClick={() => addFavoriteToQueue(favorite)}>
                        Envoyer en queue
                      </button>
                      <button className="text-action" type="button" onClick={() => watchFavoriteCompany(favorite)}>
                        Suivre societe
                      </button>
                      <button className="text-action danger" type="button" onClick={() => removeFavorite(favorite.id)}>
                        Retirer
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 3 }}>
            <SectionHeader eyebrow="Activity" title="Derniers scans" note="Historique compact de la veille societe." />

            <div className="ops-stack">
              {portalRuns.length === 0 ? (
                <div className="cv-empty-slot">Aucun scan historise pour le moment.</div>
              ) : (
                portalRuns.slice(0, 8).map((run) => (
                  <article key={run.id} className="coach-card watch-run-card">
                    <p className="eyebrow">{run.company_name || 'Company watch'}</p>
                    <h3>{run.summary?.delta?.summary || run.status}</h3>
                    <div className="coach-chip-row">
                      <span className="inline-badge">{run.jobs_found} liens</span>
                      <span className="inline-badge">{run.new_jobs} nouveaux</span>
                      <span className="inline-badge">{run.removed_jobs} retires</span>
                    </div>
                    <p>Run {formatDate(run.completed_at || run.started_at)}</p>
                  </article>
                ))
              )}
            </div>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 4 }}>
            <SectionHeader eyebrow="Story bank" title="STAR + R bank" note="Tu capitalises les histoires importantes." />

            <div className="ops-stack">
              {storySuggestions.length ? (
                <article className="candidate-brief-card">
                  <p className="eyebrow">Suggestions</p>
                  <h3>A convertir en stories</h3>
                  <div className="ops-stack">
                    {storySuggestions.map((item) => (
                      <div key={`${item.kind}-${item.title}`} className="story-suggestion-row">
                        <div>
                          <strong>{item.title}</strong>
                          <p>{item.situation || item.action}</p>
                        </div>
                        <button className="secondary-button" type="button" onClick={() => createStoryFromSuggestion(item)}>
                          Ajouter
                        </button>
                      </div>
                    ))}
                  </div>
                </article>
              ) : null}

              <form className="ops-stack" onSubmit={createStory}>
                <label className="field-stack">
                  <span>Titre</span>
                  <input value={storyDraft.title} onChange={(event) => setStoryDraft((prev) => ({ ...prev, title: event.target.value }))} />
                </label>
                <label className="field-stack">
                  <span>Situation</span>
                  <textarea rows={2} value={storyDraft.situation} onChange={(event) => setStoryDraft((prev) => ({ ...prev, situation: event.target.value }))} />
                </label>
                <label className="field-stack">
                  <span>Task</span>
                  <textarea rows={2} value={storyDraft.task} onChange={(event) => setStoryDraft((prev) => ({ ...prev, task: event.target.value }))} />
                </label>
                <label className="field-stack">
                  <span>Action</span>
                  <textarea rows={3} value={storyDraft.action} onChange={(event) => setStoryDraft((prev) => ({ ...prev, action: event.target.value }))} />
                </label>
                <label className="field-stack">
                  <span>Result</span>
                  <textarea rows={2} value={storyDraft.result} onChange={(event) => setStoryDraft((prev) => ({ ...prev, result: event.target.value }))} />
                </label>
                <label className="field-stack">
                  <span>Reflection</span>
                  <textarea rows={2} value={storyDraft.reflection} onChange={(event) => setStoryDraft((prev) => ({ ...prev, reflection: event.target.value }))} />
                </label>
                <div>
                  <TagInput
                    label="Tags"
                    placeholder="leadership, product, analytics"
                    value={storyDraft.tags}
                    onChange={(tags) => setStoryDraft((prev) => ({ ...prev, tags }))}
                  />
                </div>
                <button className="primary-button" type="submit">
                  Ajouter la story
                </button>
              </form>
            </div>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 5 }}>
            <SectionHeader eyebrow="Training" title="Evaluer un training" note="Est-ce que ce training vaut reellement ton temps ?" />

            <form className="ops-stack" onSubmit={evaluateTraining}>
              <label className="field-stack">
                <span>Titre</span>
                <input value={trainingForm.title} onChange={(event) => setTrainingForm((prev) => ({ ...prev, title: event.target.value }))} placeholder="PL-300" />
              </label>
              <label className="field-stack">
                <span>Programme / sujet</span>
                <textarea rows={4} value={trainingForm.input_text} onChange={(event) => setTrainingForm((prev) => ({ ...prev, input_text: event.target.value }))} />
              </label>
              <button className="primary-button" type="submit">
                Evaluer
              </button>
            </form>

            <div className="ops-stack">
              {trainingEvaluations.map((item) => (
                <article key={item.id} className="coach-card">
                  <p className="eyebrow">{item.title || 'Training'}</p>
                  <h3>{item.output?.verdict}</h3>
                  <div className="coach-chip-row">
                    <span className="inline-badge">Score {item.output?.score}/5</span>
                    {(item.output?.role_tracks || []).map((track) => (
                      <span key={track} className="inline-badge">{track}</span>
                    ))}
                  </div>
                  <ul className="signal-list">
                    {(item.output?.reasons || []).map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 6 }}>
            <SectionHeader eyebrow="Project" title="Evaluer une idee de projet" note="Un bon projet doit aider le dossier." />

            <form className="ops-stack" onSubmit={evaluateProject}>
              <label className="field-stack">
                <span>Titre</span>
                <input value={projectForm.title} onChange={(event) => setProjectForm((prev) => ({ ...prev, title: event.target.value }))} placeholder="SaaS analytics dashboard" />
              </label>
              <label className="field-stack">
                <span>Idee</span>
                <textarea rows={4} value={projectForm.input_text} onChange={(event) => setProjectForm((prev) => ({ ...prev, input_text: event.target.value }))} />
              </label>
              <button className="primary-button" type="submit">
                Evaluer
              </button>
            </form>

            <div className="ops-stack">
              {projectEvaluations.map((item) => (
                <article key={item.id} className="coach-card">
                  <p className="eyebrow">{item.title || 'Project idea'}</p>
                  <h3>{item.output?.verdict}</h3>
                  <div className="coach-chip-row">
                    <span className="inline-badge">Score {item.output?.score}/5</span>
                    {(item.output?.role_tracks || []).map((track) => (
                      <span key={track} className="inline-badge">{track}</span>
                    ))}
                  </div>
                  <div className="review-block">
                    <span>Deliverables</span>
                    <ul className="signal-list">
                      {(item.output?.deliverables || []).map((entry) => (
                        <li key={entry}>{entry}</li>
                      ))}
                    </ul>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </div>
      </section>
    </main>
  )
}
