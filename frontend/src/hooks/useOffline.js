import { useState, useEffect, useCallback } from 'react'

export function useOffline() {
  const [isOffline, setIsOffline] = useState(!navigator.onLine)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    const handleOnline = () => {
      setIsOffline(false)
      setRetryCount(0)
    }
    const handleOffline = () => setIsOffline(true)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  const retry = useCallback(() => {
    setRetryCount(c => c + 1)
    // Force a connectivity check
    fetch('/health', { method: 'HEAD', cache: 'no-store' })
      .then(() => setIsOffline(false))
      .catch(() => setIsOffline(true))
  }, [])

  return { isOffline, retryCount, retry }
}
