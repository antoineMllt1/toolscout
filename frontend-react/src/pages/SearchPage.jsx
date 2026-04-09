import { useDeferredValue, useEffect, useMemo, useState } from 'react'
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
    const label = item.label || item.value || item.key
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

function SearchDetailPane({ result, onNavigate, user, isFavorite, onToggleFavorite, onWatchCompany }) {
  if (!result) {
    return (
      <aside className="detail-pane empty">
        <p className="eyebrow">Overview</p>
        <h3 className="detail-title">Selectionne une annonce</h3>
        <p>Chaque carte ouvre ici un resume rapide avant de partir sur le site source.</p>
      </aside>
    )
  }

  const normalized = result.normalized || {}
  const sourceLabel = SOURCE_META[normalized.source?.key]?.label || normalized.source?.label || result.source

  return (
    <aside className="detail-pane">
      <div className="detail-pane-head">
        <div className="detail-pane-copy">
          <p className="eyebrow">{sourceLabel}</p>
          <h3 className="detail-title">{result.job_title}</h3>
          <p className="detail-company">{result.company_name || 'Entreprise non precisee'}</p>
        </div>
        <button
          className="primary-button detail-cta"
          onClick={() => window.open(result.job_url, '_blank', 'noopener,noreferrer')}
        >
          Voir l'annonce source
        </button>
      </div>

      <div className="detail-metadata-grid">
        <div>
          <span>Contrat</span>
          <strong>{normalized.contract?.label || result.contract_type || 'Non precise'}</strong>
        </div>
        <div>
          <span>Mode</span>
          <strong>{normalized.remote_mode?.label || 'A verifier'}</strong>
        </div>
        <div>
          <span>Niveau</span>
          <strong>{normalized.seniority?.label || 'Non precise'}</strong>
        </div>
        <div>
          <span>Ville</span>
          <strong>{normalized.location?.label || result.location || 'Non precisee'}</strong>
        </div>
      </div>

      <section className="detail-section">
        <header>
          <h4>Extraits ou l'outil est cite</h4>
          <small>Normalises pour filtrer plus vite</small>
        </header>
        <div className="detail-quote-list">
          {(result.tool_context || []).map((snippet, index) => (
            <blockquote key={`${result.id}-${index}`}>{formatSnippet(snippet)}</blockquote>
          ))}
        </div>
      </section>

      <section className="detail-section">
        <header>
          <h4>Prochaines actions</h4>
        </header>
        <div className="detail-action-stack">
          {user ? (
            <button className="secondary-button" onClick={() => onToggleFavorite(result)}>
              {isFavorite ? 'Retirer des favoris' : 'Ajouter aux favoris'}
            </button>
          ) : null}
          <button className="secondary-button" onClick={() => onNavigate('dashboard')}>
            Classer dans mes candidatures
          </button>
          <button className="secondary-button" onClick={() => onNavigate('cv')}>
            Ouvrir le profil candidat
          </button>
          {user ? (
            <button className="secondary-button" onClick={() => onWatchCompany(result)}>
              Suivre la societe
            </button>
          ) : null}
          <button className="secondary-button" onClick={() => onNavigate('ops')}>
            Ouvrir career ops
          </button>
        </div>
      </section>
    </aside>
  )
}

export default function SearchPage({ onNavigate }) {
  const { user, authFetch } = useAuth()
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

  async function handleWatchCompany(result) {
    if (!user) {
      onNavigate('auth')
      return
    }
    const companyName = result.company_name || 'Company to watch'
    const response = await authFetch('/api/company-portals', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_name: companyName,
        careers_url: result.job_url,
        active: true,
        favorite: true,
        cadence: 'weekly',
        notes: `Ajoute depuis une annonce: ${result.job_title || ''}`.trim(),
      }),
    })
    if (!response.ok) {
      setActionFeedback('Impossible de creer la veille societe.')
      return
    }
    setActionFeedback(`${companyName} ajoutee a la veille societe.`)
  }

  return (
    <main className="workspace-page">
      <section className="search-dashboard-hero">
        <div className="command-center-card">
          <div className="command-center-head">
            <div className="command-center-copy">
              <p className="eyebrow is-light">Recherche d'offres</p>
              <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.03em', margin: '0 0 6px' }}>
                Lance une recherche
              </h1>
              <p className="lede is-light">{statusCopy}</p>
            </div>
            <div className="command-center-kpis">
              <div className="mini-metric">
                <span>Run</span>
                <strong>{tool || 'Nouveau'}</strong>
              </div>
              <div className="mini-metric">
                <span>Statut</span>
                <strong>{isRunning ? 'En cours' : status === 'completed' ? 'Termine' : 'Pret'}</strong>
              </div>
            </div>
          </div>

          <form
            className="search-command-form"
            onSubmit={(event) => {
              event.preventDefault()
              startSearch(draftTool)
            }}
          >
            <label className="field-stack grow dark">
              <span>Outil a detecter dans les annonces</span>
              <input
                value={draftTool}
                onChange={(event) => setDraftTool(event.target.value)}
                placeholder="Power BI, Make, HubSpot, dbt"
              />
            </label>
            <button className="primary-button light" type="submit" disabled={!draftTool.trim() || isRunning}>
              {isRunning ? 'Scraping en cours' : 'Lancer la recherche'}
            </button>
            <button className="secondary-button dark" type="button" onClick={clearSearch}>
              Reinitialiser
            </button>
          </form>

          <div className="popular-strip dark">
            {POPULAR_TOOLS.map((item) => (
              <button
                key={item}
                type="button"
                className="filter-chip dark"
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
            <div className="overview-card tone-blue">
              <span>Resultats visibles</span>
              <strong>{filteredResults.length}</strong>
            </div>
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
          user={user}
          isFavorite={Boolean(displayedSelectedResult && favoriteByUrl[displayedSelectedResult.job_url])}
          onToggleFavorite={handleToggleFavorite}
          onWatchCompany={handleWatchCompany}
        />
      </section>
    </main>
  )
}
