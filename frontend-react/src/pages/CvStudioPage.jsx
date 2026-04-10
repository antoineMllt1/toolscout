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
  target_roles: [],
  cv_text: '',
  portfolio_url: '',
  portfolio_snapshot: {},
  portfolio_last_scraped_at: '',
  candidate_brief: {
    summary: '',
    focus_areas: [],
    strengths: [],
    project_highlights: [],
    source_health: {},
  },
  student_guidance: {
    role_tracks: [],
    story_starters: [],
    project_ideas: [],
  },
  interview_prep: {
    practice_plan: [],
    motivation_questions: [],
    behavioural_questions: [],
    role_question_sets: [],
  },
  application_plan: {
    readiness_score: 0,
    checklist: [],
    priority_actions: [],
    next_week_plan: [],
  },
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

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

function downloadBase64Pdf(base64Value, filename) {
  const binary = window.atob(base64Value)
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0))
  downloadBlob(new Blob([bytes], { type: 'application/pdf' }), filename)
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

function InsightMetric({ label, value, tone = '' }) {
  return (
    <article className={`summary-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  )
}

function StoryStarterCard({ item }) {
  return (
    <article className="coach-card">
      <p className="eyebrow">Story starter</p>
      <h3>{item.title}</h3>
      <p>{item.when_to_use}</p>
      <div className="coach-block">
        <span>Prompt</span>
        <p>{item.prompt}</p>
      </div>
      {item.focus_points?.length ? (
        <div className="coach-chip-row">
          {item.focus_points.map((point) => (
            <span key={point} className="inline-badge">
              {point}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  )
}

function ProjectIdeaCard({ item }) {
  return (
    <article className="coach-card">
      <p className="eyebrow">{item.track}</p>
      <h3>{item.title}</h3>
      <p>{item.brief}</p>
      <div className="coach-block">
        <span>Pourquoi ce projet aide</span>
        <p>{item.why_it_helps}</p>
      </div>
      <div className="coach-chip-row">
        {(item.stack || []).map((tech) => (
          <span key={tech} className="inline-badge">
            {tech}
          </span>
        ))}
      </div>
    </article>
  )
}

function InterviewQuestionCard({ item }) {
  return (
    <article className="coach-card">
      <p className="eyebrow">{item.category}</p>
      <h3>{item.question}</h3>
      <div className="coach-block">
        <span>Pourquoi on te la pose</span>
        <p>{item.why_asked}</p>
      </div>
      <div className="coach-block">
        <span>Structure de reponse</span>
        <p>{item.answer_shape}</p>
      </div>
      {(item.evidence_refs || []).length ? (
        <div className="coach-chip-row">
          {item.evidence_refs.map((ref) => (
            <span key={ref} className="inline-badge">
              {ref}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  )
}

function ChecklistRow({ item }) {
  return (
    <div className={`checklist-row ${item.done ? 'is-done' : ''}`}>
      <div className="checklist-mark">{item.done ? 'OK' : 'TODO'}</div>
      <div className="checklist-copy">
        <strong>{item.label}</strong>
        <p>{item.detail}</p>
      </div>
    </div>
  )
}

function PortfolioProjectCard({ project }) {
  return (
    <article className="portfolio-project-card">
      <div className="portfolio-project-head">
        <div>
          <h3>{project.name}</h3>
          <p>{project.summary || 'Projet importe depuis le portfolio.'}</p>
        </div>
        {project.url ? (
          <a className="text-action" href={project.url} target="_blank" rel="noreferrer">
            Ouvrir
          </a>
        ) : null}
      </div>
      {(project.technologies || []).length ? (
        <div className="coach-chip-row">
          {project.technologies.map((tech) => (
            <span key={tech} className="inline-badge">
              {tech}
            </span>
          ))}
        </div>
      ) : null}
    </article>
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
          <h3>Experiences</h3>
        </div>
        <button className="secondary-button" type="button" onClick={() => onChange([...items, createExperience()])}>
          Ajouter
        </button>
      </div>

      {items.length === 0 ? <div className="cv-empty-slot">Ajoute au moins une experience concrete.</div> : null}

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
                <span>Prioritaire</span>
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
              <span>Structure</span>
              <input value={item.company} onChange={(event) => updateItem(item.id, { company: event.target.value })} />
            </label>
            <label className="field-stack">
              <span>Lieu</span>
              <input value={item.location} onChange={(event) => updateItem(item.id, { location: event.target.value })} />
            </label>
            <label className="field-stack">
              <span>Dates</span>
              <div className="cv-date-row">
                <input value={item.start_date} onChange={(event) => updateItem(item.id, { start_date: event.target.value })} placeholder="2024" />
                <input value={item.end_date} onChange={(event) => updateItem(item.id, { end_date: event.target.value })} placeholder="Present" />
              </div>
            </label>
          </div>

          <label className="field-stack">
            <span>Resume factuel</span>
            <textarea
              rows={3}
              value={item.summary}
              onChange={(event) => updateItem(item.id, { summary: event.target.value })}
              placeholder="Contexte, scope, ce que tu as gere toi-meme."
            />
          </label>

          <div className="cv-entry-grid">
            <label className="field-stack">
              <span>Faits ou impacts</span>
              <textarea
                rows={4}
                value={arrayToLines(item.highlights)}
                onChange={(event) => updateItem(item.id, { highlights: linesToArray(event.target.value) })}
                placeholder={'Une ligne = un point utile en entretien\nEx: Automatise un reporting hebdomadaire'}
              />
            </label>
            <label className="field-stack">
              <span>Competences mobilisees</span>
              <textarea
                rows={4}
                value={arrayToLines(item.skills)}
                onChange={(event) => updateItem(item.id, { skills: linesToArray(event.target.value) })}
                placeholder={'SQL\nPower BI\nCoordination'}
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

      {items.length === 0 ? <div className="cv-empty-slot">Le portfolio importe des projets, mais tu peux aussi en saisir a la main.</div> : null}

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
                <span>Prioritaire</span>
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
            <span>Resume</span>
            <textarea
              rows={3}
              value={item.summary}
              onChange={(event) => updateItem(item.id, { summary: event.target.value })}
              placeholder="Probleme, approche, resultat ou apprentissage."
            />
          </label>

          <div className="cv-entry-grid">
            <label className="field-stack">
              <span>Faits ou livrables</span>
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

      {items.length === 0 ? <div className="cv-empty-slot">Ajoute ta formation pour donner du contexte au recruteur.</div> : null}

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
                <span>Prioritaire</span>
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
                <input value={item.start_date} onChange={(event) => updateItem(item.id, { start_date: event.target.value })} placeholder="2022" />
                <input value={item.end_date} onChange={(event) => updateItem(item.id, { end_date: event.target.value })} placeholder="2026" />
              </div>
            </label>
          </div>

          <label className="field-stack">
            <span>Resume</span>
            <textarea rows={3} value={item.summary} onChange={(event) => updateItem(item.id, { summary: event.target.value })} />
          </label>

          <div className="cv-entry-grid">
            <label className="field-stack">
              <span>Faits utiles</span>
              <textarea rows={4} value={arrayToLines(item.highlights)} onChange={(event) => updateItem(item.id, { highlights: linesToArray(event.target.value) })} />
            </label>
            <label className="field-stack">
              <span>Competences</span>
              <textarea rows={4} value={arrayToLines(item.skills)} onChange={(event) => updateItem(item.id, { skills: linesToArray(event.target.value) })} />
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
  const [uploadingCv, setUploadingCv] = useState(false)
  const [importingPortfolio, setImportingPortfolio] = useState(false)
  const [generatingDraft, setGeneratingDraft] = useState(false)
  const [enhancingDraft, setEnhancingDraft] = useState(false)
  const [generatingLetter, setGeneratingLetter] = useState(false)
  const [coverLettersByDraft, setCoverLettersByDraft] = useState({})
  const [feedback, setFeedback] = useState('')
  const [feedbackTone, setFeedbackTone] = useState('info')

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
    setProfile({ ...EMPTY_PROFILE, ...(await response.json()) })
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
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || 'Impossible de sauvegarder le profil')
      }
      setProfile({ ...EMPTY_PROFILE, ...data })
      setFeedbackTone('info')
      setFeedback('Profil candidat sauvegarde.')
    } catch (error) {
      setFeedbackTone('danger')
      setFeedback(error.message)
    } finally {
      setSavingProfile(false)
    }
  }

  async function uploadCvFile(event) {
    const selectedFile = event.target.files?.[0]
    if (!selectedFile) return

    setUploadingCv(true)
    setFeedback('')
    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      const response = await authFetch('/api/cv/upload', {
        method: 'POST',
        body: formData,
      })
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.detail || 'Impossible d importer le CV')
      }
      setProfile({ ...EMPTY_PROFILE, ...(payload.profile || {}) })
      setFeedbackTone('info')
      setFeedback(
        `CV importe. ${payload.imported?.experience_found || 0} experience(s), ${payload.imported?.education_found || 0} formation(s), ${payload.imported?.projects_found || 0} projet(s).`,
      )
    } catch (error) {
      setFeedbackTone('danger')
      setFeedback(error.message)
    } finally {
      event.target.value = ''
      setUploadingCv(false)
    }
  }

  async function importPortfolio() {
    if (!profile.portfolio_url.trim()) {
      setFeedbackTone('danger')
      setFeedback('Ajoute une URL de portfolio avant de lancer le scraping.')
      return
    }

    setImportingPortfolio(true)
    setFeedback('')
    try {
      const response = await authFetch('/api/cv/portfolio/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ portfolio_url: profile.portfolio_url }),
      })
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.detail || 'Impossible de scraper le portfolio')
      }
      setProfile({ ...EMPTY_PROFILE, ...(payload.profile || {}) })
      setFeedbackTone('info')
      setFeedback(`Portfolio importe. ${payload.imported?.projects_found || 0} projet(s) detecte(s).`)
    } catch (error) {
      setFeedbackTone('danger')
      setFeedback(error.message)
    } finally {
      setImportingPortfolio(false)
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
        throw new Error('Choisis une annonce ou une candidature pour generer le draft.')
      }

      const response = await authFetch('/api/cv/drafts/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const draft = await response.json()
      if (!response.ok) {
        throw new Error(draft.detail || 'Impossible de generer le draft')
      }
      setDrafts((prev) => [draft, ...prev.filter((item) => item.id !== draft.id)])
      setSelectedDraftId(draft.id)
      setFeedbackTone('info')
      setFeedback('Draft cible genere.')
    } catch (error) {
      setFeedbackTone('danger')
      setFeedback(error.message)
    } finally {
      setGeneratingDraft(false)
    }
  }

  async function downloadDraft(draft) {
    setFeedback('')
    try {
      const copySuggestions = copySuggestionsByDraft[draft.id]
      const response = await authFetch(`/api/cv/drafts/${draft.id}/pdf`, {
        method: 'POST',
        headers: copySuggestions ? { 'Content-Type': 'application/json' } : undefined,
        body: copySuggestions ? JSON.stringify({ copy_suggestions: copySuggestions }) : undefined,
      })
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}))
        throw new Error(payload.detail || 'Impossible de telecharger le PDF')
      }
      const blob = await response.blob()
      downloadBlob(blob, `toolscout-cv-${draft.id}.pdf`)
    } catch (error) {
      setFeedbackTone('danger')
      setFeedback(error.message)
    }
  }

  async function enhanceDraft(draft) {
    setEnhancingDraft(true)
    setFeedback('')
    try {
      const response = await authFetch(`/api/cv/drafts/${draft.id}/copywrite`, { method: 'POST' })
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.detail || 'Impossible de polir le draft')
      }
      setCopySuggestionsByDraft((prev) => ({ ...prev, [draft.id]: payload.suggestions }))
      setFeedbackTone('info')
      setFeedback('Suggestions de copywriting recues.')
    } catch (error) {
      setFeedbackTone('danger')
      setFeedback(error.message)
    } finally {
      setEnhancingDraft(false)
    }
  }

  async function generateCoverLetter(draft) {
    setGeneratingLetter(true)
    setFeedback('')
    try {
      const response = await authFetch('/api/cv/cover-letter/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ draft_id: draft.id }),
      })
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.detail || 'Impossible de generer la lettre')
      }
      setCoverLettersByDraft((prev) => ({ ...prev, [draft.id]: payload }))
      setFeedbackTone('info')
      setFeedback('Lettre de motivation generee.')
    } catch (error) {
      setFeedbackTone('danger')
      setFeedback(error.message)
    } finally {
      setGeneratingLetter(false)
    }
  }

  function downloadCoverLetter(letter) {
    if (!letter?.pdf_base64) return
    downloadBase64Pdf(letter.pdf_base64, letter.file_name || 'toolscout-cover-letter.pdf')
  }

  if (!user) {
    return (
      <main className="cv-page">
        <section className="empty-panel">
          <p className="eyebrow">Compte requis</p>
          <h3>Connecte-toi pour construire ton profil, importer ton portfolio et preparer tes candidatures.</h3>
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
  const coverLetter = selectedDraft ? coverLettersByDraft[selectedDraft.id] : null
  const candidateBrief = profile.candidate_brief || EMPTY_PROFILE.candidate_brief
  const studentGuidance = profile.student_guidance || EMPTY_PROFILE.student_guidance
  const interviewPrep = profile.interview_prep || EMPTY_PROFILE.interview_prep
  const applicationPlan = profile.application_plan || EMPTY_PROFILE.application_plan
  const portfolioSnapshot = profile.portfolio_snapshot || {}
  const sourceHealth = candidateBrief.source_health || {}

  return (
    <main className="cv-page">
      <section className="cv-hero-grid">
        <article className="hero-slab dark fade-stagger" style={{ '--index': 0 }}>
          <div className="hero-copy">
            <p className="eyebrow is-light">Candidate profile</p>
            <h1 className="dashboard-display">Ton CV general, ton portfolio et tes preuves de stage au meme endroit.</h1>
            <p className="lede is-light">
              Le but n&apos;est pas seulement de remplir un CV. Cette page sert a comprendre ton profil,
              recuperer les bons projets depuis ton portfolio, puis transformer tout ca en candidatures plus solides.
            </p>
          </div>

          <div className="hero-action-row">
            <button className="primary-button light" onClick={() => onNavigate('search')}>
              Retour aux annonces
            </button>
            <button className="secondary-button dark" onClick={() => onNavigate('dashboard')}>
              Ouvrir le cockpit
            </button>
          </div>

          <div className="hero-stat-strip">
            <div className="hero-stat-chip">
              <span>CV master</span>
              <strong>{sourceHealth.has_cv_text ? 'Oui' : 'A faire'}</strong>
            </div>
            <div className="hero-stat-chip">
              <span>Portfolio</span>
              <strong>{sourceHealth.has_portfolio ? 'Connecte' : 'A relier'}</strong>
            </div>
            <div className="hero-stat-chip">
              <span>Projets</span>
              <strong>{profile.projects.length}</strong>
            </div>
          </div>
        </article>

        <aside className="hero-rail">
          <article className="rail-panel fade-stagger" style={{ '--index': 1 }}>
            <p className="eyebrow">Lecture rapide</p>
            <h2>{portfolioSnapshot.page_title || 'Aucun portfolio scrape pour le moment'}</h2>
            <p>
              {portfolioSnapshot.domain
                ? `${portfolioSnapshot.domain} - dernier import ${formatDate(profile.portfolio_last_scraped_at)}`
                : 'Ajoute ton portfolio pour recuperer des projets et des signaux utiles.'}
            </p>
            {portfolioSnapshot.final_url ? (
              <a className="text-action" href={portfolioSnapshot.final_url} target="_blank" rel="noreferrer">
                Ouvrir le portfolio
              </a>
            ) : null}
          </article>

          <div className="dashboard-summary-grid">
            <InsightMetric label="Roles cibles" value={profile.target_roles.length} tone="tone-blue" />
            <InsightMetric label="Readiness" value={`${applicationPlan.readiness_score || 0}%`} tone="tone-green" />
            <InsightMetric label="Drafts" value={drafts.length} tone="tone-yellow" />
          </div>
        </aside>
      </section>

      <section className="cv-layout">
        <div className="cv-main-column">
          <section className="panel-shell fade-stagger" style={{ '--index': 2 }}>
            <SectionHeader
              eyebrow="Source of truth"
              title="CV general et portfolio"
              note="Pense comme un etudiant: un CV master brut + un portfolio vivant = la meilleure base pour toutes les candidatures."
            />

            <div className="source-truth-grid">
              <label className="field-stack cv-raw-source">
                <span>CV general brut</span>
                <textarea
                  className="cv-raw-editor"
                  rows={16}
                  value={profile.cv_text}
                  onChange={(event) => setProfile((prev) => ({ ...prev, cv_text: event.target.value }))}
                  placeholder="Colle ici ton CV complet en texte brut ou markdown. Le systeme s'en sert comme source de contexte, meme si tu structures aussi les sections plus bas."
                />
              </label>

              <div className="source-truth-side">
                <label className="field-stack">
                  <span>URL de portfolio</span>
                  <input
                    value={profile.portfolio_url}
                    onChange={(event) => setProfile((prev) => ({ ...prev, portfolio_url: event.target.value }))}
                    placeholder="https://ton-portfolio.dev"
                  />
                </label>

                <label className="field-stack">
                  <span>Importer un CV existant</span>
                  <input
                    type="file"
                    accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
                    onChange={uploadCvFile}
                    disabled={uploadingCv}
                  />
                </label>

                <div className="cv-panel-actions">
                  <button className="primary-button" type="button" onClick={saveProfile} disabled={savingProfile}>
                    {savingProfile ? 'Sauvegarde...' : 'Sauvegarder'}
                  </button>
                  <button className="secondary-button" type="button" onClick={importPortfolio} disabled={importingPortfolio}>
                    {importingPortfolio ? 'Scraping...' : 'Scraper le portfolio'}
                  </button>
                </div>

                {feedback ? <div className={`feedback-box ${feedbackTone === 'danger' ? 'danger' : 'info'}`}>{feedback}</div> : null}

                <div className="portfolio-summary-card">
                  <div className="portfolio-summary-head">
                    <div>
                      <p className="eyebrow">Portfolio sync</p>
                      <h3>{portfolioSnapshot.domain || 'Pas encore synchronise'}</h3>
                    </div>
                    {portfolioSnapshot.links?.github ? (
                      <a className="text-action" href={portfolioSnapshot.links.github} target="_blank" rel="noreferrer">
                        GitHub
                      </a>
                    ) : null}
                  </div>
                  <p>{portfolioSnapshot.narrative || 'Le scrape va detecter les pages, projets, technos et liens visibles sur ton portfolio.'}</p>
                  <div className="coach-chip-row">
                    <span className="inline-badge">{portfolioSnapshot.projects?.length || 0} projet(s)</span>
                    <span className="inline-badge">{portfolioSnapshot.skills?.length || 0} skill(s)</span>
                    <span className="inline-badge">Mis a jour {formatDate(profile.portfolio_last_scraped_at)}</span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 3 }}>
            <SectionHeader
              eyebrow="Positioning"
              title="Identite et roles cibles"
              note="Ces champs servent a orienter le profil, les entrainements et les idees de projets a construire."
            />

            <div className="cv-entry-grid cv-basics-grid">
              <label className="field-stack">
                <span>Nom complet</span>
                <input value={profile.full_name} onChange={(event) => setProfile((prev) => ({ ...prev, full_name: event.target.value }))} />
              </label>
              <label className="field-stack">
                <span>Headline</span>
                <input value={profile.headline} onChange={(event) => setProfile((prev) => ({ ...prev, headline: event.target.value }))} placeholder="Data intern | Automation | Analytics" />
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
                placeholder="Resume sobre: ce que tu sais faire, le type d'environnement que tu vises et les sujets sur lesquels tu veux etre credible."
              />
            </label>

            <div className="cv-tag-grid">
              <TagInput label="Roles cibles" placeholder="Data analyst intern, Product ops intern..." value={profile.target_roles} onChange={(target_roles) => setProfile((prev) => ({ ...prev, target_roles }))} />
              <TagInput label="Competences principales" placeholder="SQL, Power BI, Python..." value={profile.skills} onChange={(skills) => setProfile((prev) => ({ ...prev, skills }))} />
              <TagInput label="Langues" placeholder="French native, English C1" value={profile.languages} onChange={(languages) => setProfile((prev) => ({ ...prev, languages }))} />
              <TagInput label="Certifications" placeholder="PL-300, Google Analytics..." value={profile.certifications} onChange={(certifications) => setProfile((prev) => ({ ...prev, certifications }))} />
            </div>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 4 }}>
            <SectionHeader
              eyebrow="Candidate signal"
              title="Synthese automatique de ton profil"
              note="Cette couche sert a mieux lire ton profil avant de personnaliser les candidatures."
            />

            <div className="candidate-brief-grid">
              <article className="candidate-brief-card">
                <p className="eyebrow">Synthese</p>
                <h3>Lecture recruiter</h3>
                <p>{candidateBrief.summary || 'Sauvegarde ton profil et relie ton portfolio pour generer une synthese.'}</p>
              </article>

              <article className="candidate-brief-card">
                <p className="eyebrow">Focus</p>
                <h3>Axes dominants</h3>
                {(candidateBrief.focus_areas || []).length ? (
                  <div className="coach-chip-row">
                    {candidateBrief.focus_areas.map((area) => (
                      <span key={area} className="inline-badge">
                        {area}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p>Ajoute tes competences et projets pour faire emerger les bons axes.</p>
                )}
              </article>

              <article className="candidate-brief-card">
                <p className="eyebrow">Strengths</p>
                <h3>Ce que le systeme voit</h3>
                {(candidateBrief.strengths || []).length ? (
                  <ul className="signal-list">
                    {candidateBrief.strengths.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p>Les points forts apparaitront ici apres sauvegarde du profil.</p>
                )}
              </article>
            </div>

            {(candidateBrief.project_highlights || []).length ? (
              <div className="portfolio-project-grid">
                {candidateBrief.project_highlights.map((project) => (
                  <PortfolioProjectCard key={project.name} project={project} />
                ))}
              </div>
            ) : null}
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 5 }}>
            <SectionHeader
              eyebrow="Apply ready"
              title="Checklist de readiness"
              note="Une vue simple pour savoir si ton dossier est deja presentable ou s'il manque encore des pieces importantes."
            />

            <div className="readiness-hero">
              <div className="readiness-score-ring">
                <strong>{applicationPlan.readiness_score || 0}%</strong>
                <span>pret a candidater</span>
              </div>

              <div className="readiness-copy">
                <h3>Priorites immediates</h3>
                <ul className="signal-list">
                  {(applicationPlan.priority_actions || []).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="checklist-stack">
              {(applicationPlan.checklist || []).map((item) => (
                <ChecklistRow key={item.label} item={item} />
              ))}
            </div>

            <div className="candidate-brief-grid compact">
              <article className="candidate-brief-card">
                <p className="eyebrow">Cette semaine</p>
                <h3>Plan simple</h3>
                <ul className="signal-list">
                  {(applicationPlan.next_week_plan || []).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
            </div>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 6 }}>
            <SectionHeader
              eyebrow="Evidence bank"
              title="Experiences, projets et formation"
              note="C'est la matiere premiere des story starters, du CV cible et de tes futures candidatures."
            />

            <div className="cv-editor-stack">
              <ExperienceEditor items={profile.experience} onChange={(experience) => setProfile((prev) => ({ ...prev, experience }))} />
              <ProjectEditor items={profile.projects} onChange={(projects) => setProfile((prev) => ({ ...prev, projects }))} />
              <EducationEditor items={profile.education} onChange={(education) => setProfile((prev) => ({ ...prev, education }))} />
            </div>

            <div className="cv-panel-actions">
              <button className="primary-button" type="button" onClick={saveProfile} disabled={savingProfile}>
                {savingProfile ? 'Sauvegarde...' : 'Sauvegarder ma base candidat'}
              </button>
            </div>
          </section>
        </div>

        <aside className="cv-side-column">
          <section className="panel-shell fade-stagger" style={{ '--index': 7 }}>
            <SectionHeader
              eyebrow="Training"
              title="Story starters pour l'entretien"
              note="Pas des reponses toutes faites. Des points de depart a retravailler en STAR."
            />

            <div className="coach-stack">
              {(studentGuidance.story_starters || []).length ? (
                studentGuidance.story_starters.map((item) => <StoryStarterCard key={`${item.title}-${item.prompt}`} item={item} />)
              ) : (
                <div className="cv-empty-slot">Ajoute des experiences ou projets pour generer des story starters.</div>
              )}
            </div>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 8 }}>
            <SectionHeader
              eyebrow="Interview drills"
              title="Questions a bosser"
              note="Des questions probables, reliees a tes roles cibles et a ce que ton profil montre deja."
            />

            <div className="coach-stack">
              {(interviewPrep.practice_plan || []).length ? (
                <article className="candidate-brief-card">
                  <p className="eyebrow">Plan d'entrainement</p>
                  <h3>Avant de candidater</h3>
                  <ul className="signal-list">
                    {interviewPrep.practice_plan.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </article>
              ) : null}

              {(interviewPrep.motivation_questions || []).map((item) => (
                <InterviewQuestionCard key={item.question} item={item} />
              ))}
              {(interviewPrep.behavioural_questions || []).map((item) => (
                <InterviewQuestionCard key={item.question} item={item} />
              ))}
              {(interviewPrep.role_question_sets || []).flatMap((group) =>
                (group.questions || []).map((item) => (
                  <InterviewQuestionCard key={`${group.track}-${item.question}`} item={{ ...item, category: group.track }} />
                )),
              )}
            </div>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 9 }}>
            <SectionHeader
              eyebrow="Build next"
              title="Idees de projets a lancer"
              note="Inspire de career-ops, mais pense pour un etudiant: des projets faisables qui renforcent un dossier de stage."
            />

            <div className="coach-stack">
              {(studentGuidance.project_ideas || []).length ? (
                studentGuidance.project_ideas.map((item) => <ProjectIdeaCard key={`${item.track}-${item.title}`} item={item} />)
              ) : (
                <div className="cv-empty-slot">Definis des roles cibles pour faire remonter des idees plus pertinentes.</div>
              )}
            </div>
          </section>

          <section className="panel-shell fade-stagger" style={{ '--index': 10 }}>
            <SectionHeader
              eyebrow="Generation"
              title="Generer un CV cible"
              note="Tu peux partir d'une annonce selectionnee ou d'une candidature sauvegardee."
            />

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

          <section className="panel-shell fade-stagger" style={{ '--index': 11 }}>
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

          <section className="panel-shell fade-stagger" style={{ '--index': 12 }}>
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
                    Telecharger le PDF
                  </button>
                  <button className="secondary-button" type="button" onClick={() => enhanceDraft(selectedDraft)} disabled={enhancingDraft}>
                    {enhancingDraft ? 'Analyse...' : 'Polir avec l IA'}
                  </button>
                  <button className="secondary-button" type="button" onClick={() => generateCoverLetter(selectedDraft)} disabled={generatingLetter}>
                    {generatingLetter ? 'Generation...' : 'Generer la lettre'}
                  </button>
                  {coverLetter?.pdf_base64 ? (
                    <button className="secondary-button" type="button" onClick={() => downloadCoverLetter(coverLetter)}>
                      Lettre PDF
                    </button>
                  ) : null}
                </div>

                {copySuggestions ? (
                  <div className="cv-ai-panel">
                    <p className="eyebrow">Suggestions de copywriting</p>
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
                            <span key={skill} className="inline-badge">
                              {skill}
                            </span>
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
                        <span>Notes</span>
                        <ul>
                          {copySuggestions.compliance_notes.map((note) => (
                            <li key={note}>{note}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </div>
                ) : null}

                {coverLetter ? (
                  <div className="cv-ai-panel">
                    <p className="eyebrow">Lettre de motivation</p>
                    {coverLetter.subject ? (
                      <div className="cv-ai-block">
                        <span>Objet</span>
                        <strong>{coverLetter.subject}</strong>
                      </div>
                    ) : null}
                    <div className="cv-ai-block">
                      <span>Texte</span>
                      <textarea rows={14} readOnly value={coverLetter.letter_text} className="cv-code-preview" />
                    </div>
                    {coverLetter.compliance_notes?.length ? (
                      <div className="cv-ai-block">
                        <span>Notes</span>
                        <ul>
                          {coverLetter.compliance_notes.map((note) => (
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
