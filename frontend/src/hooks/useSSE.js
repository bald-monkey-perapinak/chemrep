import { useEffect, useRef, useState, useCallback } from 'react'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

/**
 * useSSE — подписка на SSE-поток событий урока.
 *
 * @param {string|null} lessonId  — UUID урока (null = не подписываться)
 * @returns {{ events, status, lastEvent, clear }}
 *
 * events    — массив всех событий с начала подписки
 * status    — 'connecting' | 'connected' | 'disconnected' | 'error'
 * lastEvent — последнее полученное событие
 * clear     — очистить список событий
 */
export function useSSE(lessonId) {
  const [events,    setEvents]    = useState([])
  const [status,    setStatus]    = useState('disconnected')
  const [lastEvent, setLastEvent] = useState(null)
  const esRef = useRef(null)

  const clear = useCallback(() => setEvents([]), [])

  useEffect(() => {
    if (!lessonId) return

    const token = localStorage.getItem('token')
    if (!token) return

    const url = `${BASE}/sse/lessons/${lessonId}?token=${encodeURIComponent(token)}`

    const es = new EventSource(url)
    esRef.current = es

    es.onopen = () => setStatus('connected')

    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data)
        if (event.kind === 'heartbeat') return  // не добавляем в список
        setLastEvent(event)
        setEvents(prev => [...prev, event])
      } catch {
        // ignore malformed events
      }
    }

    es.onerror = () => {
      setStatus('error')
      es.close()
      esRef.current = null
    }

    return () => {
      es.close()
      esRef.current = null
      setStatus('disconnected')
    }
  }, [lessonId])

  return { events, status, lastEvent, clear }
}
