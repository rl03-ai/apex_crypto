const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'

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
