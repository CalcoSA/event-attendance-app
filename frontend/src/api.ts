import type { AttendanceSummary } from './types'

export class ApiError extends Error {
  status: number
  attendance?: AttendanceSummary

  constructor(message: string, status: number, attendance?: AttendanceSummary) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.attendance = attendance
  }
}

export const isAbort = (error: unknown) => error instanceof DOMException && error.name === 'AbortError'

export const messageOf = (error: unknown) => error instanceof Error ? error.message : 'No fue posible completar la operación. Intenta nuevamente.'

async function request<T>(path: string, options: RequestInit, readResponse: (response: Response) => Promise<T>, timeoutMs: number): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body) headers.set('Content-Type', 'application/json')
  if (options.method && options.method !== 'GET') headers.set('X-Requested-With', 'XMLHttpRequest')
  const controller = new AbortController()
  let timedOut = false
  const abort = () => controller.abort()
  if (options.signal?.aborted) controller.abort()
  else options.signal?.addEventListener('abort', abort, { once: true })
  const timeout = window.setTimeout(() => { timedOut = true; controller.abort() }, timeoutMs)
  try {
    const response = await fetch(path, { ...options, headers, credentials: 'include', cache: 'no-store', signal: controller.signal })
    if (response.ok) return await readResponse(response)
    if (response.status === 401 && path !== '/api/auth/login') window.dispatchEvent(new Event('session-expired'))
    if (response.status >= 500) window.dispatchEvent(new Event('api-unavailable'))
    const body: unknown = await response.json().catch(error => { if (isAbort(error)) throw error; return null })
    let detail = response.status === 401 ? 'La sesión terminó. Ingresa nuevamente.' : 'No fue posible completar la operación. Intenta nuevamente.'
    let attendance: AttendanceSummary | undefined
    if (body && typeof body === 'object' && 'detail' in body) {
      if (typeof body.detail === 'string') detail = body.detail
      else if (Array.isArray(body.detail)) detail = 'Revisa los datos seleccionados e intenta nuevamente.'
    }
    if (body && typeof body === 'object' && 'attendance' in body) attendance = body.attendance as AttendanceSummary
    throw new ApiError(detail, response.status, attendance)
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (isAbort(error) && !timedOut) throw error
    window.dispatchEvent(new Event('api-unavailable'))
    throw new ApiError(timedOut ? 'El servidor tardó demasiado en responder. Revisa la conexión e intenta nuevamente.' : 'No fue posible conectar con el servidor. Revisa la conexión e intenta nuevamente.', 0)
  } finally {
    window.clearTimeout(timeout)
    options.signal?.removeEventListener('abort', abort)
  }
}

export function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  return request(path, options, response => response.json() as Promise<T>, 20000)
}

export function apiDownload(path: string): Promise<{ blob: Blob; disposition: string }> {
  return request(path, {}, async response => ({ blob: await response.blob(), disposition: response.headers.get('Content-Disposition') ?? '' }), 60000)
}
