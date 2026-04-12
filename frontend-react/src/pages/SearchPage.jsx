import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import AppPageHeader from '../components/AppPageHeader'
import FilterBar from '../components/FilterBar'
import JobCard from '../components/JobCard'
import { useApplications } from '../context/ApplicationContext'
import { useAuth } from '../context/AuthContext'
import { useFavorites } from '../context/FavoritesContext'
import { useSearch } from '../context/SearchContext'

const POPULAR_TOOLS = ['n8n', 'Make', 'Airtable', 'Notion', 'Power BI', 'Tableau', 'HubSpot', 'dbt']
const SOURCE_META = {
  wttj: { label: 'WTTJ', color: '#346538', background: '#edf3ec' },
  linkedin: { label: 'LinkedIn', color: '#1f6c9f', background: '#e1f3fe' },
  indeed: { label: 'Indeed', color: '#956400', background: '#fbf3db' },
  jobteaser: { label: 'JobTeaser', color: '#9f2f2d', background: '#fdebec' },
}

function buildOptionList(results, getter) {
  const counts = new Map()
  results.forEach((result) => {
    const item = getter(result)
    if (!item?.key && !item?.value) return
    const value = item.key || item.value
    const label = (item.label || item.value || item.key || '').trim()
    if (!value || !label) return
    counts.set(value, { value, label, count: (counts.get(value)?.count || 0) + 1 })
  })
  return [...counts.values()].sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
}

function matchesLocalQuery(result, query) {
  if (!query) return true
  const haystack = [
    result.job_title,
    result.company_name,
    result.location,
    ...(result.tool_context || []),
  ].join(' ').toLowerCase()
  return haystack.includes(query.toLowerCase())
}

