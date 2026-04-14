/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { useAuth } from './AuthContext'

const AppCtx = createContext(null)

export function ApplicationProvider({ children }) {
  const { user, authFetch } = useAuth()
  const [applications, setApplications] = useState([])
  const [prepByApplicationId, setPrepByApplicationId] = useState({})

  useEffect(() => {
    if (user) {
      void load()
    } else {
      setApplications([])
      setPrepByApplicationId({})
    }
  }, [user])

  async function load() {
    try {
      const response = await authFetch('/api/applications')
      if (!response.ok) return
      const data = await response.json()
      setApplications(data)
      setPrepByApplicationId((prev) => {
        const next = { ...prev }
        for (const application of data) {
          next[application.id] = {
            prep: prev[application.id]?.prep || null,
            status: application.prep_status || null,
            updatedAt: application.prep_updated_at || null,
            isStale: Boolean(application.prep_is_stale),
            loading: false,
            error: '',
          }
        }
        return next
      })
    } catch (error) {
      console.error(error)
    }
  }

  async function saveJob(job) {
    try {
      const response = await authFetch('/api/applications', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_url: job.job_url,
          job_title: job.job_title,
          company_name: job.company_name,
          source: job.source,
          location: job.location,
          contract_type: job.contract_type,
          tool_context: job.tool_context || [],
          status: 'saved',
        }),
      })
      if (!response.ok) return null
      const application = await response.json()
      setApplications((prev) => {
        const exists = prev.find((item) => item.id === application.id)
        return exists
          ? prev.map((item) => item.id === application.id ? application : item)
          : [application, ...prev]
      })
      setPrepByApplicationId((prev) => ({
        ...prev,
        [application.id]: prev[application.id] || {
          prep: null,
          status: application.prep_status || null,
          updatedAt: application.prep_updated_at || null,
          isStale: Boolean(application.prep_is_stale),
          loading: false,
          error: '',
        },
      }))
      return application
    } catch {
      return null
    }
  }

  async function updateStatus(appId, status, notes) {
    try {
      const response = await authFetch(`/api/applications/${appId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, notes }),
      })
      if (!response.ok) return null
      const application = await response.json()
      setApplications((prev) => prev.map((item) => item.id === appId ? { ...item, ...application } : item))
      return application
    } catch {
      return null
    }
  }

  async function removeApplication(appId) {
    await authFetch(`/api/applications/${appId}`, { method: 'DELETE' })
    setApplications((prev) => prev.filter((item) => item.id !== appId))
    setPrepByApplicationId((prev) => {
      const next = { ...prev }
      delete next[appId]
      return next
    })
  }

  async function loadPrep(appId) {
    setPrepByApplicationId((prev) => ({
      ...prev,
      [appId]: {
        ...(prev[appId] || { prep: null, status: null, updatedAt: null, isStale: false }),
        loading: true,
        error: '',
      },
    }))
    try {
      const response = await authFetch(`/api/applications/${appId}/prep`)
      if (response.status === 404) {
        setPrepByApplicationId((prev) => ({
          ...prev,
          [appId]: {
            ...(prev[appId] || { prep: null }),
            prep: null,
            status: null,
            updatedAt: null,
            isStale: false,
            loading: false,
            error: '',
          },
        }))
        return null
      }
      if (!response.ok) return null
      const payload = await response.json()
      hydratePrep(payload)
      return payload
    } catch (error) {
      setPrepByApplicationId((prev) => ({
        ...prev,
        [appId]: {
          ...(prev[appId] || { prep: null }),
          loading: false,
          error: error.message || 'Unable to load prep',
        },
      }))
      return null
    }
  }

  async function generatePrep(appId) {
    setPrepByApplicationId((prev) => ({
      ...prev,
      [appId]: {
        ...(prev[appId] || { prep: null, status: null, updatedAt: null, isStale: false }),
        loading: true,
        error: '',
      },
    }))
    try {
      const response = await authFetch(`/api/applications/${appId}/prep/generate`, { method: 'POST' })
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}))
        throw new Error(payload.detail || 'Unable to generate prep')
      }
      const payload = await response.json()
      hydratePrep(payload)
      return payload
    } catch (error) {
      setPrepByApplicationId((prev) => ({
        ...prev,
        [appId]: {
          ...(prev[appId] || { prep: null }),
          loading: false,
          error: error.message || 'Unable to generate prep',
        },
      }))
      return null
    }
  }

  function hydratePrep(payload) {
    const applicationId = payload?.application?.id
    const prep = payload?.prep
    if (!applicationId || !prep) return
    setPrepByApplicationId((prev) => ({
      ...prev,
      [applicationId]: {
        prep,
        status: prep.status || null,
        updatedAt: prep.updated_at || null,
        isStale: Boolean(prep.is_stale),
        loading: false,
        error: '',
      },
    }))
    setApplications((prev) => prev.map((item) => item.id === applicationId ? {
      ...item,
      has_prep: true,
      prep_status: prep.status || 'ready',
      prep_updated_at: prep.updated_at || null,
      prep_is_stale: Boolean(prep.is_stale),
    } : item))
  }

  const byUrl = useMemo(
    () => Object.fromEntries(applications.map((item) => [item.job_url, item])),
    [applications],
  )

  return (
    <AppCtx.Provider
      value={{
        applications,
        byUrl,
        prepByApplicationId,
        saveJob,
        updateStatus,
        removeApplication,
        loadPrep,
        generatePrep,
        reload: load,
      }}
    >
      {children}
    </AppCtx.Provider>
  )
}

export function useApplications() {
  return useContext(AppCtx)
}
