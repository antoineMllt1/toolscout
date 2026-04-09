import { useState, useEffect, useRef, useCallback } from 'react'
import JobCard from '../components/JobCard'
import FilterBar from '../components/FilterBar'

const POPULAR_TOOLS = [
  'n8n', 'Make', 'Zapier', 'Airtable', 'Notion', 'HubSpot',
  'Power BI', 'Tableau', 'Salesforce', 'Figma', 'Snowflake', 'dbt',
]

const SOURCE_STATUS_LABELS = { wttj: 'WTTJ', linkedin: 'LinkedIn', indeed: 'Indeed', jobteaser: 'Jobteaser' }
const SOURCE_COLORS = { wttj: '#7BBFAA', linkedin: '#0A66C2', indeed: '#6B9BC8', jobteaser: '#E8A598' }
const ALL_SOURCES = ['wttj', 'linkedin', 'indeed', 'jobteaser']

export default function SearchPage({ initialSearchId, onClearInitial }) {
  const [tool, setTool] = useState('')
  const [searchId, setSearchId] = useState(null)
  const [status, setStatus] = useState('idle') // idle | running | completed | error
  const [results, setResults] = useState([])
  const [sourcesDone, setSourcesDone] = useState([])
  const [total, setTotal] = useState(0)
  const [filters, setFilters] = useState({ sources: [], contracts: [], locations: [], sort: 'recent' })
  const sseRef = useRef(null)

  // Load from history if passed
  useEffect(() => {
    if (initialSearchId) {
      loadSearch(initialSearchId)
      onClearInitial()
    }
  }, [initialSearchId])

  async function loadSearch(id) {
    try {
      const res = await fetch(`/api/search/${id}/results`)
      const data = await res.json()
      setSearchId(data.search.id)
      setTool(data.search.tool_name)
      setStatus(data.search.status)
      setTotal(data.search.total_results || 0)
      setSourcesDone((data.search.sources_done || '').split(',').filter(Boolean))
      setResults(
        data.results.map(r => ({
          ...r,
          tool_context: tryParse(r.tool_context),
        }))
      )
    } catch (e) {
      console.error(e)
    }
  }

  function tryParse(v) {
    if (Array.isArray(v)) return v
    try { return JSON.parse(v || '[]') } catch { return [] }
  }

  async function startSearch(e) {
    e?.preventDefault()
    const q = tool.trim()
    if (!q) return

    // Close existing SSE
    sseRef.current?.close()
    setResults([])
    setSourcesDone([])
    setTotal(0)
    setStatus('running')

    try {
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool_name: q }),
      })
      const data = await res.json()
      setSearchId(data.search_id)
      subscribeSSE(data.search_id)
    } catch (err) {
      setStatus('error')
    }
  }

  function subscribeSSE(id) {
    const es = new EventSource(`/api/search/${id}/stream`)
    sseRef.current = es

    es.onmessage = (e) => {
      const msg = JSON.parse(e.data)

      if (msg.type === 'result') {
        const r = msg.data
        r.tool_context = tryParse(r.tool_context)
        setResults(prev => [...prev, r])
      }
      if (msg.type === 'status') {
        setTotal(msg.total || 0)
        setSourcesDone((msg.sources_done || '').split(',').filter(Boolean))
      }
      if (msg.type === 'done') {
        setStatus('completed')
        setTotal(msg.total || 0)
        es.close()
      }
    }

    es.onerror = () => {
      setStatus('completed')
      es.close()
    }
  }

  // Cleanup on unmount
  useEffect(() => () => sseRef.current?.close(), [])

  // Filtered + sorted results
  const filtered = results.filter(r => {
    if (filters.sources.length && !filters.sources.includes(r.source)) return false
    if (filters.contracts.length && !filters.contracts.includes(r.contract_type)) return false
    if (filters.locations.length && !filters.locations.includes(r.location)) return false
    return true
  }).sort((a, b) => {
    if (filters.sort === 'company') return (a.company_name || '').localeCompare(b.company_name || '')
    if (filters.sort === 'title') return (a.job_title || '').localeCompare(b.job_title || '')
    return (b.id || 0) - (a.id || 0) // recent = highest id first
  })

  const isRunning = status === 'running'

  return (
    <main className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
      {/* Hero */}
      <div className="text-center mb-10">
        <h1 className="text-4xl sm:text-5xl font-bold mb-3" style={{ color: '#2C3E50', letterSpacing: '-1px' }}>
          Quelles entreprises utilisent{' '}
          <span style={{ color: '#6B9BC8' }}>vos outils</span> ?
        </h1>
        <p className="text-base" style={{ color: '#7A90A4' }}>
          Recherchez un outil SaaS et découvrez les offres d'emploi qui le mentionnent.
        </p>
      </div>

      {/* Search bar */}
      <form onSubmit={startSearch} className="mb-6">
        <div
          className="flex items-center gap-3 rounded-2xl border px-4 py-3 shadow-sm transition-shadow focus-within:shadow-md"
          style={{ background: '#fff', borderColor: '#D6DFF0' }}
        >
          <svg className="w-5 h-5 shrink-0" style={{ color: '#9AABB8' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            className="flex-1 bg-transparent text-base outline-none placeholder-gray-400"
            style={{ color: '#2C3E50' }}
            placeholder="Ex : n8n, Make, Power BI, Airtable…"
            value={tool}
            onChange={e => setTool(e.target.value)}
            disabled={isRunning}
            autoFocus
          />
          <button
            type="submit"
            disabled={isRunning || !tool.trim()}
            className="px-5 py-2 rounded-xl text-sm font-semibold text-white transition-opacity disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg, #6B9BC8, #7BBFAA)' }}
          >
            {isRunning ? 'Recherche…' : 'Rechercher'}
          </button>
        </div>
      </form>

      {/* Popular tools */}
      {status === 'idle' && (
        <div className="flex flex-wrap gap-2 justify-center mb-8">
          {POPULAR_TOOLS.map(t => (
            <button
              key={t}
              onClick={() => { setTool(t); setTimeout(() => document.querySelector('form')?.requestSubmit(), 0) }}
              className="px-3 py-1.5 rounded-full text-sm border transition-all hover:shadow-sm"
              style={{ background: '#fff', color: '#6B7B90', borderColor: '#D6DFF0' }}
            >
              {t}
            </button>
          ))}
        </div>
      )}

      {/* Progress */}
      {isRunning && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium" style={{ color: '#6B7B90' }}>
              Scraping en cours… {total > 0 && `${total} résultat${total > 1 ? 's' : ''} trouvé${total > 1 ? 's' : ''}`}
            </span>
            <div className="flex gap-2">
              {ALL_SOURCES.map(s => (
                <span
                  key={s}
                  className="px-2.5 py-0.5 rounded-full text-xs font-medium transition-all"
                  style={
                    sourcesDone.includes(s)
                      ? { background: SOURCE_COLORS[s], color: '#fff' }
                      : { background: '#EEF2F7', color: '#9AABB8' }
                  }
                >
                  {sourcesDone.includes(s) ? '✓ ' : ''}{SOURCE_STATUS_LABELS[s]}
                </span>
              ))}
            </div>
          </div>
          {/* Animated bar */}
          <div className="h-1 rounded-full overflow-hidden" style={{ background: '#D6DFF0' }}>
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${(sourcesDone.length / ALL_SOURCES.length) * 100}%`,
                background: 'linear-gradient(90deg, #6B9BC8, #7BBFAA)',
              }}
            />
          </div>
        </div>
      )}

      {/* Results layout */}
      {results.length > 0 && (
        <div className="flex gap-6 items-start">
          {/* Sidebar filters */}
          <aside className="hidden lg:block w-64 shrink-0 sticky top-20">
            <FilterBar results={results} filters={filters} setFilters={setFilters} />
          </aside>

          {/* Cards */}
          <div className="flex-1 min-w-0">
            {/* Result count */}
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm font-medium" style={{ color: '#7A90A4' }}>
                {filtered.length} offre{filtered.length > 1 ? 's' : ''}
                {filtered.length !== results.length && ` (sur ${results.length})`}
              </p>
              {/* Mobile filter toggle could go here */}
            </div>

            {filtered.length === 0 ? (
              <div
                className="rounded-2xl border p-10 text-center"
                style={{ background: '#fff', borderColor: '#D6DFF0' }}
              >
                <p style={{ color: '#9AABB8' }}>Aucune offre ne correspond aux filtres sélectionnés.</p>
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-1 xl:grid-cols-2">
                {filtered.map(r => (
                  <JobCard key={r.id} result={r} />
                ))}
              </div>
            )}

            {/* Streaming indicator */}
            {isRunning && results.length > 0 && (
              <div className="text-center mt-6 text-sm" style={{ color: '#9AABB8' }}>
                <span className="inline-block animate-pulse">● Nouvelles offres en cours…</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Empty state after completed */}
      {status === 'completed' && results.length === 0 && (
        <div
          className="rounded-2xl border p-14 text-center"
          style={{ background: '#fff', borderColor: '#D6DFF0' }}
        >
          <p className="text-5xl mb-4">🔍</p>
          <p className="text-lg font-semibold mb-1" style={{ color: '#2C3E50' }}>Aucun résultat trouvé</p>
          <p className="text-sm" style={{ color: '#9AABB8' }}>
            Essayez un nom d'outil différent ou vérifiez l'orthographe.
          </p>
        </div>
      )}

      {/* Completion banner */}
      {status === 'completed' && results.length > 0 && (
        <div
          className="mt-6 rounded-2xl border px-5 py-3 flex items-center gap-3"
          style={{ background: '#E8F4EC', borderColor: '#A8D5BC' }}
        >
          <span className="text-lg">✅</span>
          <p className="text-sm font-medium" style={{ color: '#2E7D52' }}>
            Scraping terminé — {total} offre{total > 1 ? 's' : ''} trouvée{total > 1 ? 's' : ''} sur {sourcesDone.join(', ')}.
          </p>
        </div>
      )}
    </main>
  )
}
