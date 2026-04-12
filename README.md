# ToolScout

Découvrez quelles entreprises utilisent un outil SaaS en scrappant les offres d'emploi françaises en temps réel.

## Sources scrappées

| Source | Méthode | Commentaire |
|--------|---------|------------|
| **Welcome to the Jungle** | Algolia API (public) | Rapide, pas de protection |
| **LinkedIn** | HTML public | Pas d'auth requise |
| **Indeed France** | Playwright + cookies CF | Nécessite `cf_clearance` |
| **Jobteaser** | Playwright + cookies CF | Nécessite `cf_clearance` |

## Prérequis

- **Python 3.11+**
- **Node.js 18+** (pour le frontend React)
- **Playwright Chromium** : `playwright install chromium`

## Démarrage rapide

```bash
# Double-cliquer sur start.bat (Windows)
```

Ou manuellement :

```bash
# 1. Backend Python
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# 2. Frontend React (dev)
cd frontend-react
npm install
npm run dev          # http://127.0.0.1:5173 avec proxy vers le backend

# 2b. Ou build production (intégré au backend)
cd frontend-react
npm run build        # → frontend/ (servi par FastAPI sur port 8000)
```

Ouvrir **http://127.0.0.1:8000**

## Structure

```
saas_keywords/
├── backend/
│   ├── main.py              # FastAPI + SSE streaming
│   ├── database.py          # SQLite (aiosqlite)
│   ├── models.py
│   ├── requirements.txt
│   └── scrapers/
│       ├── base.py          # BaseScraper + extract_tool_context()
│       ├── wttj.py          # Welcome to the Jungle (Algolia)
│       ├── linkedin.py      # LinkedIn (HTML public)
│       ├── indeed.py        # Indeed France (Playwright)
│       └── jobteaser.py     # Jobteaser (Playwright)
├── frontend/                # Build React (généré par `npm run build`)
├── frontend-react/          # Sources React + Vite + Tailwind
│   └── src/
│       ├── pages/
│       │   ├── SearchPage.jsx   # Recherche + SSE + filtres
│       │   └── HistoryPage.jsx  # Historique
│       └── components/
│           ├── Navbar.jsx
│           ├── JobCard.jsx
│           └── FilterBar.jsx
└── start.bat                # Lancer tout en une commande (Windows)
```

## API

| Méthode | URL | Description |
|---------|-----|-------------|
| `POST` | `/api/search` | Lancer une recherche `{"tool_name": "n8n"}` |
| `GET` | `/api/search/{id}/stream` | SSE — résultats en temps réel |
| `GET` | `/api/search/{id}/results` | Tous les résultats |
| `GET` | `/api/history` | 100 dernières recherches |
| `DELETE` | `/api/history/{id}` | Supprimer une recherche |
| `GET` | `/api/stats` | Statistiques globales |
| `POST` | `/api/config/cookies` | Mettre à jour les cookies CF |

## Mettre à jour les cookies Cloudflare

Indeed et Jobteaser sont protégés par Cloudflare. Les cookies `cf_clearance` expirent au bout de quelques jours.

Pour les renouveler :
1. Ouvrir le site (Indeed ou Jobteaser) dans Chrome
2. DevTools → Application → Cookies → copier `cf_clearance`
3. Mettre à jour dans `backend/main.py` dans le dict `COOKIES`

Ou via l'API :
```bash
curl -X POST http://127.0.0.1:8000/api/config/cookies \
  -H "Content-Type: application/json" \
  -d '{"source": "indeed", "cookies": {"cf_clearance": "VALEUR"}}'
```

## Filtres disponibles

Dans l'interface React, vous pouvez filtrer par :
- **Source** (WTTJ, LinkedIn, Indeed, Jobteaser)
- **Type de contrat** (CDI, Stage, Alternance…)
- **Lieu**
- **Tri** (plus récent, entreprise A→Z, titre A→Z)

Cliquer sur une offre ouvre l'offre originale dans un nouvel onglet.
