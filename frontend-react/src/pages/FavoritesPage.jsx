import { useMemo, useState } from 'react'
import { useFavorites } from '../context/FavoritesContext'
import { useAuth } from '../context/AuthContext'
import AppPageHeader from '../components/AppPageHeader'

const SOURCE_META = {
  wttj: { label: 'WTTJ', color: '#166534', bg: '#DCFCE7' },
  linkedin: { label: 'LinkedIn', color: '#1D4ED8', bg: '#DBEAFE' },
  indeed: { label: 'Indeed', color: '#92400E', bg: '#FEF3C7' },
  jobteaser: { label: 'JobTeaser', color: '#991B1B', bg: '#FEE2E2' },
}

const IconSparkle = () => (
  <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 0 0 .95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 0 0-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 0 0-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 0 0-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 0 0 .951-.69l1.07-3.292z" />
  </svg>
)

const IconTrash = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" width="14" height="14">
    <path d="M3 6h14M8 6V4h4v2M5 6l1 11h8l1-11" />
  </svg>
)

const IconExternal = () => (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" width="13" height="13">
    <path d="M11 3h6v6M17 3l-8 8M9 5H4a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-5" />
  </svg>
)

function formatSnippet(snippet) {
  return (snippet || '')
    .replace(/\*\*/g, '')
    .replace(/`/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

export default function FavoritesPage({ onNavigate, onGenerateCv }) {
  const { user } = useAuth()
  const { favorites, removeFavorite } = useFavorites()
  const [selectedId, setSelectedId] = useState(null)

  const selected = useMemo(
    () => favorites.find((item) => item.id === selectedId) || favorites[0] || null,
    [favorites, selectedId],
  )

  if (!user) {
    return (
      <main className="favorites-page">
        <section className="empty-panel">
          <p className="eyebrow">Compte requis</p>
          <h3>Connecte-toi pour retrouver les offres que tu veux vraiment poursuivre.</h3>
          <p>Les favoris servent de shortlist avant de passer en candidature ou en CV cible.</p>
          <button className="primary-button" onClick={() => onNavigate('auth')}>
            Ouvrir la connexion
          </button>
        </section>
      </main>
    )
  }

  return (
    <main className="favorites-page">
      <AppPageHeader
        eyebrow="Favorites"
        title="Shortlist d'offres"
        description={
          selected
            ? `${selected.job_title || 'Offre'} chez ${selected.company_name || 'Entreprise'} est actuellement ouverte dans le panneau detail.`
            : "Garde ici uniquement les offres qui meritent un vrai suivi, un CV cible ou une candidature."
        }
        actions={
          <>
            <button className="primary-button" onClick={() => onNavigate('search')}>
              Ajouter des annonces
            </button>
            <button className="secondary-button" onClick={() => onNavigate('dashboard')}>
              Ouvrir le cockpit
            </button>
          </>
        }
        stats={[
          { label: 'Shortlist', value: favorites.length, tone: 'tone-blue' },
          { label: 'Avec notes', value: favorites.filter((item) => item.notes).length, tone: 'tone-green' },
          { label: 'Avec extrait', value: favorites.filter((item) => (item.payload?.tool_context || []).length).length, tone: 'tone-yellow' },
        ]}
      />

      {favorites.length === 0 ? (
        <section className="empty-panel">
          <p className="eyebrow">Shortlist vide</p>
          <h3>Aucune offre n a encore ete epinglee.</h3>
          <p>Depuis la recherche, garde seulement les cartes qui meritent un vrai suivi.</p>
          <button className="primary-button" onClick={() => onNavigate('search')}>
            Lancer une recherche
          </button>
        </section>
      ) : (
        <section className="favorites-layout">
          <section className="favorites-list panel-shell fade-stagger" style={{ '--index': 5 }}>
            <div className="panel-head">
              <div>
                <p className="eyebrow">Shortlist</p>
                <h2>Offres sauvegardees</h2>
              </div>
              <p className="panel-note">Clique une carte pour afficher les signaux et lancer la suite.</p>
            </div>

            <div className="favorites-list-stack">
              {favorites.map((favorite, index) => {
                const meta = SOURCE_META[favorite.source]
                const active = (selected?.id || favorites[0]?.id) === favorite.id

                return (
                  <button
                    key={favorite.id}
                    type="button"
                    className={`favorite-list-card fade-stagger ${active ? 'is-active' : ''}`}
                    style={{ '--index': index + 6 }}
                    onClick={() => setSelectedId(favorite.id)}
                  >
                    <div className="favorite-list-top">
                      <div>
                        <p className="eyebrow">{meta?.label || 'Source'}</p>
                        <h3>{favorite.job_title || 'Poste a qualifier'}</h3>
                      </div>
                      {meta ? (
                        <span className="favorite-source-pill" style={{ color: meta.color, background: meta.bg }}>
                          {meta.label}
                        </span>
                      ) : null}
                    </div>

                    <p className="favorite-list-company">{favorite.company_name || 'Entreprise a preciser'}</p>

                    <div className="favorite-list-meta">
                      {favorite.location ? <span className="inline-badge">{favorite.location}</span> : null}
                      {favorite.contract_type ? <span className="inline-badge">{favorite.contract_type}</span> : null}
                      {favorite.notes ? <span className="inline-badge is-selected">Note</span> : null}
                    </div>
                  </button>
                )
              })}
            </div>
          </section>

          {selected ? (
            <aside className="detail-pane favorites-detail-pane fade-stagger" style={{ '--index': 7 }}>
              <div className="detail-pane-head">
                <div className="detail-pane-copy">
                  <p className="eyebrow">{SOURCE_META[selected.source]?.label || 'Source'}</p>
                  <h3 className="detail-title">{selected.job_title || 'Poste cible'}</h3>
                  <p className="detail-company">{selected.company_name || 'Entreprise'}</p>
                </div>

                <button className="cv-generate-button" onClick={() => onGenerateCv(selected)}>
                  <IconSparkle />
                  Generer mon CV pour ce poste
                </button>

                <button
                  className="secondary-button"
                  style={{ width: '100%', justifyContent: 'center' }}
                  onClick={() => window.open(selected.job_url, '_blank', 'noopener,noreferrer')}
                >
                  <IconExternal />
                  Voir l annonce source
                </button>
              </div>

              <div className="detail-metadata-grid">
                <div>
                  <span>Localisation</span>
                  <strong>{selected.location || 'Non precisee'}</strong>
                </div>
                <div>
                  <span>Contrat</span>
                  <strong>{selected.contract_type || 'Non precise'}</strong>
                </div>
                <div>
                  <span>Source</span>
                  <strong>{selected.source?.toUpperCase() || 'N/A'}</strong>
                </div>
                <div>
                  <span>Statut</span>
                  <strong style={{ color: 'var(--brand)' }}>Favori</strong>
                </div>
              </div>

              {(selected.payload?.tool_context || []).length > 0 ? (
                <section className="detail-section">
                  <header>
                    <h4>Extraits cles</h4>
                    <small>Indices recuperes dans l annonce</small>
                  </header>
                  <div className="detail-quote-list">
                    {selected.payload.tool_context.map((snippet, index) => (
                      <blockquote key={`${selected.id}-${index}`}>{formatSnippet(snippet)}</blockquote>
                    ))}
                  </div>
                </section>
              ) : null}

              {selected.notes ? (
                <section className="detail-section">
                  <header>
                    <h4>Notes</h4>
                  </header>
                  <p className="favorite-note-copy">{selected.notes}</p>
                </section>
              ) : null}

              <section className="detail-section">
                <header>
                  <h4>Actions</h4>
                </header>
                <div className="detail-action-stack">
                  <button className="secondary-button" onClick={() => onNavigate('dashboard')}>
                    Classer dans mes candidatures
                  </button>
                  <button className="secondary-button" onClick={() => onNavigate('ops')}>
                    Transformer en veille societe
                  </button>
                  <button
                    className="secondary-button favorite-danger-button"
                    onClick={() => {
                      removeFavorite(selected.id)
                      setSelectedId(null)
                    }}
                  >
                    <IconTrash />
                    Retirer des favoris
                  </button>
                </div>
              </section>
            </aside>
          ) : null}
        </section>
      )}
    </main>
  )
}
