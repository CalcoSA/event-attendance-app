import { useCallback, useEffect, useRef, useState } from 'react'

export function useConnection() {
  const [connected, setConnected] = useState(navigator.onLine)
  const [checking, setChecking] = useState(false)
  const controllerRef = useRef<AbortController | null>(null)

  const check = useCallback(async () => {
    controllerRef.current?.abort()
    if (!navigator.onLine) {
      setConnected(false)
      setChecking(false)
      return
    }
    const controller = new AbortController()
    controllerRef.current = controller
    setChecking(true)
    const timeout = window.setTimeout(() => controller.abort('timeout'), 5000)
    try {
      const response = await fetch('/healthz', { cache: 'no-store', credentials: 'include', signal: controller.signal })
      if (controllerRef.current === controller) setConnected(response.ok)
    } catch {
      if (controllerRef.current === controller) setConnected(false)
    } finally {
      clearTimeout(timeout)
      if (controllerRef.current === controller) setChecking(false)
    }
  }, [])

  useEffect(() => {
    const offline = () => {
      controllerRef.current?.abort()
      controllerRef.current = null
      setConnected(false)
      setChecking(false)
    }
    const visible = () => { if (!document.hidden) void check() }
    void check()
    const interval = window.setInterval(() => { if (!document.hidden) void check() }, 15000)
    window.addEventListener('online', check)
    window.addEventListener('offline', offline)
    window.addEventListener('api-unavailable', check)
    document.addEventListener('visibilitychange', visible)
    return () => {
      clearInterval(interval)
      controllerRef.current?.abort()
      controllerRef.current = null
      window.removeEventListener('online', check)
      window.removeEventListener('offline', offline)
      window.removeEventListener('api-unavailable', check)
      document.removeEventListener('visibilitychange', visible)
    }
  }, [check])

  return { connected, checking, check }
}
