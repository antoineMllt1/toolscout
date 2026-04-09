import {
  createContext,
  startTransition,
  useCallback,
  useContext,
  useEffect,
  useEffectEvent,
  useMemo,
  useRef,
  useState,
} from 'react'

const SearchContext = createContext(null)
const STORAGE_KEY = 'ts_active_search_v2'

function parseStoredSearch() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function serializeSearchSnapshot(state) {
  return JSON.stringify({
    searchId: state.searchId,
    tool: state.tool,
    status: state.status,
    selectedResultId: state.selectedResultId,
  })
}

function decodeResult(result) {
  if (!result) return result
  if (!Array.isArray(result.tool_context)) {
    try {
      result.tool_context = JSON.parse(result.tool_context || '[]')
    } catch {
      result.tool_context = []
    }
  }
  return result
}

export function SearchProvider({ children }) {
  const [state, setState] = useState({
    tool: '',
    searchId: null,
    status: 'idle',
    results: [],
    total: 0,
    sourcesDone: [],
    selectedResultId: null,
    error: '',
    loadedAt: null,
  })
  const eventSourceRef = useRef(null)
  const bootedRef = useRef(false)

  const persistState = useEffectEvent((nextState) => {
    try {
      if (!nextState.searchId) {
        localStorage.removeItem(STORAGE_KEY)
        return
      }
      localStorage.setItem(STORAGE_KEY, serializeSearchSnapshot(nextState))
    } catch {
      // ignore localStorage failures
    }
  })

  const closeStream = useEffectEvent(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
  })

  const subscribeToSearch = useEffectEvent((searchId) => {
    closeStream()
    const source = new EventSource(`/api/search/${searchId}/stream`)
    eventSourceRef.current = source

    source.onmessage = (event) => {
      const message = JSON.parse(event.data)

      if (message.type === 'result') {
        const incoming = decodeResult(message.data)
        setState((prev) => {
          if (prev.results.some((item) => item.id === incoming.id)) return prev
          const next = {
            ...prev,
            results: [...prev.results, incoming],
            selectedResultId: prev.selectedResultId ?? incoming.id,
          }
          persistState(next)
          return next
        })
      }

      if (message.type === 'status') {
        setState((prev) => {
          const next = {
            ...prev,
            status: message.status || prev.status,
            total: message.total || 0,
            sourcesDone: (message.sources_done || '').split(',').filter(Boolean),
          }
          persistState(next)
          return next
        })
      }

      if (message.type === 'done') {
        setState((prev) => {
          const next = {
            ...prev,
            status: 'completed',
            total: message.total || prev.total,
            loadedAt: new Date().toISOString(),
          }
          persistState(next)
          return next
        })
        closeStream()
      }
    }

    source.onerror = () => {
      setState((prev) => {
        const next = {
          ...prev,
          status: prev.status === 'idle' ? 'error' : prev.status,
        }
        persistState(next)
        return next
      })
      closeStream()
    }
  })

  const hydrateSearch = useEffectEvent(async (searchId, options = {}) => {
    try {
      const response = await fetch(`/api/search/${searchId}/results`)
      if (!response.ok) throw new Error('Unable to restore search')
      const payload = await response.json()
      const results = (payload.results || []).map(decodeResult)
      const nextState = {
        tool: options.keepTool ? state.tool : payload.search.tool_name,
        searchId: payload.search.id,
        status: payload.search.status,
        results,
        total: payload.search.total_results || results.length,
        sourcesDone: (payload.search.sources_done || '').split(',').filter(Boolean),
        selectedResultId:
          options.selectedResultId ||
          state.selectedResultId ||
          results[0]?.id ||
          null,
        error: '',
        loadedAt: new Date().toISOString(),
      }
      setState(nextState)
      persistState(nextState)
      if (payload.search.status !== 'completed') {
        subscribeToSearch(payload.search.id)
      } else {
        closeStream()
      }
    } catch (error) {
      setState((prev) => ({ ...prev, status: 'error', error: error.message }))
    }
  })

  useEffect(() => {
    if (bootedRef.current) return
    bootedRef.current = true
    const stored = parseStoredSearch()
    if (stored?.searchId) {
      hydrateSearch(stored.searchId, { selectedResultId: stored.selectedResultId })
    }
    return () => closeStream()
  }, [])

  const startSearch = useCallback(async (tool) => {
    const cleanTool = tool.trim()
    if (!cleanTool) return null

    closeStream()
    const optimisticState = {
      tool: cleanTool,
      searchId: null,
      status: 'running',
      results: [],
      total: 0,
      sourcesDone: [],
      selectedResultId: null,
      error: '',
      loadedAt: new Date().toISOString(),
    }
    setState(optimisticState)
    persistState(optimisticState)

    try {
      const response = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool_name: cleanTool }),
      })
      if (!response.ok) throw new Error('Search failed to start')
      const payload = await response.json()
      const nextState = {
        ...optimisticState,
        searchId: payload.search_id,
      }
      setState(nextState)
      persistState(nextState)
      subscribeToSearch(payload.search_id)
      return payload.search_id
    } catch (error) {
      setState((prev) => ({ ...prev, status: 'error', error: error.message }))
      return null
    }
  }, [])

  const openSearch = useCallback((searchId) => {
    startTransition(() => {
      hydrateSearch(searchId)
    })
  }, [])

  const clearSearch = useCallback(() => {
    closeStream()
    const nextState = {
      tool: '',
      searchId: null,
      status: 'idle',
      results: [],
      total: 0,
      sourcesDone: [],
      selectedResultId: null,
      error: '',
      loadedAt: null,
    }
    setState(nextState)
    persistState(nextState)
  }, [])

  const selectResult = useCallback((resultId) => {
    setState((prev) => {
      const next = { ...prev, selectedResultId: resultId }
      persistState(next)
      return next
    })
  }, [])

  const selectedResult = useMemo(
    () => state.results.find((result) => result.id === state.selectedResultId) || null,
    [state.results, state.selectedResultId],
  )

  const value = useMemo(() => ({
    ...state,
    selectedResult,
    isRunning: state.status === 'running',
    hasActiveSearch: Boolean(state.searchId),
    startSearch,
    openSearch,
    clearSearch,
    selectResult,
    restoreSearch: hydrateSearch,
  }), [state, selectedResult, startSearch, openSearch, clearSearch, selectResult])

  return <SearchContext.Provider value={value}>{children}</SearchContext.Provider>
}

export function useSearch() {
  const context = useContext(SearchContext)
  if (!context) throw new Error('useSearch must be used inside SearchProvider')
  return context
}
