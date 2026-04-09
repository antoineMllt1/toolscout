import { useEffect, useMemo, useState } from 'react'
import TagInput from '../components/TagInput'
import { useApplications } from '../context/ApplicationContext'
import { useAuth } from '../context/AuthContext'
import { useSearch } from '../context/SearchContext'

const EMPTY_PROFILE = {
  title: 'Main profile',
  full_name: '',
  headline: '',
  email: '',
  phone: '',
  location: '',
  website: '',
  linkedin: '',
  github: '',
  summary: '',
  skills: [],
  languages: [],
  certifications: [],
  education: [],
  experience: [],
  projects: [],
}

function linesToArray(value) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

function arrayToLines(values) {
  return (values || []).join('\n')
}

function makeId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `cv-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function createEducation() {
  return {
    id: makeId(),
    school: '',
    degree: '',
    field: '',
    location: '',
    start_date: '',
    end_date: '',
    summary: '',
    highlights: [],
    skills: [],
    featured: false,
  }
}

function createExperience() {
  return {
    id: makeId(),
    company: '',
    title: '',
    location: '',
    start_date: '',
    end_date: '',
    summary: '',
    highlights: [],
    skills: [],
    featured: false,
  }
}

function createProject() {
  return {
    id: makeId(),
    name: '',
    role: '',
    url: '',
    summary: '',
    highlights: [],
    technologies: [],
    featured: false,
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

function ExperienceEditor({ items, onChange }) {
  const updateItem = (id, patch) => {
    onChange(items.map((item) => (item.id === id ? { ...item, ...patch } : item)))
  }

  return (
    <div className="cv-stack">
      <div className="cv-section-head">
        <div>
          <p className="eyebrow">Experience</p>
          <h3>Experiences professionnelles</h3>
        </div>
        <button className="secondary-button" type="button" onClick={() => onChange([...items, createExperience()])}>
          Ajouter
        </button>
      </div>

      {items.length === 0 ? <div className="cv-empty-slot">Aucune experience pour le moment.</div> : null}

      {items.map((item) => (
        <article key={item.id} className="cv-entry-card">
          <div className="cv-entry-head">
            <h4>{item.title || item.company || 'Nouvelle experience'}</h4>
            <div className="cv-entry-actions">
              <label className="cv-toggle">
                <input
                  type="checkbox"
                  checked={Boolean(item.featured)}
                  onChange={(event) => updateItem(item.id, { featured: event.target.checked })}
                />
                <span>Mettre en avant</span>
              </label>
              <button className="text-action danger" type="button" onClick={() => onChange(items.filter((entry) => entry.id !== item.id))}>
                Supprimer
              </button>
            </div>
          </div>

          <div className="cv-entry-grid">
            <label className="field-stack">
              <span>Poste</span>
              <input value={item.title} onChange={(event) => updateItem(item.id, { title: event.target.value })} />
            </label>
            <label className="field-stack">
              <span>Entreprise</span>
              <input value={item.company} onChange={(event) => updateItem(item.id, { company: event.target.value })} />
            </label>
            <label className="field-stack">
              <span>Lieu</span>
              <input value={item.location} onChange={(event) => updateItem(item.id, { location: event.target.value })} />
            </label>
            <label className="field-stack">
              <span>Dates</span>
              <div className="cv-date-row">
                <input
                  value={item.start_date}
                  onChange={(event) => updateItem(item.id, { start_date: event.target.value })}
                  placeholder="2024"
                />
                <input
                  value={item.end_date}
                  onChange={(event) => updateItem(item.id, { end_date: event.target.value })}
                  placeholder="Present"
                />
              </div>
            </label>
          </div>

          <label className="field-stack">
            <span>Resume factuel</span>
            <textarea
              rows={3}
              value={item.summary}
              onChange={(event) => updateItem(item.id, { summary: event.target.value })}
              placeholder="Contexte, responsabilites, outils, resultats deja verifies."
            />
          </label>

          <div className="cv-entry-grid">
            <label className="field-stack">
              <span>Highlights verifies</span>
              <textarea
                rows={4}
                value={arrayToLines(item.highlights)}
                onChange={(event) => updateItem(item.id, { highlights: linesToArray(event.target.value) })}
                placeholder={'Une ligne = un fait reel\nEx: Automatisation de reporting Power BI'}
              />
            </label>
            <label className="field-stack">
              <span>Competences mobilisees</span>
              <textarea
                rows={4}
                value={arrayToLines(item.skills)}
                onChange={(event) => updateItem(item.id, { skills: linesToArray(event.target.value) })}
                placeholder={'SQL\nPower BI\nStakeholder management'}
              />
            </label>
          </div>
        </article>
      ))}
    </div>
  )
}

function ProjectEditor({ items, onChange }) {
  const updateItem = (id, patch) => {
    onChange(items.map((item) => (item.id === id ? { ...item, ...patch } : item)))
  }

  return (
    <div className="cv-stack">
      <div className="cv-section-head">
        <div>
          <p className="eyebrow">Projects</p>
          <h3>Projets</h3>
        </div>
        <button className="secondary-button" type="button" onClick={() => onChange([...items, createProject()])}>
          Ajouter
        </button>
      </div>

      {items.length === 0 ? <div className="cv-empty-slot">Aucun projet pour le moment.</div> : null}

      {items.map((item) => (
        <article key={item.id} className="cv-entry-card">
          <div className="cv-entry-head">
            <h4>{item.name || item.role || 'Nouveau projet'}</h4>
            <div className="cv-entry-actions">
              <label className="cv-toggle">
                <input
                  type="checkbox"
                  checked={Boolean(item.featured)}
                  onChange={(event) => updateItem(item.id, { featured: event.target.checked })}
                />
                <span>Mettre en avant</span>
              </label>
              <button className="text-action danger" type="button" onClick={() => onChange(items.filter((entry) => entry.id !== item.id))}>
                Supprimer
              </button>
            </div>
          </div>

          <div className="cv-entry-grid">
            <label className="field-stack">
              <span>Nom</span>
              <input value={item.name} onChange={(event) => updateItem(item.id, { name: event.target.value })} />
            </label>
            <label className="field-stack">
              <span>Role</span>
              <input value={item.role} onChange={(event) => updateItem(item.id, { role: event.target.value })} />
            </label>
            <label className="field-stack">
              <span>Lien</span>
              <input value={item.url} onChange={(event) => updateItem(item.id, { url: event.target.value })} />
            </label>
          </div>

          <label className="field-stack">
            <span>Resume factuel</span>
            <textarea
              rows={3}
              value={item.summary}
              onChange={(event) => updateItem(item.id, { summary: event.target.value })}
              placeholder="Objectif, stack, perimetre, resultats deja verifies."
            />
          </label>

          <div className="cv-entry-grid">
            <label className="field-stack">
              <span>Highlights verifies</span>
              <textarea
                rows={4}
                value={arrayToLines(item.highlights)}
                onChange={(event) => updateItem(item.id, { highlights: linesToArray(event.target.value) })}
              />
            </label>
            <label className="field-stack">
              <span>Technologies</span>
              <textarea
                rows={4}
                value={arrayToLines(item.technologies)}
                onChange={(event) => updateItem(item.id, { technologies: linesToArray(event.target.value) })}
              />
            </label>
          </div>
        </article>
      ))}
    </div>
  )
}

function EducationEditor({ items, onChange }) {
  const updateItem = (id, patch) => {
    onChange(items.map((item) => (item.id === id ? { ...item, ...patch } : item)))
  }

  return (
    <div className="cv-stack">
      <div className="cv-section-head">
        <div>
          <p className="eyebrow">Education</p>
          <h3>Formation</h3>
        </div>
        <button className="secondary-button" type="button" onClick={() => onChange([...items, createEducation()])}>
          Ajouter
        </button>
      </div>

      {items.length === 0 ? <div className="cv-empty-slot">Aucune formation pour le moment.</div> : null}

      {items.map((item) => (
        <article key={item.id} className="cv-entry-card">
          <div className="cv-entry-head">
            <h4>{item.degree || item.school || 'Nouvelle formation'}</h4>
            <div className="cv-entry-actions">
              <label className="cv-toggle">
                <input
                  type="checkbox"
                  checked={Boolean(item.featured)}
                  onChange={(event) => updateItem(item.id, { featured: event.target.checked })}
                />
                <span>Mettre en avant</span>
              </label>
              <button className="text-action danger" type="button" onClick={() => onChange(items.filter((entry) => entry.id !== item.id))}>
                Supprimer
              </button>
            </div>
          </div>

          <div className="cv-entry-grid">
            <label className="field-stack">
              <span>Ecole</span>
              <input value={item.school} onChange={(event) => updateItem(item.id, { school: event.target.value })} />
            </label>
            <label className="field-stack">
              <span>Diplome</span>
              <input value={item.degree} onChange={(event) => updateItem(item.id, { degree: event.target.value })} />
            </label>
            <label className="field-stack">
              <span>Domaine</span>
              <input value={item.field} onChange={(event) => updateItem(item.id, { field: event.target.value })} />
            </label>
            <label className="field-stack">
              <span>Lieu</span>
              <input value={item.location} onChange={(event) => updateItem(item.id, { location: event.target.value })} />
            </label>
            <label className="field-stack">
              <span>Dates</span>
              <div className="cv-date-row">
                <input
                  value={item.start_date}
                  onChange={(event) => updateItem(item.id, { start_date: event.target.value })}
                  placeholder="2022"
                />
                <input
                  value={item.end_date}
                  onChange={(event) => updateItem(item.id, { end_date: event.target.value })}
                  placeholder="2025"
                />
              </div>
            </label>
          </div>

          <label className="field-stack">
            <span>Resume factuel</span>
            <textarea rows={3} value={item.summary} onChange={(event) => updateItem(item.id, { summary: event.target.value })} />
          </label>

          <div className="cv-entry-grid">
            <label className="field-stack">
              <span>Highlights verifies</span>
              <textarea
                rows={4}
                value={arrayToLines(item.highlights)}
                onChange={(event) => updateItem(item.id, { highlights: linesToArray(event.target.value) })}
              />
            </label>
            <label className="field-stack">
              <span>Competences utiles</span>
              <textarea
                rows={4}
                value={arrayToLines(item.skills)}
                onChange={(event) => updateItem(item.id, { skills: linesToArray(event.target.value) })}
              />
            </label>
          </div>
        </article>
      ))}
    </div>
  )
}

function DraftCard({ draft, active, onSelect }) {
  const selected = draft.selected_payload || {}
  const counts = selected.match_summary?.selected_counts || {}

  return (
    <article className={`cv-draft-card ${active ? 'is-active' : ''}`} onClick={() => onSelect(draft.id)}>
      <p className="eyebrow">{draft.template_slug}</p>
      <h4>{draft.target_title || 'Draft cible'}</h4>
      <p>{draft.target_company || 'Entreprise a confirmer'}</p>
      <div className="cv-draft-meta">
        <span className="inline-badge">{draft.source_kind}</span>
        <span className="inline-badge">{counts.experience || 0} exp</span>
        <span className="inline-badge">{counts.projects || 0} proj</span>
      </div>
    </article>
  )
}

export default function CvStudioPage({ onNavigate }) {
  const { user, authFetch } = useAuth()
  const { applications } = useApplications()
  const { selectedResult } = useSearch()

  const [profile, setProfile] = useState(EMPTY_PROFILE)
  const [templates, setTemplates] = useState([])
  const [drafts, setDrafts] = useState([])
  const [selectedDraftId, setSelectedDraftId] = useState(null)
  const [copySuggestionsByDraft, setCopySuggestionsByDraft] = useState({})
  const [templateSlug, setTemplateSlug] = useState('moderncv-classic')
  const [sourceMode, setSourceMode] = useState('selected-result')
  const [applicationId, setApplicationId] = useState('')
  const [savingProfile, setSavingProfile] = useState(false)
  const [generatingDraft, setGeneratingDraft] = useState(false)
  const [enhancingDraft, setEnhancingDraft] = useState(false)
  const [feedback, setFeedback] = useState('')

  useEffect(() => {
    if (!selectedResult) {
      setSourceMode('application')
    }
  }, [selectedResult])

  useEffect(() => {
    if (!user) return
    void Promise.all([loadProfile(), loadTemplates(), loadDrafts()])
  }, [user])

  const selectedDraft = useMemo(
    () => drafts.find((draft) => draft.id === selectedDraftId) || drafts[0] || null,
    [drafts, selectedDraftId],
  )

  async function loadProfile() {
    const response = await authFetch('/api/cv/profile')
    if (!response.ok) return
    setProfile(await response.json())
  }

  async function loadTemplates() {
    const response = await fetch('/api/cv/templates')
    if (!response.ok) return
    setTemplates(await response.json())
  }

  async function loadDrafts() {
    const response = await authFetch('/api/cv/drafts')
    if (!response.ok) return
    const data = await response.json()
    setDrafts(data)
    if (data.length) setSelectedDraftId((current) => current ?? data[0].id)
  }

  async function saveProfile() {
    setSavingProfile(true)
    setFeedback('')
    try {
      const response = await authFetch('/api/cv/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      })
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Unable to save profile')
      }
      const data = await response.json()
      setProfile(data)
      setFeedback('Profil CV sauvegarde.')
    } catch (error) {
      setFeedback(error.message)
    } finally {
      setSavingProfile(false)
    }
  }

  async function generateDraft() {
    setGeneratingDraft(true)
    setFeedback('')
    try {
      const payload = { template_slug: templateSlug }
      if (sourceMode === 'selected-result' && selectedResult?.id) {
        payload.result_id = selectedResult.id
      } else if (applicationId) {
        payload.application_id = Number(applicationId)
      } else {
        throw new Error('Choisis une annonce ou une candidature.')
      }

      const response = await authFetch('/api/cv/drafts/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Unable to generate draft')
      }
      const draft = await response.json()
      setDrafts((prev) => [draft, ...prev.filter((item) => item.id !== draft.id)])
      setSelectedDraftId(draft.id)
      setFeedback('Draft moderncv genere.')
    } catch (error) {
      setFeedback(error.message)
    } finally {
      setGeneratingDraft(false)
    }
  }

  async function downloadDraft(draft) {
    const response = await authFetch(`/api/cv/drafts/${draft.id}/tex`)
    if (!response.ok) return
    const source = await response.text()
    const blob = new Blob([source], { type: 'text/x-tex' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `toolscout-cv-${draft.id}.tex`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  async function enhanceDraft(draft) {
    setEnhancingDraft(true)
    setFeedback('')
    try {
      const response = await authFetch(`/api/cv/drafts/${draft.id}/copywrite`, { method: 'POST' })
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.detail || 'Unable to improve draft')
      }
      setCopySuggestionsByDraft((prev) => ({ ...prev, [draft.id]: payload.suggestions }))
      setFeedback('Suggestions Haiku recues.')
    } catch (error) {
      setFeedback(error.message)
    } finally {
      setEnhancingDraft(false)
    }
  }

  if (!user) {
    return (
      <main className="cv-page">
        <section className="empty-panel">
          <p className="eyebrow">Compte requis</p>
          <h3>Connecte-toi pour saisir ton profil et generer des CV cibles par annonce.</h3>
          <button className="primary-button" onClick={() => onNavigate('auth')}>
            Ouvrir la connexion
          </button>
        </section>
      </main>
    )
  }

  const selectedPayload = selectedDraft?.selected_payload || {}
  const selectedCounts = selectedPayload.match_summary?.selected_counts || {}
  const copySuggestions = selectedDraft ? copySuggestionsByDraft[selectedDraft.id] : null

  return (
    <main className="cv-page">
      <section className="cv-hero-grid">
        <article className="hero-slab dark fade-stagger" style={{ '--index': 0 }}>
          <div className="hero-copy">
            <p className="eyebrow is-light">CV Studio</p>
            <h1 className="dashboard-display">Genere un CV cible sans laisser l'IA inventer.</h1>
            <p className="lede is-light">
              Le profil utilisateur reste la source de verite. Le moteur choisit les experiences, projets
              et competences qui matchent l'annonce, puis sort un draft strict compatible moderncv.
            </p>
          </div>
          <div className="hero-action-row">
            <button className="primary-button light" onClick={() => onNavigate('search')}>
              Retour aux annonces
            </button>
            <button className="secondary-button dark" onClick={() => onNavigate('dashboard')}>
              Retour cockpit
            </button>
          </div>
        </article>

        <aside className="hero-rail">
          <article className="rail-panel fade-stagger" style={{ '--index': 1 }}>
            <p className="eyebrow">Regles strictes</p>
            <h2>Le draft part uniquement de tes faits verifies.</h2>
            <p>La future API IA servira au copywriting, pas a inventer des experiences ou des chiffres.</p>
          </article>

          <div className="dashboard-summary-grid">
            <article className="summary-card tone-blue fade-stagger" style={{ '--index': 2 }}>
              <span>Templates</span>
              <strong>{templates.length}</strong>
            </article>
            <article className="summary-card tone-green fade-stagger" style={{ '--index': 3 }}>
              <span>Drafts</span>
              <strong>{drafts.length}</strong>
            </article>
            <article className="summary-card tone-yellow fade-stagger" style={{ '--index': 4 }}>
              <span>Candidatures</span>
              <strong>{applications.length}</strong>
            </article>
          </div>
        </aside>
      </section>

      <section className="cv-layout">
        <div className="cv-main-column">
          <section className="panel-shell fade-stagger" style={{ '--index': 5 }}>
            <SectionHeader
              eyebrow="Profil"
              title="Informations de base"
              note="Renseigne les donnees stables du CV. Ce bloc nourrit tous les drafts."
            />

            <div className="cv-entry-grid cv-basics-grid">
              <label className="field-stack">
                <span>Nom complet</span>
                <input value={profile.full_name} onChange={(event) => setProfile((prev) => ({ ...prev, full_name: event.target.value }))} />
              </label>
              <label className="field-stack">
                <span>Headline</span>
                <input value={profile.headline} onChange={(event) => setProfile((prev) => ({ ...prev, headline: event.target.value }))} placeholder="Data analyst | Automation | BI" />
              </label>
              <label className="field-stack">
                <span>Email</span>
                <input value={profile.email} onChange={(event) => setProfile((prev) => ({ ...prev, email: event.target.value }))} />
              </label>
              <label className="field-stack">
                <span>Telephone</span>
                <input value={profile.phone} onChange={(event) => setProfile((prev) => ({ ...prev, phone: event.target.value }))} />
              </label>
              <label className="field-stack">
                <span>Localisation</span>
                <input value={profile.location} onChange={(event) => setProfile((prev) => ({ ...prev, location: event.target.value }))} />
              </label>
              <label className="field-stack">
                <span>Website</span>
                <input value={profile.website} onChange={(event) => setProfile((prev) => ({ ...prev, website: event.target.value }))} />
              </label>
              <label className="field-stack">
                <span>LinkedIn</span>
                <input value={profile.linkedin} onChange={(event) => setProfile((prev) => ({ ...prev, linkedin: event.target.value }))} />
              </label>
              <label className="field-stack">
                <span>GitHub</span>
                <input value={profile.github} onChange={(event) => setProfile((prev) => ({ ...prev, github: event.target.value }))} />
              </label>
            </div>

            <label className="field-stack">
              <span>Resume factuel</span>
              <textarea
                rows={4}
                value={profile.summary}
                onChange={(event) => setProfile((prev) => ({ ...prev, summary: event.target.value }))}
                placeholder="Resume sobre, sans invention, qui peut etre reoriente ensuite vers plusieurs postes."
              />
            </label>

            <div className="cv-tag-grid">
              <TagInput label="Competences principales" placeholder="SQL, Power BI, Python..." value={profile.skills} onChange={(skills) => setProfile((prev) => ({ ...prev, skills }))} />
              <TagInput label="Langues" placeholder="French native, English C1" value={profile.languages} onChange={(languages) => setProfile((prev) => ({ ...prev, languages }))} />
              <TagInput label="Certifications" placeholder="PL-300, Google Analytics..." value={profile.certifications} onChange={(certifications) => setProfile((prev) => ({ ...prev, certifications }))} />
            </div>

            <div className="cv-panel-actions">
              <button className="primary-button" type="button" onClick={saveProfile} disabled={savingProfile}>
                {savingProfile ? 'Sauvegarde...' : 'Sauvegarder le profil'}
              </button>
              {feedback ? <span className="panel-note">{feedback}</span> : null}
            </div>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 6 }}>
            <SectionHeader eyebrow="Contenu" title="Blocs du CV" note="Tu peux garder beaucoup d'entrees. Le moteur cible les plus pertinentes selon le poste." />
            <div className="cv-editor-stack">
              <ExperienceEditor items={profile.experience} onChange={(experience) => setProfile((prev) => ({ ...prev, experience }))} />
              <ProjectEditor items={profile.projects} onChange={(projects) => setProfile((prev) => ({ ...prev, projects }))} />
              <EducationEditor items={profile.education} onChange={(education) => setProfile((prev) => ({ ...prev, education }))} />
            </div>
          </section>
        </div>

        <aside className="cv-side-column">
          <section className="panel-shell fade-stagger" style={{ '--index': 7 }}>
            <SectionHeader eyebrow="Generation" title="Cibler une annonce" note="Tu peux partir d'une annonce selectionnee ou d'une candidature sauvegardee." />

            <label className="field-stack">
              <span>Template moderncv</span>
              <select value={templateSlug} onChange={(event) => setTemplateSlug(event.target.value)}>
                {templates.map((template) => (
                  <option key={template.slug} value={template.slug}>
                    {template.name}
                  </option>
                ))}
              </select>
            </label>

            <div className="cv-source-switch">
              <button
                className={`filter-chip ${sourceMode === 'selected-result' ? 'is-active' : ''}`}
                type="button"
                onClick={() => setSourceMode('selected-result')}
                disabled={!selectedResult}
              >
                <span>Annonce selectionnee</span>
              </button>
              <button
                className={`filter-chip ${sourceMode === 'application' ? 'is-active' : ''}`}
                type="button"
                onClick={() => setSourceMode('application')}
              >
                <span>Candidature sauvee</span>
              </button>
            </div>

            {sourceMode === 'selected-result' ? (
              <div className="cv-target-card">
                {selectedResult ? (
                  <>
                    <p className="eyebrow">{selectedResult.source || 'Annonce'}</p>
                    <h4>{selectedResult.job_title}</h4>
                    <p>{selectedResult.company_name || 'Entreprise non precisee'}</p>
                  </>
                ) : (
                  <p className="panel-note">Selectionne une annonce dans le workspace pour l'utiliser ici.</p>
                )}
              </div>
            ) : (
              <label className="field-stack">
                <span>Choisir une candidature</span>
                <select value={applicationId} onChange={(event) => setApplicationId(event.target.value)}>
                  <option value="">Selectionner</option>
                  {applications.map((application) => (
                    <option key={application.id} value={application.id}>
                      {application.job_title} - {application.company_name || 'Entreprise'}
                    </option>
                  ))}
                </select>
              </label>
            )}

            <button className="primary-button" type="button" onClick={generateDraft} disabled={generatingDraft}>
              {generatingDraft ? 'Generation...' : 'Generer un draft cible'}
            </button>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 8 }}>
            <SectionHeader eyebrow="Drafts" title="Versions generees" />
            <div className="cv-draft-stack">
              {drafts.length === 0 ? (
                <div className="cv-empty-slot">Aucun draft genere pour le moment.</div>
              ) : (
                drafts.map((draft) => (
                  <DraftCard key={draft.id} draft={draft} active={draft.id === selectedDraft?.id} onSelect={setSelectedDraftId} />
                ))
              )}
            </div>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 9 }}>
            <SectionHeader
              eyebrow="Preview"
              title={selectedDraft ? selectedDraft.target_title || 'Draft selectionne' : 'Aucun draft'}
              note={selectedDraft ? selectedDraft.target_company : 'Genere un draft pour afficher la selection ciblee.'}
            />

            {selectedDraft ? (
              <div className="cv-preview-stack">
                <div className="cv-draft-meta">
                  <span className="inline-badge">{selectedDraft.template_slug}</span>
                  <span className="inline-badge">{selectedDraft.source_kind}</span>
                  <span className="inline-badge">{selectedCounts.skills || 0} skills</span>
                </div>

                <div className="cv-match-grid">
                  <div className="cv-match-block">
                    <span>Termes couverts</span>
                    <strong>{(selectedPayload.match_summary?.covered_terms || []).slice(0, 8).join(', ') || 'A verifier'}</strong>
                  </div>
                  <div className="cv-match-block">
                    <span>Angles manquants</span>
                    <strong>{(selectedPayload.match_summary?.missing_terms || []).slice(0, 6).join(', ') || 'Aucun'}</strong>
                  </div>
                </div>

                <div className="cv-preview-list">
                  <div>
                    <p className="eyebrow">Experiences selectionnees</p>
                    <ul>
                      {(selectedPayload.experience || []).map((item) => (
                        <li key={item.id}>{item.title || item.company}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="eyebrow">Projets selectionnes</p>
                    <ul>
                      {(selectedPayload.projects || []).map((item) => (
                        <li key={item.id}>{item.name || item.role}</li>
                      ))}
                    </ul>
                  </div>
                </div>

                <div className="cv-panel-actions">
                  <button className="secondary-button" type="button" onClick={() => downloadDraft(selectedDraft)}>
                    Telecharger le .tex
                  </button>
                  <button className="secondary-button" type="button" onClick={() => enhanceDraft(selectedDraft)} disabled={enhancingDraft}>
                    {enhancingDraft ? 'Haiku travaille...' : 'Polir avec Haiku'}
                  </button>
                </div>

                {copySuggestions ? (
                  <div className="cv-ai-panel">
                    <p className="eyebrow">Suggestions Haiku</p>
                    {copySuggestions.headline ? (
                      <div className="cv-ai-block">
                        <span>Headline</span>
                        <strong>{copySuggestions.headline}</strong>
                      </div>
                    ) : null}
                    {copySuggestions.summary ? (
                      <div className="cv-ai-block">
                        <span>Summary</span>
                        <p>{copySuggestions.summary}</p>
                      </div>
                    ) : null}
                    {copySuggestions.skills_priority?.length ? (
                      <div className="cv-ai-block">
                        <span>Skills a pousser</span>
                        <div className="cv-draft-meta">
                          {copySuggestions.skills_priority.map((skill) => (
                            <span key={skill} className="inline-badge">{skill}</span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {copySuggestions.experience_rewrites?.length ? (
                      <div className="cv-ai-block">
                        <span>Bullets experience</span>
                        {copySuggestions.experience_rewrites.map((item) => (
                          <div key={item.id} className="cv-ai-list">
                            <strong>{(selectedPayload.experience || []).find((entry) => entry.id === item.id)?.title || item.id}</strong>
                            <ul>
                              {item.bullets.map((bullet) => (
                                <li key={bullet}>{bullet}</li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {copySuggestions.project_rewrites?.length ? (
                      <div className="cv-ai-block">
                        <span>Bullets projets</span>
                        {copySuggestions.project_rewrites.map((item) => (
                          <div key={item.id} className="cv-ai-list">
                            <strong>{(selectedPayload.projects || []).find((entry) => entry.id === item.id)?.name || item.id}</strong>
                            <ul>
                              {item.bullets.map((bullet) => (
                                <li key={bullet}>{bullet}</li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {copySuggestions.compliance_notes?.length ? (
                      <div className="cv-ai-block">
                        <span>Notes de conformite</span>
                        <ul>
                          {copySuggestions.compliance_notes.map((note) => (
                            <li key={note}>{note}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </div>
                ) : null}

                <label className="field-stack">
                  <span>Source strict moderncv</span>
                  <textarea rows={16} readOnly value={selectedDraft.latex_source} className="cv-code-preview" />
                </label>
              </div>
            ) : (
              <div className="cv-empty-slot">Le preview apparaitra ici apres generation.</div>
            )}
          </section>
        </aside>
      </section>
    </main>
  )
}
