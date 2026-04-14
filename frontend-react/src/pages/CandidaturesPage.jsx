import { useEffect, useMemo, useState } from 'react'
import { useApplications } from '../context/ApplicationContext'

const STATUS_OPTIONS = [
  { value: 'saved',     label: 'Saved',     cls: 'pill brand' },
  { value: 'applied',   label: 'Applied',   cls: 'pill success' },
  { value: 'interview', label: 'Interview', cls: 'pill warning' },
  { value: 'offer',     label: 'Offer',     cls: 'pill success' },
  { value: 'rejected',  label: 'Rejected',  cls: 'pill danger' },
]

const DOSSIER_TABS = [
  { id: 'fit',       label: 'Fit' },
  { id: 'questions', label: 'Questions' },
  { id: 'stories',   label: 'STAR stories' },
  { id: 'projects',  label: 'Portfolio ideas' },
  { id: 'actions',   label: 'Strengthen' },
]

function statusCls(status) {
  return STATUS_OPTIONS.find((o) => o.value === status)?.cls || 'pill'
}

export default function CandidaturesPage() {
  const { applications, prepByApplicationId, updateStatus, removeApplication, loadPrep, generatePrep } = useApplications()

  const [selectedId, setSelectedId] = useState(null)
  const [notesDraft, setNotesDraft] = useState('')
  const [savingNotes, setSavingNotes] = useState(false)
  const [activeTab, setActiveTab] = useState('fit')

  const selected = applications.find((a) => a.id === selectedId) || applications[0] || null
  const prepState = selected ? prepByApplicationId[selected.id] : null
  const prep = prepState?.prep || null

  useEffect(() => {
    if (!selected) return
    setNotesDraft(selected.notes || '')
    if (selected.has_prep && !prepState?.prep && !prepState?.loading) {
      void loadPrep(selected.id)
    }
  }, [selected?.id])

  const stats = useMemo(() => STATUS_OPTIONS.map((o) => ({
    ...o,
    count: applications.filter((a) => a.status === o.value).length,
  })), [applications])

  async function saveNotes() {
    if (!selected) return
    setSavingNotes(true)
    await updateStatus(selected.id, selected.status, notesDraft)
    setSavingNotes(false)
  }

  if (applications.length === 0) {
    return (
      <div className="page fade-up">
        <div className="page-header">
          <div className="page-header__eyebrow">Applications</div>
          <h1 className="page-header__title">Track every application, prep for every interview.</h1>
          <p className="page-header__sub">
            Save a job from Discover or generate a CV for a role and it will appear here. Each application gets a full prep dossier.
          </p>
        </div>
        <div className="empty-state card">
          <div className="section-title" style={{ marginBottom: 'var(--s3)' }}>No applications yet</div>
          <p className="muted">Head over to Discover, search for a role, and save or generate a CV for it.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page fade-up">
      <div className="page-header">
        <div className="page-header__eyebrow">Applications</div>
        <h1 className="page-header__title">Your pipeline</h1>
      </div>

      {/* Stats strip */}
      <div className="row" style={{ gap: 'var(--s4)', marginBottom: 'var(--s5)', flexWrap: 'wrap' }}>
        {stats.map((s) => (
          <div key={s.value} style={{ display: 'flex', gap: 'var(--s2)', alignItems: 'center' }}>
            <span style={{ fontFamily: 'var(--font-d)', fontSize: '1.25rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
              {s.count}
            </span>
            <span className="muted">{s.label.toLowerCase()}</span>
          </div>
        ))}
      </div>

      <div className="split-layout">
        {/* ── Left: application list ───────────────── */}
        <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: 'var(--s4) var(--s4) var(--s3)' }}>
            <h2 className="section-title">{applications.length} application{applications.length !== 1 ? 's' : ''}</h2>
          </div>
          <div className="scroll-area">
            <div className="scroll-list">
              {applications.map((app) => (
                <button
                  key={app.id}
                  type="button"
                  className={`list-card ${app.id === selected?.id ? 'is-active' : ''}`}
                  onClick={() => setSelectedId(app.id)}
                >
                  <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--s3)' }}>
                    <div style={{ minWidth: 0 }}>
                      <div className="item-title">{app.job_title}</div>
                      <div className="item-subtitle" style={{ marginTop: 2 }}>
                        {app.company_name || 'Company not set'}
                        {app.location ? ` · ${app.location}` : ''}
                      </div>
                    </div>
                    <span className={`${statusCls(app.status)} `} style={{ flexShrink: 0 }}>
                      {STATUS_OPTIONS.find((o) => o.value === app.status)?.label || app.status}
                    </span>
                  </div>
                  <div className="badge-row" style={{ marginTop: 'var(--s2)' }}>
                    {app.contract_type && <span className="pill">{app.contract_type}</span>}
                    {app.prep_status ? (
                      <span className={`pill ${app.prep_is_stale ? 'warning' : 'brand'}`}>
                        {app.prep_is_stale ? 'Prep stale' : `Prep ${app.prep_status}`}
                      </span>
                    ) : (
                      <span className="pill">No prep yet</span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* ── Right: application detail ────────────── */}
        {selected ? (
          <section className="stack">
            {/* Header card */}
            <div className="card">
              <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--s4)', flexWrap: 'wrap' }}>
                <div>
                  <h2 className="section-title" style={{ fontSize: '1.125rem' }}>{selected.job_title}</h2>
                  <p className="section-copy" style={{ marginTop: 'var(--s1)' }}>
                    {selected.company_name || 'Company not set'}
                    {selected.location ? ` · ${selected.location}` : ''}
                  </p>
                  <div className="badge-row" style={{ marginTop: 'var(--s3)' }}>
                    {selected.source && <span className="pill">{selected.source}</span>}
                    {selected.contract_type && <span className="pill">{selected.contract_type}</span>}
                    {selected.prep_status && (
                      <span className={`pill ${selected.prep_is_stale ? 'warning' : 'brand'}`}>
                        {selected.prep_is_stale ? 'Needs refresh' : `Prep ${selected.prep_status}`}
                      </span>
                    )}
                  </div>
                </div>
                <div className="button-row">
                  <button
                    type="button"
                    className="btn-soft"
                    onClick={() => generatePrep(selected.id)}
                    disabled={prepState?.loading}
                  >
                    {prepState?.loading ? (
                      <span className="row" style={{ gap: 'var(--s2)' }}>
                        <span className="spinner" />
                        Generating…
                      </span>
                    ) : prep ? 'Refresh prep' : 'Generate prep'}
                  </button>
                  {selected.job_url && (
                    <a href={selected.job_url} target="_blank" rel="noreferrer" className="btn-ghost">
                      View job
                    </a>
                  )}
                  <button
                    type="button"
                    className="btn-danger btn-sm"
                    onClick={() => removeApplication(selected.id)}
                  >
                    Remove
                  </button>
                </div>
              </div>
            </div>

            {/* Status + notes */}
            <div className="card">
              <div className="grid-2">
                <div className="field-stack">
                  <div className="field-label">Status</div>
                  <select
                    value={selected.status}
                    onChange={(e) => updateStatus(selected.id, e.target.value, notesDraft)}
                  >
                    {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
                <div className="field-stack">
                  <div className="field-label">
                    Notes
                    <span className="field-hint">follow-ups, context</span>
                  </div>
                  <textarea
                    rows={3}
                    value={notesDraft}
                    onChange={(e) => setNotesDraft(e.target.value)}
                  />
                  <button
                    type="button"
                    className="btn-ghost btn-sm"
                    onClick={saveNotes}
                    disabled={savingNotes}
                    style={{ alignSelf: 'flex-start' }}
                  >
                    {savingNotes ? 'Saving…' : 'Save notes'}
                  </button>
                </div>
              </div>
            </div>

            {prepState?.error && (
              <div className="callout callout--error">{prepState.error}</div>
            )}

            {/* Prep dossier */}
            {prep ? (
              <div className="card stack">
                <div className="tabs">
                  {DOSSIER_TABS.map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      className={`tab ${activeTab === t.id ? 'is-active' : ''}`}
                      onClick={() => setActiveTab(t.id)}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>

                {activeTab === 'fit'       && <FitTab prep={prep} />}
                {activeTab === 'questions' && <QuestionsTab prep={prep} />}
                {activeTab === 'stories'   && <StoriesTab prep={prep} />}
                {activeTab === 'projects'  && <ProjectsTab prep={prep} />}
                {activeTab === 'actions'   && <ActionsTab prep={prep} />}
              </div>
            ) : !prepState?.loading && (
              <div className="callout callout--warning">
                No prep dossier yet. Generate one to get job-specific questions, STAR stories, and portfolio ideas.
              </div>
            )}
          </section>
        ) : null}
      </div>
    </div>
  )
}

/* ── Prep tab components ─────────────────────────────────── */

function FitTab({ prep }) {
  const summary  = prep.fit_summary || {}
  const evidence = prep.selected_evidence || {}
  return (
    <div className="stack-s">
      <div className="metric-grid">
        <MetricCard label="Matched keywords" value={summary.matched_keywords?.length || 0} />
        <MetricCard label="Missing keywords" value={summary.missing_keywords?.length || 0} />
        <MetricCard label="Experiences used" value={summary.selected_counts?.experience || 0} />
        <MetricCard label="Projects used"    value={summary.selected_counts?.projects || 0} />
      </div>

      {(summary.strongest_evidence || []).length > 0 && (
        <div>
          <div className="field-label" style={{ marginBottom: 'var(--s2)' }}>Strongest evidence</div>
          <div className="badge-row">
            {summary.strongest_evidence.map((e) => <span key={e} className="pill brand">{e}</span>)}
          </div>
        </div>
      )}

      {(summary.risk_flags || []).length > 0 && (
        <div className="timeline-list">
          {summary.risk_flags.map((f) => <div key={f} className="callout callout--warning">{f}</div>)}
        </div>
      )}

      <div className="grid-2">
        <EvidenceCol title="Experience" items={evidence.experience || []} getTitle={(i) => `${i.title || 'Role'}${i.company ? ` · ${i.company}` : ''}`} />
        <EvidenceCol title="Projects"   items={evidence.projects || []}   getTitle={(i) => i.name || i.role || 'Project'} />
      </div>
      {(evidence.skills || []).length > 0 && (
        <div>
          <div className="field-label" style={{ marginBottom: 'var(--s2)' }}>Selected skills</div>
          <div className="badge-row">
            {evidence.skills.map((s) => <span key={s} className="pill">{s}</span>)}
          </div>
        </div>
      )}
    </div>
  )
}

function QuestionsTab({ prep }) {
  const q = prep.interview_questions || {}
  return (
    <div className="stack-s">
      <QuestionSection title="Motivation" items={q.motivation_questions || []} />
      <QuestionSection title="Behavioural" items={q.behavioural_questions || []} />
      <QuestionSection title="Technical" items={q.technical_questions || []} />
    </div>
  )
}

function StoriesTab({ prep }) {
  return (
    <div className="timeline-list">
      {(prep.star_stories || []).map((story) => (
        <div key={`${story.source_kind}-${story.source_id}-${story.title}`} className="callout stack-s">
          <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--s3)' }}>
            <div className="item-title">{story.title}</div>
            <span className="pill">{story.source_kind}</span>
          </div>
          <p className="muted">{story.when_to_use}</p>
          <p style={{ fontSize: '0.875rem', color: 'var(--ink-2)' }}>{story.prompt}</p>
          {(story.focus_points || []).length > 0 && (
            <div className="badge-row">
              {story.focus_points.map((p) => <span key={p} className="pill">{p}</span>)}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function ProjectsTab({ prep }) {
  return (
    <div className="timeline-list">
      {(prep.portfolio_ideas || []).map((idea) => (
        <div key={`${idea.track}-${idea.title}`} className="callout stack-s">
          <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--s3)' }}>
            <div className="item-title">{idea.title}</div>
            {idea.track && <span className="pill brand">{idea.track}</span>}
          </div>
          <p style={{ fontSize: '0.875rem', color: 'var(--ink-2)' }}>{idea.brief}</p>
          {(idea.stack || []).length > 0 && (
            <div className="badge-row">
              {idea.stack.map((s) => <span key={s} className="pill">{s}</span>)}
            </div>
          )}
          {idea.why_it_helps && <p className="muted">{idea.why_it_helps}</p>}
        </div>
      ))}
    </div>
  )
}

function ActionsTab({ prep }) {
  return (
    <div className="stack-s">
      {(prep.strengthening_actions || []).length > 0 && (
        <div>
          <div className="field-label" style={{ marginBottom: 'var(--s2)' }}>Actions to strengthen this application</div>
          <ol className="note-list">
            {prep.strengthening_actions.map((a) => <li key={a}>{a}</li>)}
          </ol>
        </div>
      )}
      {(prep.copy_notes || []).length > 0 && (
        <div className="timeline-list">
          {prep.copy_notes.map((n) => <div key={n} className="callout">{n}</div>)}
        </div>
      )}
    </div>
  )
}

function EvidenceCol({ title, items, getTitle }) {
  return (
    <div className="stack-s">
      <div className="field-label">{title}</div>
      {items.length === 0 ? <p className="muted">None selected</p> : items.map((item, i) => (
        <div key={`${title}-${i}`}>
          <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--ink)' }}>{getTitle(item)}</div>
          {(item.matched_terms || []).length > 0 && (
            <div className="badge-row" style={{ marginTop: 'var(--s1)' }}>
              {item.matched_terms.map((t) => <span key={t} className="pill brand">{t}</span>)}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function QuestionSection({ title, items }) {
  if (!items.length) return null
  return (
    <div className="stack-s">
      <div className="field-label">{title} questions</div>
      <div className="timeline-list">
        {items.map((item, i) => (
          <div key={`${title}-${i}`} className="callout stack-s">
            <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--s3)' }}>
              <div className="item-title" style={{ fontSize: '0.9375rem' }}>{item.question}</div>
              {item.category && <span className="pill">{item.category}</span>}
            </div>
            {item.why_asked && <p className="muted">{item.why_asked}</p>}
            {item.answer_shape && (
              <p style={{ fontSize: '0.875rem', color: 'var(--ink-2)' }}>
                <strong>Shape: </strong>{item.answer_shape}
              </p>
            )}
            {(item.evidence_refs || []).length > 0 && (
              <div className="badge-row">
                {item.evidence_refs.map((r) => <span key={r} className="pill brand">{r}</span>)}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function MetricCard({ label, value }) {
  return (
    <div className="metric-card">
      <div className="metric-card__value">{value}</div>
      <div className="metric-card__label">{label}</div>
    </div>
  )
}
