import { useEffect, useMemo, useState } from 'react'
import AppPageHeader from '../components/AppPageHeader'
import { useAuth } from '../context/AuthContext'
import { useApplications } from '../context/ApplicationContext'
import { useFavorites } from '../context/FavoritesContext'

function completionFromProfile(profile) {
  if (!profile) return 0
  const score = [
    Boolean(profile.full_name),
    Boolean(profile.headline),
    Boolean(profile.summary),
    (profile.target_roles || []).length > 0,
    (profile.skills || []).length > 0,
    (profile.experience || []).length > 0,
    (profile.projects || []).length > 0,
    Boolean(profile.portfolio_url),
  ].filter(Boolean).length
  return Math.round((score / 8) * 100)
}

export default function HomePage({ onNavigate }) {
  const { user, authFetch } = useAuth()
  const { applications } = useApplications()
  const { favorites } = useFavorites()
  const [profile, setProfile] = useState(null)
  const [drafts, setDrafts] = useState([])

  useEffect(() => {
    if (!user) return
    void loadData()
  }, [user])

  async function loadData() {
    const [profileResponse, draftsResponse] = await Promise.all([
      authFetch('/api/cv/profile'),
      authFetch('/api/cv/drafts'),
    ])
    if (profileResponse.ok) setProfile(await profileResponse.json())
    if (draftsResponse.ok) setDrafts(await draftsResponse.json())
  }

  const profileCompletion = completionFromProfile(profile)
  const activeApplications = applications.filter((item) => ['saved', 'applied', 'interview'].includes(item.status)).length
  const interviewCount = applications.filter((item) => item.status === 'interview').length
  const nextFavorite = favorites[0] || null
  const latestDraft = drafts[0] || null

  const nextActions = useMemo(() => {
    const actions = []
    if (profileCompletion < 70) {
      actions.push({
        title: 'Completer ton profil',
        copy: 'Renseigne les bases, les experiences et ton portfolio pour rendre la generation CV beaucoup plus fiable.',
        cta: 'Ouvrir le profil',
        page: 'profile',
      })
    }
    if (favorites.length > 0) {
      actions.push({
        title: 'Generer un CV pour une offre aimee',
        copy: `Ta shortlist contient ${favorites.length} offre${favorites.length > 1 ? 's' : ''} prêtes a etre transformees en candidature.`,
        cta: 'Ouvrir les favoris',
        page: 'favorites',
      })
    }
    if (activeApplications > 0) {
      actions.push({
        title: 'Mettre a jour tes candidatures',
        copy: `${activeApplications} candidature${activeApplications > 1 ? 's' : ''} restent actives dans le pipeline.`,
        cta: 'Voir les candidatures',
        page: 'dashboard',
      })
    }
    if (interviewCount > 0) {
      actions.push({
        title: 'Preparer tes entretiens',
        copy: `${interviewCount} entretien${interviewCount > 1 ? 's' : ''} en cours merite${interviewCount > 1 ? 'nt' : ''} une preparation.`,
        cta: 'Ouvrir l’entretien',
        page: 'interview',
      })
    }
    if (actions.length === 0) {
      actions.push({
        title: 'Lancer une nouvelle recherche',
        copy: 'Commence par chercher des offres pertinentes puis construis ta shortlist.',
        cta: 'Ouvrir la recherche',
        page: 'search',
      })
    }
    return actions.slice(0, 3)
  }, [profileCompletion, favorites.length, activeApplications, interviewCount])

  if (!user) {
    return (
      <main className="dashboard-page">
        <section className="empty-panel">
          <p className="eyebrow">Compte requis</p>
          <h3>Connecte-toi pour retrouver ton espace personnel StudentHub.</h3>
          <button className="primary-button" onClick={() => onNavigate('auth')}>
            Ouvrir la connexion
          </button>
        </section>
      </main>
    )
  }

  return (
    <main className="dashboard-page">
      <AppPageHeader
        eyebrow="Accueil"
        title={`Bonjour ${user.name || 'etudiant'}`}
        description="Retrouve ton avancement, tes prochaines actions et les derniers elements utiles sans naviguer partout."
        actions={
          <>
            <button className="primary-button" onClick={() => onNavigate('search')}>
              Nouvelle recherche
            </button>
            <button className="secondary-button" onClick={() => onNavigate('profile')}>
              Mon profil
            </button>
          </>
        }
        stats={[
          { label: 'Profil', value: `${profileCompletion}%`, tone: 'tone-blue' },
          { label: 'Favoris', value: favorites.length, tone: 'tone-green' },
          { label: 'Candidatures', value: activeApplications, tone: 'tone-yellow' },
          { label: 'CV generes', value: drafts.length },
        ]}
      />

      <section className="dashboard-grid">
        <div className="dashboard-main-column">
          <section className="home-highlight-grid">
            <article className="home-highlight-card">
              <p className="eyebrow">Profil</p>
              <h3>{profileCompletion}% complete</h3>
              <p>Plus ton profil est propre, plus les generations CV et les questions d’entretien deviennent fiables.</p>
            </article>
            <article className="home-highlight-card">
              <p className="eyebrow">Shortlist</p>
              <h3>{favorites.length} offre{favorites.length > 1 ? 's' : ''} en favoris</h3>
              <p>Garde seulement les offres qui meritent une candidature ou un CV cible.</p>
            </article>
            <article className="home-highlight-card">
              <p className="eyebrow">Pipeline</p>
              <h3>{activeApplications} candidature{activeApplications > 1 ? 's' : ''} active{activeApplications > 1 ? 's' : ''}</h3>
              <p>Ton espace perso sert surtout a transformer une recherche en vraies actions concretes.</p>
            </article>
          </section>

          <section className="panel-shell">
            <div className="panel-head">
              <div>
                <p className="eyebrow">Prochaines actions</p>
                <h2>Le plus utile maintenant</h2>
              </div>
            </div>
            <div className="ops-stack">
              {nextActions.map((action) => (
                <article key={action.title} className="candidate-brief-card">
                  <p className="eyebrow">Action</p>
                  <h3>{action.title}</h3>
                  <p>{action.copy}</p>
                  <div className="cv-panel-actions">
                    <button className="primary-button" onClick={() => onNavigate(action.page)}>
                      {action.cta}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="panel-shell">
            <div className="panel-head">
              <div>
                <p className="eyebrow">Recents</p>
                <h2>Derniers elements</h2>
              </div>
            </div>
            <div className="candidate-brief-grid">
              <article className="candidate-brief-card">
                <p className="eyebrow">Derniere offre aimee</p>
                <h3>{nextFavorite?.job_title || 'Aucune offre sauvegardee'}</h3>
                <p>{nextFavorite ? `${nextFavorite.company_name || 'Entreprise'} - ${nextFavorite.location || 'Lieu a verifier'}` : 'Sauvegarde une offre depuis la recherche pour commencer ta shortlist.'}</p>
              </article>
              <article className="candidate-brief-card">
                <p className="eyebrow">Dernier draft</p>
                <h3>{latestDraft?.target_title || 'Aucun CV genere'}</h3>
                <p>{latestDraft ? `${latestDraft.target_company || 'Entreprise'} - ${latestDraft.template_slug}` : 'Genere un premier CV cible depuis une offre ou tes favoris.'}</p>
              </article>
            </div>
          </section>
        </div>

        <aside className="dashboard-side-column">
          <section className="panel-shell">
            <div className="panel-head">
              <div>
                <p className="eyebrow">Compte</p>
                <h2>Ton espace</h2>
              </div>
            </div>
            <div className="cv-preview-stack">
              <div className="cv-match-block">
                <span>Nom</span>
                <strong>{user.name || 'Mon compte'}</strong>
              </div>
              <div className="cv-match-block">
                <span>Email</span>
                <strong>{user.email}</strong>
              </div>
              <div className="cv-match-block">
                <span>Cap actuel</span>
                <strong>{(profile?.target_roles || []).slice(0, 2).join(', ') || 'A definir'}</strong>
              </div>
            </div>
          </section>
        </aside>
      </section>
    </main>
  )
}
