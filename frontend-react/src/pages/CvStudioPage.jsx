import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { useApplications } from '../context/ApplicationContext'

function rewriteMap(items, key = 'bullets') {
  const map = {}
  for (const item of items || []) {
    if (!item?.id) continue
    map[item.id] = item[key]
  }
  return map
}

export default function CvStudioPage({ pendingJob, onClearPendingJob }) {
  const { authFetch } = useAuth()
  const { applications, saveJob } = useApplications()

  const [profile, setProfile] = useState(null)
  const [templates, setTemplates] = useState([])
  const [selectedTarget, setSelectedTarget] = useState(pendingJob || null)
  const [selectedTemplate, setSelectedTemplate] = useState('moderncv-classic')
  const [generating, setGenerating] = useState(false)
  const [loadingPdf, setLoadingPdf] = useState(false)
  const [autoDownloading, setAutoDownloading] = useState(false)
  const [error, setError] = useState('')
  const [copyError, setCopyError] = useState('')
  const [draft, setDraft] = useState(null)
  const [copySuggestions, setCopySuggestions] = useState(null)
  const [copyFallback, setCopyFallback] = useState(false)

  useEffect(() => { void loadProfile(); void loadTemplates() }, [])

  useEffect(() => {
    if (pendingJob) {
      void resolvePendingJob(pendingJob)
      onClearPendingJob?.()
    }
  }, [pendingJob])

  async function resolvePendingJob(job) {
    if (job?.application_id || applications.some((a) => a.id === job?.id && a.job_url === job.job_url)) {
      setSelectedTarget(job)
      return
    }
    const saved = await saveJob(job)
    setSelectedTarget(saved || job)
  }

  async function loadProfile() {
    try {
      const r = await authFetch('/api/cv/profile')
      if (r.ok) setProfile(await r.json())
    } catch { /* ignore */ }
  }

  async function loadTemplates() {
    try {
      const r = await authFetch('/api/cv/templates')
      if (r.ok) setTemplates(await r.json())
    } catch { /* ignore */ }
  }

  const hasProfile = Boolean(
    profile && (profile.summary || profile.skills?.length || profile.experience?.length || profile.projects?.length || profile.education?.length),
  )

  const availableTargets = useMemo(() => {
    const seen = new Set()
    const items = []
    for (const a of applications) {
      if (seen.has(a.id)) continue
      seen.add(a.id)
      items.push(a)
    }
    if (selectedTarget?.id && !seen.has(selectedTarget.id)) items.unshift(selectedTarget)
    return items
  }, [applications, selectedTarget])

  async function generateDraft() {
    if (!selectedTarget) return null
    setGenerating(true)
    setError('')
    setCopyError('')
    setCopySuggestions(null)
    setCopyFallback(false)
    try {
      const body = { template_slug: selectedTemplate }
      if (selectedTarget.application_id) {
        body.application_id = selectedTarget.application_id
      } else if (selectedTarget.id && selectedTarget.job_url && applications.some((a) => a.id === selectedTarget.id)) {
        body.application_id = selectedTarget.id
      } else if (selectedTarget.search_result_id) {
        body.result_id = selectedTarget.search_result_id
      } else {
        body.result_id = selectedTarget.id
      }

      const r = await authFetch('/api/cv/drafts/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!r.ok) {
        const payload = await r.json().catch(() => ({}))
        throw new Error(payload.detail || 'Unable to generate CV draft')
      }
      const payload = await r.json()
      setDraft(payload.draft)
      setCopySuggestions(payload.copy_suggestions || null)
      setCopyFallback(!!payload.used_fallback)
      if (payload.used_fallback) setCopyError('AI rewrite failed — basic draft applied. Try regenerating.')
      return { draft: payload.draft, suggestions: payload.copy_suggestions || null }
    } catch (err) {
      setError(err.message)
      return null
    } finally {
      setGenerating(false)
    }
  }

  function triggerBlobDownload(blob, filename) {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = filename
    document.body.appendChild(a); a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  async function downloadTex(draftId) {
    try {
      const r = await authFetch(`/api/cv/drafts/${draftId}/tex`)
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || 'TeX download failed') }
      const text = await r.text()
      triggerBlobDownload(new Blob([text], { type: 'text/plain' }), `cv-${draftId}.tex`)
    } catch (err) { setError(err.message) }
  }

  async function downloadPdf(draftId, suggestionsOverride = copySuggestions) {
    setLoadingPdf(true)
    setError('')
    try {
      const r = await authFetch(`/api/cv/drafts/${draftId}/pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ copy_suggestions: suggestionsOverride || undefined }),
      })
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || 'PDF generation failed') }
      triggerBlobDownload(await r.blob(), `cv-${draftId}.pdf`)
    } catch (err) { setError(err.message) }
    finally { setLoadingPdf(false) }
  }

  async function generateAndDownload() {
    if (!selectedTarget || !hasProfile) return
    setAutoDownloading(true)
    const result = await generateDraft()
    if (result?.draft?.id) await downloadPdf(result.draft.id, result.suggestions)
    setAutoDownloading(false)
  }

  const expRewrites  = useMemo(() => rewriteMap(copySuggestions?.experience_rewrites), [copySuggestions])
  const projRewrites = useMemo(() => rewriteMap(copySuggestions?.project_rewrites), [copySuggestions])
  const eduRewrites  = useMemo(() => rewriteMap(copySuggestions?.education_rewrites, 'bullet'), [copySuggestions])

  const isWorking = generating || loadingPdf || autoDownloading

  return (
    <div className="page fade-up">
      <div className="page-header">
        <div className="page-header__eyebrow">CV Studio</div>
        <h1 className="page-header__title">One click from job to tailored PDF.</h1>
        <p className="page-header__sub">
          Select a saved application, pick a template. The AI reads the job posting, picks your strongest content, and rewrites everything to match.
        </p>
      </div>

      {!hasProfile && (
        <div className="callout callout--warning" style={{ marginBottom: 'var(--s4)' }}>
          Your profile needs more content before a strong CV can be generated. Fill in your experience, projects and education in Profile first.
        </div>
      )}

      {error && <div className="callout callout--error" style={{ marginBottom: 'var(--s4)' }}>{error}</div>}
      {copyError && <div className="callout callout--warning" style={{ marginBottom: 'var(--s4)' }}>{copyError}</div>}

      <div className="split-layout">
        {/* ── Left: application picker ─────────────── */}
        <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: 'var(--s4) var(--s4) var(--s3)' }}>
            <h2 className="section-title">Choose an application</h2>
            <p className="section-copy" style={{ marginTop: 'var(--s1)' }}>
              {availableTargets.length} saved
            </p>
          </div>
          {availableTargets.length === 0 ? (
            <div style={{ padding: 'var(--s4)' }}>
              <div className="callout">No saved applications yet. Save a job from the Discover page first.</div>
            </div>
          ) : (
            <div className="scroll-area">
              <div className="scroll-list">
                {availableTargets.map((target) => (
                  <button
                    key={target.id}
                    type="button"
                    className={`list-card ${selectedTarget?.id === target.id ? 'is-active' : ''}`}
                    onClick={() => setSelectedTarget(target)}
                  >
                    <div className="item-title">{target.job_title}</div>
                    <div className="item-subtitle" style={{ marginTop: 2 }}>
                      {target.company_name || 'Company not set'}
                      {target.location ? ` · ${target.location}` : ''}
                    </div>
                    <div className="badge-row" style={{ marginTop: 'var(--s2)' }}>
                      {target.contract_type && <span className="pill">{target.contract_type}</span>}
                      {target.status && <span className="pill brand">{target.status}</span>}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* ── Right: generate + draft preview ──────── */}
        <section className="stack">
          <div className="card stack-s">
            {selectedTarget ? (
              <div className="callout">
                <div className="item-title">{selectedTarget.job_title}</div>
                <div className="item-subtitle" style={{ marginTop: 2 }}>
                  {selectedTarget.company_name}
                  {selectedTarget.location ? ` · ${selectedTarget.location}` : ''}
                </div>
              </div>
            ) : (
              <div className="callout">Select an application on the left to get started.</div>
            )}

            {templates.length > 0 && (
              <div className="field-stack">
                <div className="field-label">Template</div>
                <div className="toggle-group">
                  {templates.map((t) => (
                    <button
                      key={t.slug}
                      type="button"
                      className={`toggle-item ${selectedTemplate === t.slug ? 'is-active' : ''}`}
                      onClick={() => setSelectedTemplate(t.slug)}
                    >
                      {t.name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <button
              type="button"
              className="btn"
              onClick={generateAndDownload}
              disabled={isWorking || !selectedTarget || !hasProfile}
              style={{ width: '100%' }}
            >
              {isWorking ? (
                <span className="row" style={{ gap: 'var(--s2)' }}>
                  <span className="spinner" />
                  {generating ? 'Analysing & tailoring…' : 'Building PDF…'}
                </span>
              ) : 'Generate CV + Download PDF'}
            </button>

            {draft && !isWorking && (
              <div className="button-row">
                <button type="button" className="btn-soft" onClick={() => downloadPdf(draft.id)} disabled={loadingPdf}>
                  {loadingPdf ? 'Building…' : 'Download PDF'}
                </button>
                <button type="button" className="btn-ghost" onClick={() => downloadTex(draft.id)}>
                  Download TeX
                </button>
              </div>
            )}
          </div>

          {draft && !isWorking && (
            <>
              <div className="card stack-s">
                <div className="row-between">
                  <h2 className="section-title">CV content</h2>
                  <span className={`pill ${copySuggestions && !copyFallback ? 'brand' : copyFallback ? 'warning' : ''}`}>
                    {copyFallback ? 'Basic draft' : copySuggestions ? 'AI rewritten' : 'Raw draft'}
                  </span>
                </div>

                <div className="field-stack">
                  <div className="field-label">Headline</div>
                  <div className="callout">{copySuggestions?.headline || profile?.headline || '—'}</div>
                </div>

                <div className="field-stack">
                  <div className="field-label">Summary</div>
                  <div className="callout" style={{ whiteSpace: 'pre-wrap' }}>
                    {copySuggestions?.summary || profile?.summary || '—'}
                  </div>
                </div>

                {(copySuggestions?.skills_priority || draft.selected_payload?.skills || []).length > 0 && (
                  <div className="field-stack">
                    <div className="field-label">Skills selected for this role</div>
                    <div className="badge-row">
                      {(copySuggestions?.skills_priority || draft.selected_payload?.skills || []).map((s) => (
                        <span key={s} className="pill brand">{s}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {(draft.selected_payload?.experience || []).length > 0 && (
                <div className="card stack-s">
                  <h3 className="section-title">Experience</h3>
                  <div className="timeline-list">
                    {draft.selected_payload.experience.map((item) => {
                      const bullets = expRewrites[item.id] || [item.summary, ...(item.highlights || [])].filter(Boolean)
                      return (
                        <div key={item.id} className="callout stack-s">
                          <div>
                            <div className="item-title">{item.title || item.company || 'Experience'}</div>
                            <div className="item-subtitle">
                              {[item.company, item.location, item.start_date && `${item.start_date}${item.end_date ? ` — ${item.end_date}` : ''}`].filter(Boolean).join(' · ')}
                            </div>
                          </div>
                          <ul style={{ paddingLeft: '1.1rem', color: 'var(--ink-2)' }}>
                            {bullets.map((b) => <li key={b} style={{ fontSize: '0.875rem', lineHeight: 1.55 }}>{b}</li>)}
                          </ul>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {(draft.selected_payload?.projects || []).length > 0 && (
                <div className="card stack-s">
                  <h3 className="section-title">Projects</h3>
                  <div className="timeline-list">
                    {draft.selected_payload.projects.map((item) => {
                      const bullets = projRewrites[item.id] || [item.summary, ...(item.highlights || [])].filter(Boolean)
                      return (
                        <div key={item.id} className="callout stack-s">
                          <div>
                            <div className="item-title">{item.name || item.role || 'Project'}</div>
                            <div className="item-subtitle">
                              {[item.role, ...(item.technologies || []).slice(0, 4)].filter(Boolean).join(' · ')}
                            </div>
                          </div>
                          <ul style={{ paddingLeft: '1.1rem', color: 'var(--ink-2)' }}>
                            {bullets.map((b) => <li key={b} style={{ fontSize: '0.875rem', lineHeight: 1.55 }}>{b}</li>)}
                          </ul>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {draft.job_analysis?.candidate_angle && (
                <div className="card stack-s">
                  <h3 className="section-title">How the AI read this role</h3>
                  <div className="callout">{draft.job_analysis.candidate_angle}</div>
                  {(draft.job_analysis?.priority_keywords || []).length > 0 && (
                    <div className="badge-row">
                      {draft.job_analysis.priority_keywords.map((kw) => <span key={kw} className="pill brand">{kw}</span>)}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {!draft && !isWorking && (
            <div className="callout">Select an application and click Generate to get your tailored PDF.</div>
          )}
        </section>
      </div>
    </div>
  )
}