function formatSnippet(snippet) {
  return (snippet || '')
    .replace(/\*\*/g, '')
    .replace(/`/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

const IconSparkle = () => (
  <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 0 0 .95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 0 0-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 0 0-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 0 0-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 0 0 .951-.69l1.07-3.292z" />
  </svg>
)

const IconExternal = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" width="13" height="13">
    <path d="M11 3h6v6M17 3l-8 8M9 5H4a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-5" />
  </svg>
)

function SearchDetailPane({ result, onNavigate, onGenerateCv, user, isFavorite, onToggleFavorite }) {
  if (!result) {
    return (
      <aside className="detail-pane empty">
        <p className="eyebrow">Aperçu</p>
        <h3 className="detail-title">Sélectionne une annonce</h3>
        <p>Clique sur une carte pour voir le détail et générer ton CV.</p>
      </aside>
    )
  }

  const normalized = result.normalized || {}
  const sourceKey = normalized.source?.key || result.source
  const sourceLabel = SOURCE_META[sourceKey]?.label || result.source

  return (
    <aside className="detail-pane">
      <div className="detail-pane-head">
        <div className="detail-pane-copy">
          {sourceLabel && <p className="eyebrow">{sourceLabel}</p>}
          <h3 className="detail-title">{result.job_title}</h3>
          <p className="detail-company">{result.company_name || 'Entreprise non précisée'}</p>
        </div>

        {/* PRIMARY CTA — Generate CV */}
        {user ? (
          <button className="cv-generate-button" onClick={() => onGenerateCv(result)}>
            <IconSparkle />
            Générer mon CV pour ce poste
          </button>
        ) : (
          <button className="cv-generate-button" onClick={() => onNavigate('auth')}>
            <IconSparkle />
            Connecte-toi pour générer ton CV
          </button>
        )}

        <button
          className="secondary-button"
          style={{ width: '100%', justifyContent: 'center' }}
          onClick={() => window.open(result.job_url, '_blank', 'noopener,noreferrer')}
        >
          <IconExternal />
          Voir l'annonce source
        </button>
      </div>

      <div className="detail-metadata-grid">
        <div>
          <span>Contrat</span>
          <strong>{normalized.contract?.label || result.contract_type || 'Non précisé'}</strong>
        </div>
        <div>
          <span>Mode</span>
          <strong>{normalized.remote_mode?.label || 'À vérifier'}</strong>
        </div>
        <div>
          <span>Niveau</span>
          <strong>{normalized.seniority?.label || 'Non précisé'}</strong>
        </div>
        <div>
          <span>Ville</span>
          <strong>{normalized.location?.label || result.location || 'Non précisée'}</strong>
        </div>
      </div>

      {(result.tool_context || []).length > 0 && (
        <section className="detail-section">
          <header>
            <h4>Extraits clés</h4>
            <small>Où l'outil est cité</small>
          </header>
          <div className="detail-quote-list">
            {result.tool_context.map((snippet, index) => (
              <blockquote key={`${result.id}-${index}`}>{formatSnippet(snippet)}</blockquote>
            ))}
          </div>
        </section>
      )}

      <section className="detail-section">
        <header><h4>Actions</h4></header>
        <div className="detail-action-stack">
          {user && (
            <button className="secondary-button" onClick={() => onToggleFavorite(result)}>
              {isFavorite ? '♥ Retirer des favoris' : "♡ Sauvegarder l'offre"}
            </button>
          )}
          <button className="secondary-button" onClick={() => onNavigate('dashboard')}>
            Classer dans mes candidatures
          </button>
        </div>
      </section>
    </aside>
  )
}

export default function SearchPage({ onNavigate, onGenerateCv }) {
  const { user } = useAuth()
  const { byJobUrl: favoriteByUrl, toggleJobFavorite } = useFavorites()
  const {
    tool,
    results,
    total,
    status,
    error,
    sourcesDone,
    isRunning,
    selectedResult,
    selectedResultId,
    startSearch,
    selectResult,
    clearSearch,
  } = useSearch()
  const { applications } = useApplications()
  const [draftTool, setDraftTool] = useState(tool)
  const [actionFeedback, setActionFeedback] = useState('')
  const [filters, setFilters] = useState({
    query: '',
    source: [],
    contract: [],
    remote: [],
    seniority: [],
    location: [],
    sort: 'recent',
  })

  useEffect(() => {
    setDraftTool(tool)
  }, [tool])

  const deferredResults = useDeferredValue(results)

  const filterOptions = useMemo(() => ({
    source: buildOptionList(deferredResults, (result) => {
      const source = result.normalized?.source
      if (!source) return null
      return { ...source, label: SOURCE_META[source.key]?.label || source.label }
    }),
    contract: buildOptionList(deferredResults, (result) => result.normalized?.contract),
    remote: buildOptionList(deferredResults, (result) => result.normalized?.remote_mode),
    seniority: buildOptionList(deferredResults, (result) => result.normalized?.seniority),
    location: buildOptionList(deferredResults, (result) => {
      const city = result.normalized?.location?.city
      return city ? { value: city, label: city } : null
    }).slice(0, 12),
  }), [deferredResults])

  const filteredResults = useMemo(() => {
    const visible = deferredResults.filter((result) => {
      if (!matchesLocalQuery(result, filters.query)) return false
      if (filters.source.length && !filters.source.includes(result.normalized?.source?.key)) return false
      if (filters.contract.length && !filters.contract.includes(result.normalized?.contract?.key)) return false
      if (filters.remote.length && !filters.remote.includes(result.normalized?.remote_mode?.key)) return false
      if (filters.seniority.length && !filters.seniority.includes(result.normalized?.seniority?.key)) return false
      if (filters.location.length && !filters.location.includes(result.normalized?.location?.city)) return false
      return true
    })

    return visible.sort((left, right) => {
      if (filters.sort === 'company') return (left.company_name || '').localeCompare(right.company_name || '')
      if (filters.sort === 'title') return (left.job_title || '').localeCompare(right.job_title || '')
      return (right.id || 0) - (left.id || 0)
    })
  }, [deferredResults, filters])

  const displayedSelectedResult =
    filteredResults.find((result) => result.id === selectedResultId) ||
    selectedResult ||
    filteredResults[0] ||
    null

  const statusCopy = error
    ? error
    : isRunning
      ? `La recherche continue meme si tu changes d'onglet ou de page. ${sourcesDone.length}/4 sources terminees.`
      : total > 0
        ? `${total} annonces remontees. Les filtres utilisent des categories normalisees pour eviter les doublons.`
        : 'Lance une recherche et garde une vue synthetique de chaque annonce avant de partir sur le site source.'

  const sourceCards = Object.entries(SOURCE_META).map(([key, meta]) => ({
    key,
    ...meta,
    done: sourcesDone.includes(key),
  }))

  async function handleToggleFavorite(result) {
    if (!user) {
      onNavigate('auth')
      return
    }
    const existing = favoriteByUrl[result.job_url]
    await toggleJobFavorite(result)
    setActionFeedback(existing ? 'Annonce retiree des favoris.' : 'Annonce ajoutee aux favoris.')
  }

  return (
    <main className="workspace-page">
      <AppPageHeader
        eyebrow="Recherche d'offres"
        title={tool ? `Recherche: ${tool}` : 'Recherche de postes'}
        description={statusCopy}
        actions={
          <>
            <button className="primary-button" type="button" onClick={() => startSearch(draftTool)} disabled={!draftTool.trim() || isRunning}>
              {isRunning ? 'Scraping en cours' : 'Lancer la recherche'}
            </button>
            <button className="secondary-button" type="button" onClick={clearSearch}>
              Reinitialiser
            </button>
          </>
        }
        stats={[
          { label: 'Run', value: tool || 'Nouveau', tone: 'tone-blue' },
          { label: 'Statut', value: isRunning ? 'En cours' : status === 'completed' ? 'Termine' : 'Pret', tone: 'tone-green' },
          { label: 'Resultats visibles', value: filteredResults.length, tone: 'tone-yellow' },
          { label: 'Sources terminees', value: `${sourcesDone.length}/4` },
        ]}
      />

      <section className="search-dashboard-hero">
        <div className="panel-shell search-command-shell fade-stagger" style={{ '--index': 1 }}>
          <div className="panel-head">
            <div>
              <p className="eyebrow">Commande</p>
              <h2>Lancer un run</h2>
            </div>
            <p className="panel-note">Choisis un outil, lance le scraping, puis affine les cartes avec les filtres.</p>
          </div>

          <form
            className="search-command-form"
            onSubmit={(event) => {
              event.preventDefault()
              startSearch(draftTool)
            }}
          >
            <label className="field-stack grow">
              <span>Outil a detecter dans les annonces</span>
              <input
                value={draftTool}
                onChange={(event) => setDraftTool(event.target.value)}
                placeholder="Power BI, Make, HubSpot, dbt"
              />
            </label>
            <button className="primary-button" type="submit" disabled={!draftTool.trim() || isRunning}>
              {isRunning ? 'Scraping en cours' : 'Lancer la recherche'}
            </button>
            <button className="secondary-button" type="button" onClick={clearSearch}>
              Reinitialiser
            </button>
          </form>

          <div className="popular-strip">
            {POPULAR_TOOLS.map((item) => (
              <button
                key={item}
                type="button"
                className="filter-chip"
                onClick={() => {
                  setDraftTool(item)
                  startSearch(item)
                }}
              >
                <span>{item}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="search-overview-stack">
          <div className="overview-grid">
            <div className="overview-card tone-green">
              <span>Sources terminees</span>
              <strong>{sourcesDone.length}/4</strong>
            </div>
            <div className="overview-card tone-yellow">
              <span>Candidatures</span>
              <strong>{applications.length}</strong>
            </div>
          </div>

          <div className="run-health-card">
            <div className="panel-head compact">
              <div>
                <p className="eyebrow">Run health</p>
                <h2>Etat des scrapers</h2>
              </div>
              <button className="text-action inverted" onClick={() => onNavigate('history')}>
                Historique
              </button>
            </div>

            <div className="source-health-grid">
              {sourceCards.map((item) => (
                <div
                  key={item.key}
                  className={`source-health-card ${item.done ? 'is-done' : ''}`}
                  style={{ '--source-color': item.color, '--source-background': item.background }}
                >
                  <div className="source-health-head">
                    <span>{item.label}</span>
                    <span className="status-dot" />
                  </div>
                  <strong>{item.done ? 'Termine' : isRunning ? 'Actif' : 'Pret'}</strong>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {actionFeedback ? <div className="feedback-box info">{actionFeedback}</div> : null}

      <section className="workspace-grid">
        <FilterBar
          filters={filters}
          setFilters={setFilters}
          options={filterOptions}
          resultCount={filteredResults.length}
        />

        <section className="results-column">
          <div className="results-column-head">
            <div className="section-copy">
              <p className="eyebrow">Run actif</p>
              <p className="section-title">{tool || 'Aucune recherche active'}</p>
            </div>
            <div className="results-head-actions">
              <span className={`inline-badge ${status === 'completed' ? 'is-selected' : ''}`}>
                {status === 'running' ? 'En cours' : status === 'completed' ? 'Termine' : 'En attente'}
              </span>
              <button className="text-action" onClick={() => onNavigate('history')}>
                Voir les runs
              </button>
            </div>
          </div>

          <div className="result-stream-note">
            <div className="status-dot" />
            <span>{isRunning ? 'Le flux continue en arriere-plan.' : 'Le resultat reste restaurable apres refresh.'}</span>
          </div>

          {error ? <div className="feedback-box danger">{error}</div> : null}

          {filteredResults.length === 0 ? (
            <div className="empty-panel">
              <p className="eyebrow">Aucune carte</p>
              <h3>{status === 'completed' ? 'Rien ne correspond a ces filtres.' : 'Lance une recherche pour remplir le board.'}</h3>
              <p>Les cartes deviennent cliquables des que les premiers resultats arrivent.</p>
            </div>
          ) : (
            <div className="job-card-list">
              {filteredResults.map((result, index) => (
                <div key={result.id} className="fade-stagger" style={{ '--index': index }}>
                  <JobCard
                    result={result}
                    isActive={selectedResultId === result.id}
                    onOpen={(item) => selectResult(item.id)}
                  />
                </div>
              ))}
            </div>
          )}
        </section>

        <SearchDetailPane
          result={displayedSelectedResult}
          onNavigate={onNavigate}
          onGenerateCv={onGenerateCv}
          user={user}
          isFavorite={Boolean(displayedSelectedResult && favoriteByUrl[displayedSelectedResult.job_url])}
          onToggleFavorite={handleToggleFavorite}
        />
      </section>
    </main>
  )
}
