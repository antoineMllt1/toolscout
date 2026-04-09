import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { useAuth } from './AuthContext'

const AppCtx = createContext(null)

export function ApplicationProvider({ children }) {
  const { user, authFetch } = useAuth()
  const [applications, setApplications] = useState([])
  const [byUrl, setByUrl] = useState({})  // job_url → application

  // Reload when user changes
  useEffect(() => {
    if (user) load()
    else { setApplications([]); setByUrl({}) }
  }, [user])

  async function load() {
    try {
      const r = await authFetch('/api/applications')
      if (!r.ok) return
      const data = await r.json()
      setApplications(data)
      setByUrl(Object.fromEntries(data.map(a => [a.job_url, a])))
    } catch (e) { console.error(e) }
  }

  async function saveJob(job) {
    try {
      const r = await authFetch('/api/applications', {
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
      if (!r.ok) return null
      const app = await r.json()
      setApplications(prev => {
        const exists = prev.find(a => a.id === app.id)
        return exists ? prev.map(a => a.id === app.id ? app : a) : [app, ...prev]
      })
      setByUrl(prev => ({ ...prev, [app.job_url]: app }))
      return app
    } catch (e) { return null }
  }

  async function updateStatus(appId, status, notes) {
    try {
      const r = await authFetch(`/api/applications/${appId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, notes }),
      })
      if (!r.ok) return null
      const app = await r.json()
      setApplications(prev => prev.map(a => a.id === appId ? app : a))
      setByUrl(prev => ({ ...prev, [app.job_url]: app }))
      return app
    } catch (e) { return null }
  }

  async function removeApplication(appId) {
    await authFetch(`/api/applications/${appId}`, { method: 'DELETE' })
    setApplications(prev => {
      const removed = prev.find(a => a.id === appId)
      if (removed) setByUrl(p => { const n = { ...p }; delete n[removed.job_url]; return n })
      return prev.filter(a => a.id !== appId)
    })
  }

  return (
    <AppCtx.Provider value={{ applications, byUrl, saveJob, updateStatus, removeApplication, reload: load }}>
      {children}
    </AppCtx.Provider>
  )
}

export function useApplications() {
  return useContext(AppCtx)
}
