import { useEffect, useMemo, useState } from 'react'
import { useSearch } from '../context/SearchContext'

function formatDate(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString('fr-FR', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function HistoryPage({ onOpen }) {
  const { searchId } = useSearch()
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void fetchHistory()
  }, [])

  async function fetchHistory() {
    try {
      const response = await fetch('/api/history')
      if (!response.ok) return
      setHistory(await response.json())
    } finally {
      setLoading(false)
    }
  }

  async function removeRun(runId) {
    await fetch(`/api/history/${runId}`, { method: 'DELETE' })
    setHistory((prev) => prev.filter((item) => item.id !== runId))
  }

  const historyStats = useMemo(() => {
    const completed = history.filter((item) => item.status === 'completed').length
    const running = history.filter((item) => item.status === 'running').length
    const totalResults = history.reduce((sum, item) => sum + (item.total_results || 0), 0)
    return { completed, running, totalResults }
  }, [history])

  const latestRun = history[0] || null

  return (
    <main className="history-page">
      <section className="history-layout">
        <article className="hero-slab fade-stagger" style={{ '--index': 0 }}>
          <div className="hero-copy">
            <p className="eyebrow">Run archive</p>
            <h1 className="history-display">Retrouve une recherche, meme apres navigation ou refresh.</h1>
            <p className="lede">
              Les runs restent restaurables pour revenir sur un flux d'annonces, un outil precis ou un tri deja lance.
            </p>
          </div>

          <div className="history-meta-grid">
            <div className="summary-card tone-blue">
              <span>Runs completes</span>
              <strong>{historyStats.completed}</strong>
            </div>
            <div className="summary-card tone-green">
              <span>Runs actifs</span>
              <strong>{historyStats.running}</strong>
            </div>
            <div className="summary-card tone-yellow">
              <span>Annonces cumulees</span>
              <strong>{historyStats.totalResults}</strong>
            </div>
          </div>
        </article>

        <aside className="hero-rail">
          <article className="rail-panel fade-stagger" style={{ '--index': 1 }}>
            <p className="eyebrow">Dernier contexte</p>
            <h2>{latestRun ? latestRun.tool_name : 'Aucun run pour le moment'}</h2>
            <p>
              {latestRun
                ? `${formatDate(latestRun.created_at)} - ${latestRun.total_results || 0} annonces`
                : 'Lance une recherche depuis le workspace pour commencer a remplir cette archive.'}
            </p>
            {latestRun && (
              <button className="text-action" onClick={() => onOpen(latestRun.id)}>
                Restaurer ce run
              </button>
            )}
          </article>
        </aside>
      </section>

      <section className="panel-shell fade-stagger" style={{ '--index': 2 }}>
        <div className="panel-head">
          <div>
            <p className="eyebrow">Historique</p>
            <h2>Dernieres recherches</h2>
          </div>
          <p className="panel-note">Chaque ligne peut rouvrir le contexte exact du run.</p>
        </div>

        {loading ? (
          <div className="kanban-empty">Chargement des runs...</div>
        ) : history.length === 0 ? (
          <div className="kanban-empty">Aucune recherche enregistree.</div>
        ) : (
          <div className="history-stack">
            {history.map((item, index) => (
              <article
                key={item.id}
                className={`history-card fade-stagger ${searchId === item.id ? 'is-active' : ''}`}
                style={{ '--index': index + 3 }}
                onClick={() => onOpen(item.id)}
              >
                <div>
                  <p className="eyebrow">Run #{item.id}</p>
                  <h3>{item.tool_name}</h3>
                  <p>{formatDate(item.created_at)}</p>
                </div>

                <div className="history-card-meta">
                  <span className={`inline-badge ${item.status === 'completed' ? 'is-selected' : ''}`}>
                    {item.status}
                  </span>
                  <span className="inline-badge">{item.total_results || 0} annonces</span>
                </div>

                <div className="history-card-actions">
                  <button
                    className="text-action"
                    onClick={(event) => {
                      event.stopPropagation()
                      onOpen(item.id)
                    }}
                  >
                    Reouvrir
                  </button>
                  <button
                    className="text-action danger"
                    onClick={(event) => {
                      event.stopPropagation()
                      void removeRun(item.id)
                    }}
                  >
                    Supprimer
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}
