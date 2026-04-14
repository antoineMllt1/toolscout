/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect } from 'react'

const AuthContext = createContext(null)

async function readResponsePayload(response) {
  const text = await response.text()
  if (!text) return null

  try {
    return JSON.parse(text)
  } catch {
    return { detail: text }
  }
}

function buildAuthError(response, payload, fallbackMessage) {
  if (payload?.detail) return payload.detail
  if (response.status === 502 || response.status === 503 || response.status === 504) {
    return 'Backend unreachable. Start the API on http://127.0.0.1:8000 and retry.'
  }
  if (response.status >= 500) {
    return 'Server error. Check the backend logs and retry.'
  }
  return fallbackMessage
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(() => localStorage.getItem('ts_token') || '')
  const [loading, setLoading] = useState(() => Boolean(localStorage.getItem('ts_token') || ''))

  // Fetch current user on mount
  useEffect(() => {
    if (!token) return
    fetch('/api/auth/me', { headers: { Authorization: `Bearer ${token}` } })
      .then(async (response) => {
        const payload = await readResponsePayload(response)
        return response.ok ? payload : null
      })
      .then((u) => { setUser(u); setLoading(false) })
      .catch(() => { setLoading(false) })
  }, [token])

  function authFetch(url, opts = {}) {
    return fetch(url, {
      ...opts,
      headers: { ...(opts.headers || {}), Authorization: `Bearer ${token}` },
    })
  }

  async function login(email, password) {
    let response
    try {
      response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
    } catch {
      throw new Error('Unable to reach the backend. Start the API on http://127.0.0.1:8000.')
    }

    const data = await readResponsePayload(response)
    if (!response.ok) {
      throw new Error(buildAuthError(response, data, 'Login failed'))
    }
    if (!data?.token || !data?.user) {
      throw new Error('Unexpected server response during login.')
    }

    localStorage.setItem('ts_token', data.token)
    setToken(data.token)
    setUser(data.user)
    return data.user
  }

  async function register(email, password, name) {
    let response
    try {
      response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, name }),
      })
    } catch {
      throw new Error('Unable to reach the backend. Start the API on http://127.0.0.1:8000.')
    }

    const data = await readResponsePayload(response)
    if (!response.ok) {
      throw new Error(buildAuthError(response, data, 'Registration failed'))
    }
    if (!data?.token || !data?.user) {
      throw new Error('Unexpected server response during registration.')
    }

    localStorage.setItem('ts_token', data.token)
    setToken(data.token)
    setUser(data.user)
    return data.user
  }

  function logout() {
    localStorage.removeItem('ts_token')
    setToken('')
    setUser(null)
    setLoading(false)
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, authFetch }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
