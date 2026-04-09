import { useState } from 'react'
import { useApplications } from '../context/ApplicationContext'

const STATUSES = [
  { key: 'saved',     label: 'Sauvegardé',   emoji: '🔖', color: '#6B7B90', bg: '#EEF2F7', border: '#D6DFF0' },
  { key: 'applied',   label: 'Postulé',       emoji: '📤', color: '#3A5FA8', bg: '#E8F0FC', border: '#B8CCEF' },
  { key: 'interview', label: 'Entretien',     emoji: '🤝', color: '#8B6A00', bg: '#FEF9E8', border: '#E8D88A' },
  { key: 'offer',     label: 'Offre reçue',   emoji: '🎉', color: '#2E7D52', bg: '#E8F4EC', border: '#A8D5BC' },
  { key: 'rejected',  label: 'Refusé',        emoji: '❌', color: '#9B2E2E', bg: '#FDECEA', border: '#F5BCBC' },
]

const SOURCE_LABELS = { wttj: 'WTTJ', linkedin: 'LinkedIn', indeed: 'Indeed', jobteaser: 'Jobteaser' }

function StatusBadge({ status }) {
  const s = STATUSES.find(x => x.key === status) || STATUSES[0]
  return (
    <span
      className="px-2.5 py-0.5 rounded-full text-xs font-medium"
      style={{ background: s.bg, color: s.color }}
    >
      {s.emoji} {s.label}
    </span>
  )
}

function ApplicationCard({ app, onStatusChange, onDelete }) {
  const [open, setOpen] = useState(false)
  const [notes, setNotes] = useState(app.notes || '')
  const [saving, setSaving] = useState(false)

  async function handleStatus(newStatus) {
    setSaving(true)
    await onStatusChange(app.id, newStatus, notes)
    setSaving(false)
  }

  async function handleNotesSave() {
    setSaving(true)
    await onStatusChange(app.id, app.status, notes)
    setSaving(false)
    setOpen(false)
  }

  return (
    <div
      className="rounded-2xl border p-4 transition-shadow hover:shadow-md"
      style={{ background: '#fff', borderColor: '#D6DFF0' }}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wider mb-0.5" style={{ color: '#9AABB8' }}>
            {app.company_name || '—'}
          </p>
          <a
            href={app.job_url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-semibold text-sm leading-snug hover:underline"
            style={{ color: '#2C3E50' }}
            onClick={e => e.stopPropagation()}
          >
            {app.job_title}
          </a>
        </div>
        <button
          onClick={() => onDelete(app.id)}
          className="opacity-30 hover:opacity-70 transition-opacity shrink-0"
        >
          <svg className="w-4 h-4" style={{ color: '#9B2E2E' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Meta */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {app.location && (
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: '#EEF2F7', color: '#6B7B90' }}>
            📍 {app.location}
          </span>
        )}
        {app.source && (
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: '#EEF2F7', color: '#6B7B90' }}>
            {SOURCE_LABELS[app.source] || app.source}
          </span>
        )}
        {app.applied_at && (
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: '#EEF2F7', color: '#6B7B90' }}>
            📅 {new Date(app.applied_at).toLocaleDateString('fr-FR')}
          </span>
        )}
      </div>

      {/* Status selector */}
      <div className="flex flex-wrap gap-1 mb-3">
        {STATUSES.map(s => (
          <button
            key={s.key}
            disabled={saving}
            onClick={() => handleStatus(s.key)}
            className="px-2 py-0.5 rounded-full text-xs font-medium border transition-all"
            style={
              app.status === s.key
                ? { background: s.bg, color: s.color, borderColor: s.border }
                : { background: '#fff', color: '#9AABB8', borderColor: '#D6DFF0' }
            }
          >
            {s.emoji} {s.label}
          </button>
        ))}
      </div>

      {/* Notes toggle */}
      <button
        onClick={() => setOpen(!open)}
        className="text-xs underline transition-colors"
        style={{ color: '#9AABB8' }}
      >
        {open ? 'Fermer les notes' : (app.notes ? '📝 Voir les notes' : '+ Ajouter une note')}
      </button>

      {open && (
        <div className="mt-2">
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            rows={3}
            placeholder="Notes sur cette candidature…"
            className="w-full rounded-xl border px-3 py-2 text-sm resize-none outline-none focus:ring-2 transition-shadow"
            style={{ borderColor: '#D6DFF0', color: '#2C3E50' }}
          />
          <button
            onClick={handleNotesSave}
            disabled={saving}
            className="mt-1.5 px-4 py-1.5 rounded-xl text-xs font-semibold text-white"
            style={{ background: 'linear-gradient(135deg, #6B9BC8, #7BBFAA)' }}
          >
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </div>
      )}
    </div>
  )
}

