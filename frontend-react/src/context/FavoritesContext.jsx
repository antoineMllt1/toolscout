import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { useAuth } from './AuthContext'

const FavoritesContext = createContext(null)

function buildPayload(job, overrides = {}) {
  return {
    search_result_id: job?.id ?? overrides.search_result_id ?? null,
    job_url: overrides.job_url ?? job?.job_url ?? '',
    job_title: overrides.job_title ?? job?.job_title ?? '',
    company_name: overrides.company_name ?? job?.company_name ?? '',
    source: overrides.source ?? job?.source ?? '',
    location: overrides.location ?? job?.location ?? '',
    contract_type: overrides.contract_type ?? job?.contract_type ?? '',
    notes: overrides.notes ?? '',
    payload: overrides.payload ?? {
      normalized: job?.normalized ?? {},
      tool_context: job?.tool_context ?? [],
    },
  }
}

export function FavoritesProvider({ children }) {
  const { user, authFetch } = useAuth()
  const [favorites, setFavorites] = useState([])

  useEffect(() => {
    if (!user) {
      setFavorites([])
      return
    }
    void loadFavorites()
  }, [user])

  async function loadFavorites() {
    try {
      const response = await authFetch('/api/favorites/jobs')
      if (!response.ok) return
      setFavorites(await response.json())
    } catch (error) {
      console.error(error)
    }
  }

  async function saveFavorite(job, overrides = {}) {
    const payload = buildPayload(job, overrides)
    if (!payload.job_url) return null
    try {
      const response = await authFetch('/api/favorites/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!response.ok) return null
      const favorite = await response.json()
      setFavorites((prev) => {
        const exists = prev.find((item) => item.id === favorite.id || item.job_url === favorite.job_url)
        if (!exists) return [favorite, ...prev]
        return prev.map((item) => (item.id === exists.id ? favorite : item))
      })
      return favorite
    } catch (error) {
      console.error(error)
      return null
    }
  }

  async function updateFavorite(favoriteId, notes) {
    try {
      const response = await authFetch(`/api/favorites/jobs/${favoriteId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes }),
      })
      if (!response.ok) return null
      const favorite = await response.json()
      setFavorites((prev) => prev.map((item) => (item.id === favoriteId ? favorite : item)))
      return favorite
    } catch (error) {
      console.error(error)
      return null
    }
  }

  async function removeFavorite(favoriteOrId) {
    const favoriteId =
      typeof favoriteOrId === 'number'
        ? favoriteOrId
        : typeof favoriteOrId === 'string'
          ? byJobUrl[favoriteOrId]?.id
          : favoriteOrId?.id

    if (!favoriteId) return false
    try {
      const response = await authFetch(`/api/favorites/jobs/${favoriteId}`, { method: 'DELETE' })
      if (!response.ok) return false
      setFavorites((prev) => prev.filter((item) => item.id !== favoriteId))
      return true
    } catch (error) {
      console.error(error)
      return false
    }
  }

  async function toggleJobFavorite(job, overrides = {}) {
    const existing = byJobUrl[overrides.job_url ?? job?.job_url ?? '']
    if (existing) {
      await removeFavorite(existing.id)
      return null
    }
    return saveFavorite(job, overrides)
  }

  const byJobUrl = useMemo(
    () => Object.fromEntries(favorites.map((item) => [item.job_url, item])),
    [favorites],
  )

  const value = useMemo(() => ({
    favorites,
    byJobUrl,
    loadFavorites,
    saveFavorite,
    updateFavorite,
    removeFavorite,
    toggleJobFavorite,
  }), [favorites, byJobUrl, loadFavorites, saveFavorite, updateFavorite, removeFavorite, toggleJobFavorite])

  return <FavoritesContext.Provider value={value}>{children}</FavoritesContext.Provider>
}

export function useFavorites() {
  const context = useContext(FavoritesContext)
  if (!context) throw new Error('useFavorites must be used inside FavoritesProvider')
  return context
}
