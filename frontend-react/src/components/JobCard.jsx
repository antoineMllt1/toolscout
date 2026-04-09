import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { useApplications } from '../context/ApplicationContext'

const SOURCE_COLORS = {
  wttj:      { bg: '#E8F4EC', text: '#3A8A5C', label: 'WTTJ' },
  indeed:    { bg: '#E8F0FC', text: '#3A5FA8', label: 'Indeed' },
  jobteaser: { bg: '#FEF0E8', text: '#B05A2A', label: 'Jobteaser' },
  linkedin:  { bg: '#E8EFF8', text: '#0A66C2', label: 'LinkedIn' },
}

const CONTRACT_COLORS = {
  'CDI':        { bg: '#E8F4EC', text: '#2E7D52' },
  'Stage':      { bg: '#FEF0E8', text: '#B05A2A' },
  'Alternance': { bg: '#F3ECFC', text: '#6B3AAD' },
  'CDD':        { bg: '#FEF9E8', text: '#8B6A00' },
  'Freelance':  { bg: '#E8F0FC', text: '#3A5FA8' },
}

const STATUS_NEXT = {
  saved:     { label: 'Marquer postulé',    next: 'applied',   emoji: '📤' },
  applied:   { label: 'Entretien obtenu',   next: 'interview', emoji: '🤝' },
  interview: { label: 'Offre reçue',        next: 'offer',     emoji: '🎉' },
  offer:     { label: 'Offre acceptée ✓',   next: null,        emoji: '🎉' },
  rejected:  { label: 'Refusé',             next: null,        emoji: '❌' },
}

function contractStyle(type) {
  for (const [key, style] of Object.entries(CONTRACT_COLORS)) {
    if (type && type.toLowerCase().includes(key.toLowerCase())) return style
  }
  return { bg: '#EEF2F7', text: '#6B7B90' }
}

export default function JobCard({ result }) {
  const { user } = useAuth()
  const { byUrl, saveJob, updateStatus } = useApplications()

  const src    = SOURCE_COLORS[result.source] || { bg: '#EEF2F7', text: '#6B7B90', label: result.source }
  const ctx    = Array.isArray(result.tool_context) ? result.tool_context : []
  const cStyle = contractStyle(result.contract_type)

  const existing = byUrl[result.job_url]
  const [saving, setSaving] = useState(false)

  function openJob(e) {
    if (e.target.closest('button')) return
    if (result.job_url) window.open(result.job_url, '_blank', 'noopener,noreferrer')
  }

  async function handleSave(e) {
    e.stopPropagation()
    if (!user || saving) return
    setSaving(true)
    await saveJob(result)
    setSaving(false)
  }

  async function handleAdvance(e) {
    e.stopPropagation()
    if (!existing || saving) return
    const nextStatus = STATUS_NEXT[existing.status]?.next
    if (!nextStatus) return
    setSaving(true)
    await updateStatus(existing.id, nextStatus)
    setSaving(false)
  }

  const statusInfo = existing ? STATUS_NEXT[existing.status] : null

  return (
    <div
      className="group rounded-2xl border p-5 cursor-pointer transition-all duration-200 hover:shadow-md"
      style={{
        background: '#fff',
        borderColor: existing ? '#A8D5BC' : '#D6DFF0',
      }}
      onClick={openJob}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: '#9AABB8' }}>
            {result.company_name || '—'}
          </p>
          <h3 className="font-semibold text-base leading-snug group-hover:underline" style={{ color: '#2C3E50' }}>
            {result.job_title}
          </h3>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {/* Save / status button */}
          {user && (
            existing ? (
              <div className="flex items-center gap-1.5">
                <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                  style={{ background: '#E8F4EC', color: '#2E7D52' }}>
                  {statusInfo?.emoji} {existing.status === 'saved' ? 'Sauvegardé' :
                    existing.status === 'applied' ? 'Postulé' :
                    existing.status === 'interview' ? 'Entretien' :
                    existing.status === 'offer' ? 'Offre' : 'Refusé'}
                </span>
                {statusInfo?.next && (
                  <button
                    onClick={handleAdvance}
                    disabled={saving}
                    title={statusInfo.label}
                    className="w-6 h-6 rounded-full flex items-center justify-center text-xs transition-all hover:scale-110"
                    style={{ background: '#E8F4EC' }}
                  >
                    →
                  </button>
                )}
              </div>
            ) : (
              <button
                onClick={handleSave}
                disabled={saving}
                title="Sauvegarder cette offre"
                className="w-7 h-7 rounded-full flex items-center justify-center transition-all hover:scale-110 opacity-0 group-hover:opacity-100"
                style={{ background: '#EEF2F7', color: '#6B9BC8' }}
              >
                {saving ? '…' : '🔖'}
              </button>
            )
          )}
          {/* External link */}
          <svg
            className="w-4 h-4 opacity-30 group-hover:opacity-70 transition-opacity"
            style={{ color: '#6B9BC8' }}
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </div>
      </div>

      {/* Meta tags */}
      <div className="flex flex-wrap gap-2 mb-3">
        <span className="px-2.5 py-0.5 rounded-full text-xs font-medium" style={{ background: src.bg, color: src.text }}>
          {src.label}
        </span>
        {result.contract_type && (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-medium" style={{ background: cStyle.bg, color: cStyle.text }}>
            {result.contract_type}
          </span>
        )}
        {result.location && (
          <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium"
            style={{ background: '#EEF2F7', color: '#6B7B90' }}>
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            {result.location}
          </span>
        )}
      </div>

      {/* Context excerpts */}
      {ctx.length > 0 && (
        <div className="space-y-1.5">
          {ctx.slice(0, 2).map((c, i) => (
            <p key={i} className="text-sm leading-relaxed line-clamp-2" style={{ color: '#5A6B7B' }}>
              <span className="opacity-40 mr-1">"</span>{c}<span className="opacity-40 ml-1">"</span>
            </p>
          ))}
        </div>
      )}
    </div>
  )
}
