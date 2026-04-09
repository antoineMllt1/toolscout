import { useState } from 'react'
import { useApplications } from '../context/ApplicationContext'
import { useAuth } from '../context/AuthContext'

const STATUS_LABELS = {
  saved: 'A relire',
  applied: 'Candidate',
  interview: 'Entretien',
  offer: 'Offre',
  rejected: 'Cloture',
}

const SOURCE_LABELS = {
  wttj: 'WTTJ',
  linkedin: 'LinkedIn',
  indeed: 'Indeed',
  jobteaser: 'JobTeaser',
}

function formatSnippet(snippet) {
  return (snippet || '')
    .replace(/\*\*/g, '')
    .replace(/`/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

export default function JobCard({ result, onOpen, isActive }) {
  const { user } = useAuth()
  const { byUrl, saveJob, updateStatus } = useApplications()
  const [saving, setSaving] = useState(false)

  const application = byUrl[result.job_url]
  const normalized = result.normalized || {}
  const contract = normalized.contract?.label || result.contract_type || 'Non precise'
  const remote = normalized.remote_mode?.label || 'A verifier'
  const seniority = normalized.seniority?.label || 'Non precise'
  const sourceLabel = SOURCE_LABELS[normalized.source?.key] || normalized.source?.label || result.source

  async function handleSave(event) {
    event.stopPropagation()
    if (!user || saving) return
    setSaving(true)
    await saveJob(result)
    setSaving(false)
  }

  async function advanceStatus(event) {
    event.stopPropagation()
    if (!application || saving) return
    const next = application.status === 'saved'
      ? 'applied'
      : application.status === 'applied'
        ? 'interview'
        : application.status === 'interview'
          ? 'offer'
          : null
    if (!next) return
    setSaving(true)
    await updateStatus(application.id, next)
    setSaving(false)
  }

  return (
    <article
      className={`job-card ${isActive ? 'is-active' : ''}`}
      onClick={() => onOpen(result)}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onOpen(result)
        }
      }}
    >
      <div className="job-card-head">
        <div className="job-card-copy">
          <p className="eyebrow">{sourceLabel}</p>
          <h3>{result.job_title}</h3>
          <p className="job-company">{result.company_name || 'Entreprise non precisee'}</p>
        </div>

        <div className="job-card-actions">
          {application ? (
            <>
              <span className="inline-badge is-selected">{STATUS_LABELS[application.status] || 'Suivie'}</span>
              <button className="inline-icon-button" onClick={advanceStatus}>
                Etape suivante
              </button>
            </>
          ) : user ? (
            <button className="inline-icon-button" onClick={handleSave}>
              {saving ? 'En cours' : 'Sauvegarder'}
            </button>
          ) : null}
        </div>
      </div>

      <div className="job-card-meta">
        <span className="inline-badge">{contract}</span>
        <span className="inline-badge">{remote}</span>
        <span className="inline-badge">{seniority}</span>
        {normalized.location?.city && <span className="inline-badge">{normalized.location.city}</span>}
      </div>

      <div className="job-card-context">
        {(result.tool_context || []).slice(0, 2).map((snippet, index) => (
          <p key={`${result.id}-${index}`}>{formatSnippet(snippet)}</p>
        ))}
      </div>

      <div className="job-card-footer">
        <button
          className="text-action"
          onClick={(event) => {
            event.stopPropagation()
            window.open(result.job_url, '_blank', 'noopener,noreferrer')
          }}
        >
          Ouvrir l'annonce
        </button>
        <span className="mono-meta">overview</span>
      </div>
    </article>
  )
}
