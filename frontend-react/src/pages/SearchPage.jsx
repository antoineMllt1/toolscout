import { useEffect, useMemo, useState } from 'react'
import { useSearch } from '../context/SearchContext'
import { useApplications } from '../context/ApplicationContext'
import { useAuth } from '../context/AuthContext'

const SOURCE_META = {
  wttj:      { label: 'WTTJ' },
  indeed:    { label: 'Indeed' },
  linkedin:  { label: 'LinkedIn' },
  jobteaser: { label: 'JobTeaser' },
}

const SOURCE_KEYS = Object.keys(SOURCE_META)

export default function SearchPage({ onGenerateCv }) {
  const { authFetch } = useAuth()
  const { results, isRunning, error, selectedResultId, selectedResult, startSearch, selectResult } = useSearch()
  const { saveJob, byUrl } = useApplications()

  const [query, setQuery] = useState('')
  const [sourceFilter, setSourceFilter] = useState('all')
  const [locationFilter, setLocationFilter] = useState('')
  const [contractFilter, setContractFilter] = useState('')
  const [savingUrl, setSavingUrl] = useState('')
  const [roleSummary, setRoleSummary] = useState('')
  const [summaryHighlights, setSummaryHighlights] = useState([])
  const [summaryLoading, setSummaryLoading] = useState(false)

  const availableContracts = useMemo(
    () => [...new Set(results.map((r) => r.normalized?.contract?.label || r.contract_type).filter(Boolean))].sort((a, b) => a.localeCompare(b)),
    [results],
  )

  const normalizedLoc = locationFilter.trim().toLowerCase()

  const filteredResults = results.filter((r) => {
    const srcOk = sourceFilter === 'all' || r.source === sourceFilter
    const city = r.normalized?.location?.city || ''
    const label = r.normalized?.location?.label || r.location || ''
    const locOk = !normalizedLoc || city.toLowerCase().includes(normalizedLoc) || label.toLowerCase().includes(normalizedLoc)
    const contract = (r.normalized?.contract?.label || r.contract_type || '').toLowerCase()
    const contractOk = !contractFilter || contract === contractFilter.toLowerCase()
    return srcOk && locOk && contractOk
  })

  useEffect(() => {
    if (!selectedResult?.id) { setRoleSummary(''); setSummaryHighlights([]); return }
    let active = true
    setRoleSummary(selectedResult.normalized?.role_summary || '')
    setSummaryHighlights(selectedResult.normalized?.summary_highlights || [])
    setSummaryLoading(true)
    authFetch(`/api/search/results/${selectedResult.id}/summary`)
      .then((r) => r.ok ? r.json() : null)
      .then((p) => {
        if (!active || !p) return
        setRoleSummary(p.summary || selectedResult.normalized?.role_summary || '')
        setSummaryHighlights(p.highlights || selectedResult.normalized?.summary_highlights || [])
      })
      .catch(() => {})
      .finally(() => { if (active) setSummaryLoading(false) })
    return () => { active = false }
  }, [selectedResult?.id])

  async function handleSearch(e) {
    e.preventDefault()
    if (!query.trim()) return
    setSourceFilter('all'); setContractFilter('')
    await startSearch(query.trim())
  }

  async function handleSave(job) {
    if (!job?.job_url) return
    setSavingUrl(job.job_url)
    await saveJob(job)
    setSavingUrl('')
  }

  async function handleGenerate(job) {
    const saved = await saveJob(job)
    onGenerateCv(saved || job)
  }

  function locLabel(job) {
    return job.normalized?.location?.city || job.location || ''
  }

  const hasResults = results.length > 0

  return (
    <div className="page fade-up">

      {/* ── Search bar — always visible ──────────────────────── */}
      {!hasResults && (
        <div className="page-header">
          <div className="page-header__eyebrow">Discover</div>
          <h1 className="page-header__title">Find the role, then make it yours.</h1>
          <p className="page-header__sub">
            Search across WTTJ, Indeed, LinkedIn and JobTeaser at once. Save what matters, generate a targeted CV from it.
          </p>
        </div>
      )}

      <form onSubmit={handleSearch} style={{ marginBottom: hasResults ? 'var(--s4)' : 'var(--s6)' }}>
        <div className="search-wrap">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0, alignSelf: 'center', color: 'var(--ink-3)' }}>
            <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M10.5 10.5L13.5 13.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Backend intern, AI product manager, data analyst…"
          />
          <button type="submit" className="btn" disabled={isRunning || !query.trim()}>
            {isRunning ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--s2)' }}>
                <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                Searching…
              </span>
            ) : 'Search'}
          </button>
        </div>
      </form>

      {error && <div className="callout callout--error" style={{ marginBottom: 'var(--s4)' }}>{error}</div>}

      {/* ── Empty state ──────────────────────────────────────── */}
      {!hasResults && !isRunning && (
        <div style={{
          marginTop: 'var(--s7)',
          textAlign: 'center',
          color: 'var(--ink-3)',
        }}>
          <div style={{
            width: 48, height: 48,
            background: 'var(--rule-soft)',
            borderRadius: '50%',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto var(--s4)',
          }}>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <circle cx="9" cy="9" r="5.5" stroke="var(--ink-3)" strokeWidth="1.75"/>
              <path d="M13.5 13.5L17 17" stroke="var(--ink-3)" strokeWidth="1.75" strokeLinecap="round"/>
            </svg>
          </div>
          <p style={{ fontFamily: 'var(--font-d)', fontWeight: 700, fontSize: '1rem', color: 'var(--ink)', marginBottom: 'var(--s2)' }}>
            Type a role above to start
          </p>
          <p className="muted">Try "Backend intern", "AI product", or "Data analyst"</p>
        </div>
      )}

      {isRunning && !hasResults && (
        <div style={{ textAlign: 'center', marginTop: 'var(--s7)', color: 'var(--ink-3)' }}>
          <div className="spinner spinner--lg" style={{ margin: '0 auto var(--s4)' }} />
          <p className="muted">Searching across all platforms…</p>
        </div>
      )}

      {/* ── Results ──────────────────────────────────────────── */}
      {hasResults && (
        <div className="split-layout" style={{ gap: 'var(--s5)', alignItems: 'start' }}>

          {/* Left: filters + list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s3)' }}>
            {/* Source filter pills */}
            <div style={{ display: 'flex', gap: 'var(--s1)', flexWrap: 'nowrap', overflowX: 'auto', alignItems: 'center', scrollbarWidth: 'none' }}>
              <span className="muted" style={{ marginRight: 'var(--s1)' }}>
                {filteredResults.length} result{filteredResults.length !== 1 ? 's' : ''}
                {filteredResults.length < results.length ? ` of ${results.length}` : ''}
              </span>
              <button
                type="button"
                className={`filter-pill ${sourceFilter === 'all' ? 'is-active' : ''}`}
                onClick={() => setSourceFilter('all')}
              >
                All
              </button>
              {SOURCE_KEYS.map((s) => (
                <button
                  key={s}
                  type="button"
                  className={`filter-pill ${sourceFilter === s ? 'is-active' : ''}`}
                  onClick={() => setSourceFilter(s)}
                >
                  {SOURCE_META[s].label}
                </button>
              ))}
            </div>

            {/* Location + contract */}
            <div style={{ display: 'flex', gap: 'var(--s2)' }}>
              <input
                value={locationFilter}
                onChange={(e) => setLocationFilter(e.target.value)}
                placeholder="Filter by city…"
                style={{ flex: 1 }}
              />
              <select value={contractFilter} onChange={(e) => setContractFilter(e.target.value)} style={{ flex: 1 }}>
                <option value="">All contracts</option>
                {availableContracts.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>

            {/* Job list */}
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <div className="scroll-area">
                <div className="scroll-list">
                  {filteredResults.map((job) => {
                    const isSaved = Boolean(byUrl[job.job_url])
                    const src = SOURCE_META[job.source]
                    const loc = locLabel(job)
                    return (
                      <button
                        key={job.id}
                        type="button"
                        className={`list-card ${selectedResultId === job.id ? 'is-active' : ''}`}
                        onClick={() => selectResult(job.id)}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--s3)', alignItems: 'flex-start' }}>
                          <div style={{ minWidth: 0 }}>
                            <div className="item-title">{job.job_title}</div>
                            <div className="item-subtitle" style={{ marginTop: 3 }}>
                              {job.company_name || 'Unknown'}
                              {loc ? <span style={{ margin: '0 3px', opacity: 0.4 }}>·</span> : ''}
                              {loc}
                            </div>
                          </div>
                          {src && (
                            <span className="pill" style={{ flexShrink: 0, marginTop: 2 }}>
                              {src.label}
                            </span>
                          )}
                        </div>
                        <div className="badge-row" style={{ marginTop: 'var(--s2)' }}>
                          {job.contract_type && <span className="pill">{job.contract_type}</span>}
                          {isSaved && <span className="pill success">Saved</span>}
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* Right: job detail */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s4)', position: 'sticky', top: 'var(--s5)' }}>
            {selectedResult ? (
              <>
                {/* Job header */}
                <div className="card">
                  <h2 style={{
                    fontFamily: 'var(--font-d)',
                    fontSize: '1.25rem',
                    fontWeight: 800,
                    letterSpacing: '-0.02em',
                    color: 'var(--ink)',
                    lineHeight: 1.25,
                    marginBottom: 'var(--s2)',
                  }}>
                    {selectedResult.job_title}
                  </h2>

                  <p style={{ fontSize: '0.9375rem', color: 'var(--ink-2)', marginBottom: 'var(--s3)' }}>
                    {selectedResult.company_name || 'Unknown company'}
                    {locLabel(selectedResult) ? (
                      <span> · <span style={{ color: 'var(--ink-3)' }}>{locLabel(selectedResult)}</span></span>
                    ) : ''}
                  </p>

                  <div className="badge-row" style={{ marginBottom: 'var(--s4)' }}>
                    {selectedResult.contract_type && <span className="pill">{selectedResult.contract_type}</span>}
                    {selectedResult.source && SOURCE_META[selectedResult.source] && (
                      <span className="pill brand">{SOURCE_META[selectedResult.source].label}</span>
                    )}
                    {byUrl[selectedResult.job_url] && <span className="pill success">Saved</span>}
                  </div>

                  <div style={{ display: 'flex', gap: 'var(--s2)', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="btn"
                      onClick={() => handleGenerate(selectedResult)}
                      style={{ flex: 1, minWidth: 160 }}
                    >
                      Save &amp; generate CV
                    </button>
                    <button
                      type="button"
                      className="btn-ghost"
                      onClick={() => handleSave(selectedResult)}
                      disabled={savingUrl === selectedResult.job_url || Boolean(byUrl[selectedResult.job_url])}
                    >
                      {byUrl[selectedResult.job_url] ? 'Saved' : savingUrl === selectedResult.job_url ? 'Saving…' : 'Save'}
                    </button>
                    {selectedResult.job_url && (
                      <a href={selectedResult.job_url} target="_blank" rel="noreferrer" className="btn-ghost">
                        Open ↗
                      </a>
                    )}
                  </div>
                </div>

                {/* Role summary */}
                <div className="card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--s4)' }}>
                    <h3 className="section-title">Role summary</h3>
                    {summaryLoading ? (
                      <span className="pill" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <span className="spinner" style={{ width: 12, height: 12, borderWidth: 1.5 }} />
                        Analysing…
                      </span>
                    ) : (
                      <span className="pill brand">AI</span>
                    )}
                  </div>
                  <p style={{ fontSize: '0.9375rem', color: 'var(--ink-2)', lineHeight: 1.75, whiteSpace: 'pre-wrap' }}>
                    {roleSummary || 'No summary available yet — the AI will generate one when you open a job.'}
                  </p>
                  {summaryHighlights.length > 0 && (
                    <div className="badge-row" style={{ marginTop: 'var(--s4)' }}>
                      {summaryHighlights.map((h) => (
                        <span key={h} className="pill brand" style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {h}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="card" style={{ padding: 'var(--s7) var(--s5)', textAlign: 'center' }}>
                <div style={{
                  width: 40, height: 40,
                  background: 'var(--rule-soft)',
                  borderRadius: 'var(--r2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  margin: '0 auto var(--s3)',
                }}>
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                    <rect x="2.5" y="2.5" width="13" height="13" rx="2" stroke="var(--ink-3)" strokeWidth="1.5"/>
                    <path d="M6 7h6M6 10h4" stroke="var(--ink-3)" strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                </div>
                <p className="section-title" style={{ marginBottom: 'var(--s2)' }}>Select a result</p>
                <p className="muted">Click a job on the left to view details and save it.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
