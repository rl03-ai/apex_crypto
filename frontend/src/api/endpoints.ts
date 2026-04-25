import { api, setToken } from './client'
import type {
  Alert, AssetDetail, ChartPoint, CryptoAsset, FearGreed,
  Portfolio, PortfolioSummary, Position,
  SearchResult,
  TokenResponse, UserOut,
  WatchlistEnriched, WatchlistEntry,
} from '../types'

// ── Auth ──────────────────────────────────────────────────────────────────────
export const register = (email: string, name: string, password: string) =>
  api.post<TokenResponse>('/auth/register', { email, name, password })
    .then(r => { setToken(r.access_token); return r })

export const login = (email: string, password: string) =>
  api.post<TokenResponse>('/auth/login', { email, password })
    .then(r => { setToken(r.access_token); return r })

export const fetchMe = () => api.get<UserOut>('/auth/me')

// ── Crypto Scanner ────────────────────────────────────────────────────────────
export const fetchScanner    = (limit = 80)   => api.get<CryptoAsset[]>(`/crypto/scanner?limit=${limit}`)
export const fetchAsset      = (id: string)   => api.get<CryptoAsset>(`/crypto/asset/${id}`)
export const fetchDetail     = (id: string)   => api.get<AssetDetail>(`/crypto/detail/${id}`)
export const fetchChart      = (id: string, days = 90) => api.get<ChartPoint[]>(`/crypto/chart/${id}?days=${days}`)
export const searchCoins     = (q: string, limit = 15) =>
  api.get<SearchResult[]>(`/crypto/search?q=${encodeURIComponent(q)}&limit=${limit}`)

// ── Market ────────────────────────────────────────────────────────────────────
export const fetchFearGreed  = ()             => api.get<FearGreed>('/market/fear-greed')

// ── Watchlist ─────────────────────────────────────────────────────────────────
export const fetchWatchlist         = ()              => api.get<WatchlistEntry[]>('/watchlist')
export const fetchWatchlistEnriched = ()              => api.get<WatchlistEnriched[]>('/watchlist/enriched')
export const addToWatchlist         = (coin_id: string, symbol: string, name: string) =>
  api.post<WatchlistEntry>('/watchlist', { coin_id, symbol, name })
export const updateWatchlistEntry   = (id: string, body: Partial<WatchlistEntry>) =>
  api.put<WatchlistEntry>(`/watchlist/${id}`, body)
export const removeFromWatchlist    = (id: string) => api.delete<void>(`/watchlist/${id}`)

// ── Portfolios ────────────────────────────────────────────────────────────────
export const fetchPortfolios    = ()              => api.get<Portfolio[]>('/portfolios')
export const createPortfolio    = (name: string)  => api.post<Portfolio>('/portfolios', { name })
export const fetchPortfolio     = (id: string)    => api.get<PortfolioSummary>(`/portfolios/${id}`)
export const refreshPortfolio   = (id: string)    => api.post<unknown>(`/portfolios/${id}/refresh`)
export const deletePortfolio    = (id: string)    => api.delete<void>(`/portfolios/${id}`)

export const fetchPositions     = (portfolioId: string) =>
  api.get<Position[]>(`/portfolios/${portfolioId}/positions`)
export const createPosition     = (portfolioId: string, body: object) =>
  api.post<Position>(`/portfolios/${portfolioId}/positions`, body)
export const updatePosition     = (portfolioId: string, posId: string, body: object) =>
  api.put<Position>(`/portfolios/${portfolioId}/positions/${posId}`, body)
export const deletePosition     = (portfolioId: string, posId: string) =>
  api.delete<void>(`/portfolios/${portfolioId}/positions/${posId}`)
export const addLot             = (portfolioId: string, posId: string, body: object) =>
  api.post<unknown>(`/portfolios/${portfolioId}/positions/${posId}/lots`, body)

// ── Alerts ────────────────────────────────────────────────────────────────────
export const fetchAlerts    = (all = false) => api.get<Alert[]>(`/alerts${all ? '?all=true' : ''}`)
export const markRead       = (id: string)  => api.post<Alert>(`/alerts/${id}/read`)
export const markAllRead    = ()            => api.post<unknown>('/alerts/read-all')
export const deleteAlert    = (id: string)  => api.delete<void>(`/alerts/${id}`)
