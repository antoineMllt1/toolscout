import { useAuth } from '../context/AuthContext'

const PAGE_META = {
  home: { label: 'Accueil', title: 'Mon espace etudiant', subtitle: 'Vue d’ensemble de ta progression, de tes favoris et de tes prochaines actions.' },
  profile: { label: 'Profil', title: 'Base candidat', subtitle: 'Toutes les informations que StudentHub reutilise pour tes CV et tes entretiens.' },
  search: { label: 'Recherche', title: 'Trouver des offres', subtitle: 'Recherche, qualification et passage rapide vers favoris, CV ou candidature.' },
  favorites: { label: 'Favoris', title: 'Shortlist', subtitle: 'Les offres qui meritent une vraie candidature ou un CV cible.' },
  cv: { label: 'CV Studio', title: 'Production de documents', subtitle: 'Generation de CV cibles, drafts et export PDF.' },
  dashboard: { label: 'Candidatures', title: 'Pipeline candidatures', subtitle: 'Suivi simple des candidatures en cours, envoyees et en entretien.' },
  interview: { label: 'Entretien', title: 'Preparation', subtitle: 'Questions, histoires et repetition sur les candidatures actives.' },
  history: { label: 'Historique', title: 'Runs de recherche', subtitle: 'Retrouve les recherches precedentes et restaure leur contexte.' },
  ops: { label: 'Ops', title: 'Career ops', subtitle: 'Surfaces avancees et outils annexes.' },
}

export default function AppTopbar({ page, onNavigate }) {
  const { user } = useAuth()
  const meta = PAGE_META[page] || PAGE_META.search

  return (
    <header className="app-topbar">
      <div className="app-topbar-copy">
        <span className="app-topbar-label">{meta.label}</span>
        <h1>{meta.title}</h1>
        <p>{meta.subtitle}</p>
      </div>

      <div className="app-topbar-actions">
        {user ? (
          <>
            <button className="secondary-button" onClick={() => onNavigate('search')}>
              Nouvelle recherche
            </button>
            <button className="primary-button" onClick={() => onNavigate('cv')}>
              Generer un CV
            </button>
          </>
        ) : (
          <button className="primary-button" onClick={() => onNavigate('auth')}>
            Se connecter
          </button>
        )}
      </div>
    </header>
  )
}
