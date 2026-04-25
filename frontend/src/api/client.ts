/**
 * Resolve a URL base do backend.
 *
 * Prioridade:
 *   1. VITE_API_BASE_URL (se definido na build)
 *   2. localhost:8001 quando o frontend corre em localhost (dev)
 *   3. Deriva do hostname: apex-crypto-terminal.onrender.com → apex-crypto-api.onrender.com
 *      (ou em geral: substitui "-terminal" por "-api" no hostname)
 *   4. Mesma origem (último recurso, pressupõe proxy)
 */
function resolveBase(): string {
  const fromEnv = import.meta.env.VITE_API_BASE_URL
  if (fromEnv) return fromEnv

  if (typeof window === 'undefined') return 'http://localhost:8001'

  const { hostname, protocol } = window.location

  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:8001'
  }

  if (hostname.includes('-terminal')) {
    return `${protocol}//${hostname.replace('-terminal', '-api')}`
  }

  return `${protocol}//${hostname}`
}

const BASE = resolveBase()

function token(): string {
  return localStorage.getItem('apex_token') || ''
}

function headers(extra: Record<string, string> = {}): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json', ...extra }
  const t = token()
  if (t) h['Authorization'] = `Bearer ${t}`
  return h
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: headers(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (res.status === 401) {
    // Token inválido ou expirado — limpa e redirecciona se não estamos já no login
    localStorage.removeItem('apex_token')
    if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
      window.location.href = '/login'
    }
    throw new Error('Sessão expirada — faz login novamente.')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
    throw new Error(err.detail || `API error ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  get:    <T>(path: string)                  => request<T>('GET',    path),
  post:   <T>(path: string, body?: unknown)  => request<T>('POST',   path, body),
  put:    <T>(path: string, body?: unknown)  => request<T>('PUT',    path, body),
  delete: <T>(path: string)                  => request<T>('DELETE', path),
}

export function setToken(t: string) { localStorage.setItem('apex_token', t) }
export function clearToken()        { localStorage.removeItem('apex_token')  }
export function hasToken(): boolean { return !!token() }