export default function DashboardPage() {
  const { applications, updateStatus, removeApplication } = useApplications()
  const [activeStatus, setActiveStatus] = useState('all')

  const stats = STATUSES.reduce((acc, s) => {
    acc[s.key] = applications.filter(a => a.status === s.key).length
    return acc
  }, {})

  const filtered = activeStatus === 'all'
    ? applications
    : applications.filter(a => a.status === activeStatus)

  return (
    <main className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-1" style={{ color: '#2C3E50' }}>Mes candidatures</h1>
        <p className="text-sm" style={{ color: '#7A90A4' }}>
          {applications.length} offre{applications.length > 1 ? 's' : ''} suivie{applications.length > 1 ? 's' : ''}
        </p>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-8">
        {STATUSES.map(s => (
          <button
            key={s.key}
            onClick={() => setActiveStatus(activeStatus === s.key ? 'all' : s.key)}
            className="rounded-2xl border p-4 text-left transition-all hover:shadow-md"
            style={{
              background: activeStatus === s.key ? s.bg : '#fff',
              borderColor: activeStatus === s.key ? s.border : '#D6DFF0',
            }}
          >
            <p className="text-2xl mb-1">{s.emoji}</p>
            <p className="text-2xl font-bold" style={{ color: s.color }}>{stats[s.key] || 0}</p>
            <p className="text-xs font-medium" style={{ color: '#7A90A4' }}>{s.label}</p>
          </button>
        ))}
      </div>

      {/* Filter pills */}
      <div className="flex gap-2 mb-6 flex-wrap">
        <button
          onClick={() => setActiveStatus('all')}
          className="px-4 py-1.5 rounded-full text-sm font-medium transition-all border"
          style={
            activeStatus === 'all'
              ? { background: '#6B9BC8', color: '#fff', borderColor: '#6B9BC8' }
              : { background: '#fff', color: '#6B7B90', borderColor: '#D6DFF0' }
          }
        >
          Toutes ({applications.length})
        </button>
        {STATUSES.filter(s => stats[s.key] > 0).map(s => (
          <button
            key={s.key}
            onClick={() => setActiveStatus(activeStatus === s.key ? 'all' : s.key)}
            className="px-4 py-1.5 rounded-full text-sm font-medium transition-all border"
            style={
              activeStatus === s.key
                ? { background: s.bg, color: s.color, borderColor: s.border }
                : { background: '#fff', color: '#6B7B90', borderColor: '#D6DFF0' }
            }
          >
            {s.emoji} {s.label} ({stats[s.key]})
          </button>
        ))}
      </div>

      {/* Cards grid */}
      {filtered.length === 0 ? (
        <div
          className="rounded-2xl border p-16 text-center"
          style={{ background: '#fff', borderColor: '#D6DFF0' }}
        >
          <p className="text-5xl mb-4">📋</p>
          <p className="font-semibold text-lg mb-1" style={{ color: '#2C3E50' }}>
            {applications.length === 0 ? 'Aucune candidature suivie' : 'Aucune candidature dans ce statut'}
          </p>
          <p className="text-sm" style={{ color: '#9AABB8' }}>
            {applications.length === 0
              ? 'Sauvegardez des offres depuis la page Recherche pour les retrouver ici.'
              : 'Changez le filtre ou mettez à jour le statut de vos candidatures.'}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map(app => (
            <ApplicationCard
              key={app.id}
              app={app}
              onStatusChange={updateStatus}
              onDelete={removeApplication}
            />
          ))}
        </div>
      )}
    </main>
  )
}
