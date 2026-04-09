import { useState, useEffect } from 'react'

const STATUS_STYLES = {
  completed: { bg: '#E8F4EC', text: '#2E7D52', label: 'Terminé' },
  running:   { bg: '#E8F0FC', text: '#3A5FA8', label: 'En cours' },
  pending:   { bg: '#FEF9E8', text: '#8B6A00', label: 'En attente' },
}

export default function HistoryPage({ onOpen }) {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchHistory()
  }, [])

  async function fetchHistory() {
    try {
      const res = await fetch('/api/history')
      setHistory(await res.json())
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  async function deleteSearch(id, e) {
    e.stopPropagation()
    await fetch(`/api/history/${id}`, { method: 'DELETE' })
    setHistory(prev => prev.filter(s => s.id !== id))
  }

  function formatDate(iso) {
    if (!iso) return '—'
    return new Date(iso).toLocaleString('fr-FR', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  }

  return (
    <main className="max-w-3xl mx-auto px-4 sm:px-6 py-10">
      <h1 className="text-3xl font-bold mb-2" style={{ color: '#2C3E50' }}>Historique</h1>
      <p className="text-sm mb-8" style={{ color: '#7A90A4' }}>
        Vos 100 dernières recherches.
      </p>

      {loading && (
        <div className="text-center py-16" style={{ color: '#9AABB8' }}>Chargement…</div>
      )}

      {!loading && history.length === 0 && (
        <div
          className="rounded-2xl border p-14 text-center"
          style={{ background: '#fff', borderColor: '#D6DFF0' }}
        >
          <p className="text-4xl mb-4">📋</p>
          <p className="font-semibold" style={{ color: '#2C3E50' }}>Aucune recherche pour l'instant</p>
          <p className="text-sm mt-1" style={{ color: '#9AABB8' }}>Lancez votre première recherche depuis l'onglet Recherche.</p>
        </div>
      )}

      <div className="space-y-3">
        {history.map(s => {
          const st = STATUS_STYLES[s.status] || STATUS_STYLES.pending
          return (
            <div
              key={s.id}
              onClick={() => onOpen(s.id)}
              className="group flex items-center justify-between rounded-2xl border px-5 py-4 cursor-pointer transition-all hover:shadow-md"
              style={{ background: '#fff', borderColor: '#D6DFF0' }}
            >
              <div className="flex items-center gap-4 min-w-0">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold text-sm shrink-0"
                  style={{ background: 'linear-gradient(135deg, #6B9BC8, #7BBFAA)' }}
                >
                  {(s.tool_name || '?')[0].toUpperCase()}
                </div>
                <div className="min-w-0">
                  <p className="font-semibold truncate" style={{ color: '#2C3E50' }}>{s.tool_name}</p>
                  <p className="text-xs" style={{ color: '#9AABB8' }}>{formatDate(s.created_at)}</p>
                </div>
              </div>

              <div className="flex items-center gap-3 shrink-0 ml-3">
                {s.total_results > 0 && (
                  <span className="text-sm font-medium" style={{ color: '#6B7B90' }}>
                    {s.total_results} offre{s.total_results > 1 ? 's' : ''}
                  </span>
                )}
                <span
                  className="px-2.5 py-0.5 rounded-full text-xs font-medium"
                  style={{ background: st.bg, color: st.text }}
                >
                  {st.label}
                </span>
                <button
                  onClick={(e) => deleteSearch(s.id, e)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-lg hover:bg-red-50"
                  title="Supprimer"
                >
                  <svg className="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </main>
  )
}
