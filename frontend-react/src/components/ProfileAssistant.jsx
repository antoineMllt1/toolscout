import { useEffect, useMemo, useState } from 'react'

function makeId(prefix) {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}-${crypto.randomUUID()}`
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function createExperience() {
  return {
    id: makeId('exp'),
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
    id: makeId('proj'),
    name: '',
    role: '',
    url: '',
    summary: '',
    highlights: [],
    technologies: [],
    featured: false,
  }
}

function createEducation() {
  return {
    id: makeId('edu'),
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

function splitList(value) {
  return (value || '')
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean)
}

const TRACKS = {
  basics: {
    label: 'Base',
    title: 'Identite et cap',
    intro: 'Pose les informations minimales pour rendre ton profil exploitable tout de suite.',
    steps: [
      { id: 'full_name', prompt: 'Nom a afficher sur le CV', placeholder: 'Ex: Antoine Millot', hint: 'Utilise le meme format que sur LinkedIn et ton portfolio.' },
      { id: 'headline', prompt: 'Headline en une ligne', placeholder: 'Ex: Data intern | SQL | Power BI | Automation', hint: 'Une phrase courte, pas un paragraphe.' },
      { id: 'target_roles', prompt: 'Roles cibles', placeholder: 'Ex: Data analyst intern, Product ops intern', hint: 'Separe par virgules.', multiline: true },
      { id: 'skills', prompt: 'Competences principales', placeholder: 'Ex: SQL, Power BI, Python, Excel', hint: 'Garde seulement les competences que tu peux vraiment defendre.', multiline: true },
      { id: 'summary', prompt: 'Resume factuel', placeholder: "Ex: J'aide a transformer des donnees en decisions claires...", hint: '3 a 5 phrases simples sur ton profil et le type de poste vise.', multiline: true },
    ],
  },
  experience: {
    label: 'Experience',
    title: 'Une experience solide',
    intro: 'Meme un stage, une asso, un freelance ou une mission serieuse peuvent devenir une vraie ligne CV.',
    steps: [
      { id: 'company', prompt: 'Structure ou entreprise', placeholder: 'Ex: BIPP Consulting' },
      { id: 'title', prompt: 'Role / poste', placeholder: 'Ex: Consultant BI junior' },
      { id: 'location', prompt: 'Lieu', placeholder: 'Ex: Lyon' },
      { id: 'summary', prompt: 'Contexte et responsabilites', placeholder: "Ex: J'intervenais sur des sujets de reporting et de visualisation...", multiline: true },
      { id: 'highlights', prompt: 'Actions ou resultats concrets', placeholder: 'Ex: creation de dashboards, automatisation de reporting', hint: 'Une idee par ligne ou separe par virgules.', multiline: true },
      { id: 'skills', prompt: 'Competences utilisees', placeholder: 'Ex: Power BI, SQL, analyse, coordination', multiline: true },
    ],
  },
  project: {
    label: 'Projet',
    title: 'Un projet qui compte',
    intro: 'Le but est de transformer un projet en signal fort, pas juste de stocker un titre.',
    steps: [
      { id: 'name', prompt: 'Nom du projet', placeholder: 'Ex: Sales Analytics Dashboard' },
      { id: 'role', prompt: 'Ton role', placeholder: 'Ex: Concepteur et developpeur' },
      { id: 'summary', prompt: 'Probleme resolu', placeholder: 'Ex: Centraliser les KPI commerciaux et automatiser le suivi...', multiline: true },
      { id: 'highlights', prompt: 'Livrables ou resultats', placeholder: 'Ex: dashboard interactif, auth, export PDF, visualisations', multiline: true },
      { id: 'technologies', prompt: 'Technos utilisees', placeholder: 'Ex: React, FastAPI, PostgreSQL, Docker', multiline: true },
    ],
  },
  education: {
    label: 'Formation',
    title: 'Formation utile',
    intro: 'Ajoute seulement les elements qui renforcent vraiment ton dossier.',
    steps: [
      { id: 'school', prompt: 'Ecole ou universite', placeholder: 'Ex: ESILV' },
      { id: 'degree', prompt: 'Diplome prepare', placeholder: 'Ex: Master Data & IA' },
      { id: 'field', prompt: 'Specialisation', placeholder: 'Ex: Data science, business intelligence' },
      { id: 'summary', prompt: 'Ce qui est utile a montrer', placeholder: 'Ex: projets appliques, analytics, automatisation...', multiline: true },
    ],
  },
}

function recommendedTrack(profile) {
  if (!profile.full_name || !profile.headline || !(profile.target_roles || []).length) return 'basics'
  if (!(profile.experience || []).length) return 'experience'
  if (!(profile.projects || []).length) return 'project'
  if (!(profile.education || []).length) return 'education'
  return 'experience'
}

function ensureItem(collection, factory) {
  return collection.length ? [...collection] : [factory()]
}

function applyAnswer(track, stepId, answer, profile) {
  const value = (answer || '').trim()
  if (!value) return profile

  if (track === 'basics') {
    if (stepId === 'target_roles' || stepId === 'skills') {
      return { ...profile, [stepId]: splitList(value) }
    }
    return { ...profile, [stepId]: value }
  }

  if (track === 'experience') {
    const items = ensureItem(profile.experience || [], createExperience)
    const current = { ...items[0] }
    current[stepId] = stepId === 'highlights' || stepId === 'skills' ? splitList(value) : value
    items[0] = current
    return { ...profile, experience: items }
  }

  if (track === 'project') {
    const items = ensureItem(profile.projects || [], createProject)
    const current = { ...items[0] }
    current[stepId] = stepId === 'highlights' || stepId === 'technologies' ? splitList(value) : value
    items[0] = current
    return { ...profile, projects: items }
  }

  if (track === 'education') {
    const items = ensureItem(profile.education || [], createEducation)
    const current = { ...items[0], [stepId]: value }
    items[0] = current
    return { ...profile, education: items }
  }

  return profile
}

function extractPreview(profile, track) {
  if (track === 'basics') {
    return [
      profile.full_name || 'Nom non renseigne',
      profile.headline || 'Headline non renseigne',
      (profile.target_roles || []).slice(0, 3).join(', ') || 'Roles cibles non renseignes',
    ]
  }

  if (track === 'experience') {
    const item = profile.experience?.[0]
    return item
      ? [item.company || 'Entreprise', item.title || 'Role', (item.highlights || []).slice(0, 2).join(' • ') || 'Actions non renseignees']
      : ['Aucune experience capturee pour le moment']
  }

  if (track === 'project') {
    const item = profile.projects?.[0]
    return item
      ? [item.name || 'Projet', item.role || 'Role', (item.technologies || []).slice(0, 3).join(', ') || 'Technos non renseignees']
      : ['Aucun projet capture pour le moment']
  }

  const item = profile.education?.[0]
  return item
    ? [item.school || 'Ecole', item.degree || 'Diplome', item.field || 'Specialisation']
    : ['Aucune formation capturee pour le moment']
}

export default function ProfileAssistant({ profile, setProfile, onSave, saving }) {
  const [track, setTrack] = useState(() => recommendedTrack(profile))
  const [stepIndex, setStepIndex] = useState(0)
  const [draft, setDraft] = useState('')

  const activeTrack = TRACKS[track]
  const activeStep = activeTrack.steps[stepIndex]
  const isLastStep = stepIndex === activeTrack.steps.length - 1

  useEffect(() => {
    setTrack((current) => current || recommendedTrack(profile))
  }, [profile])

  useEffect(() => {
    setDraft('')
  }, [track, stepIndex])

  const completion = useMemo(() => {
    return {
      basics: Number(Boolean(profile.full_name)) + Number(Boolean(profile.headline)) + Number((profile.target_roles || []).length > 0),
      experience: (profile.experience || []).length,
      project: (profile.projects || []).length,
      education: (profile.education || []).length,
    }
  }, [profile])

  const preview = useMemo(() => extractPreview(profile, track), [profile, track])

  function switchTrack(nextTrack) {
    setTrack(nextTrack)
    setStepIndex(0)
  }

  function applyCurrentAnswer() {
    if (!draft.trim() || !activeStep) return
    setProfile((prev) => applyAnswer(track, activeStep.id, draft, prev))
  }

  function handleNext() {
    if (!activeStep) return
    applyCurrentAnswer()
    if (!isLastStep) setStepIndex((current) => current + 1)
  }

  function handlePrevious() {
    setStepIndex((current) => Math.max(0, current - 1))
  }

  function handleFinish() {
    applyCurrentAnswer()
    onSave()
  }

  return (
    <section className="panel-shell">
      <div className="panel-head">
        <div>
          <p className="eyebrow">Capture rapide</p>
          <h2>Assistant de profil guide</h2>
        </div>
        <p className="panel-note">Pas de faux chat. Une question utile a la fois, avec un apercu direct de ce qui entre dans ton profil.</p>
      </div>

      <div className="profile-capture-shell">
        <div className="profile-capture-topbar">
          {Object.entries(TRACKS).map(([key, value]) => (
            <button
              key={key}
              type="button"
              className={`profile-capture-pill ${track === key ? 'is-active' : ''}`}
              onClick={() => switchTrack(key)}
            >
              <strong>{value.label}</strong>
              <span>
                {key === 'basics'
                  ? `${completion.basics}/3`
                  : `${completion[key]}`}
              </span>
            </button>
          ))}
        </div>

        <div className="profile-capture-grid">
          <section className="profile-capture-main">
            <div className="profile-capture-stage">
              <div>
                <p className="eyebrow">{activeTrack.label}</p>
                <h3>{activeTrack.title}</h3>
                <p>{activeTrack.intro}</p>
              </div>
              <div className="profile-capture-progress">
                <span>Etape {stepIndex + 1}/{activeTrack.steps.length}</span>
                <div className="profile-capture-progress-bar">
                  <div style={{ width: `${((stepIndex + 1) / activeTrack.steps.length) * 100}%` }} />
                </div>
              </div>
            </div>

            <label className="field-stack">
              <span>{activeStep.prompt}</span>
              {activeStep.multiline ? (
                <textarea
                  rows={5}
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder={activeStep.placeholder}
                />
              ) : (
                <input
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder={activeStep.placeholder}
                />
              )}
            </label>

            <div className="profile-capture-hint">
              <strong>Conseil</strong>
              <p>{activeStep.hint || 'Reste concret et ecris comme tu voudrais etre compris rapidement par un recruteur.'}</p>
            </div>

            <div className="cv-panel-actions">
              <button className="secondary-button" type="button" onClick={handlePrevious} disabled={stepIndex === 0}>
                Etape precedente
              </button>
              {!isLastStep ? (
                <button className="primary-button" type="button" onClick={handleNext}>
                  Enregistrer et continuer
                </button>
              ) : (
                <button className="primary-button" type="button" onClick={handleFinish} disabled={saving}>
                  {saving ? 'Sauvegarde...' : 'Terminer et sauvegarder'}
                </button>
              )}
              <button className="secondary-button" type="button" onClick={onSave} disabled={saving}>
                {saving ? 'Sauvegarde...' : 'Sauvegarder maintenant'}
              </button>
            </div>
          </section>

          <aside className="profile-capture-side">
            <article className="profile-capture-card">
              <p className="eyebrow">Apercu en direct</p>
              <h3>{activeTrack.title}</h3>
              <div className="profile-capture-preview">
                {preview.map((line) => (
                  <p key={line}>{line}</p>
                ))}
              </div>
            </article>

            <article className="profile-capture-card">
              <p className="eyebrow">Etat du profil</p>
              <ul className="signal-list">
                <li>Bases: {completion.basics}/3</li>
                <li>Experiences: {completion.experience}</li>
                <li>Projets: {completion.project}</li>
                <li>Formation: {completion.education}</li>
              </ul>
            </article>
          </aside>
        </div>
      </div>
    </section>
  )
}
