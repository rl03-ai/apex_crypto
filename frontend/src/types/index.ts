// ── Scanner / Assets ─────────────────────────────────────────────────────────
export interface CryptoAsset {
  id: string
  symbol: string
  name: string
  image?: string
  price: number
  market_cap: number
  rank: number
  volume_24h: number
  change_24h: number
  change_7d: number
  change_30d: number
  ath_change: number
  sparkline_7d: number[]
  // score dims
  adoption: number
  quality: number
  valuation: number
  market: number
  catalysts: number
  risk: number
  total_score: number
  priority_score: number
  state: 'confirming' | 'watchlist' | 'avoid' | string
  why_selected: string[]
}

export interface ChartPoint {
  date: number | string
  price: number
}

// ── Market ────────────────────────────────────────────────────────────────────
export interface FearGreed {
  value: number
  label: string
  timestamp: string | null
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface UserOut {
  id: string
  email: string
  name: string
}

// ── Watchlist ─────────────────────────────────────────────────────────────────
export interface WatchlistEntry {
  id: string
  coin_id: string
  symbol: string
  name: string
  notes: string | null
  alert_price_above: number | null
  alert_price_below: number | null
  alert_score_above: number | null
  added_at: string
}

export interface WatchlistEnriched extends WatchlistEntry,
  Partial<Omit<CryptoAsset, 'id' | 'symbol' | 'name'>> {
  watchlist_id: string
}

// ── Portfolio ─────────────────────────────────────────────────────────────────
export interface Portfolio {
  id: string
  name: string
  base_currency: string
  created_at: string
}

export interface Position {
  id: string
  portfolio_id: string
  coin_id: string
  symbol: string
  name: string
  status: string
  first_buy_date: string
  avg_cost: number
  quantity: number
  invested_amount: number
  current_price: number | null
  current_value: number | null
  pnl: number | null
  pnl_pct: number | null
  last_refreshed_at: string | null
  exchange: string | null
  horizon: string | null
  thesis: string | null
  target_price: number | null
  stop_loss: number | null
  created_at: string
}

export interface PortfolioSummary {
  portfolio: Portfolio
  positions: Position[]
  total_invested: number
  total_value: number
  total_pnl: number
  total_pnl_pct: number
}

// ── Alerts ────────────────────────────────────────────────────────────────────
export interface Alert {
  id: string
  alert_type: string
  severity: string
  coin_id: string | null
  title: string
  message: string
  is_read: boolean
  created_at: string
}

// ── Asset Detail (enriquecido) ────────────────────────────────────────────────
export interface Tokenomics {
  circulating_supply: number | null
  total_supply: number | null
  max_supply: number | null
  circulating_pct: number | null   // % do max supply
  fdv: number | null
  fdv_ratio: number | null         // FDV / Market Cap
  genesis_date: string | null
}

export interface AthAtl {
  ath: number | null
  ath_date: string | null
  ath_change_pct: number | null
  atl: number | null
  atl_date: string | null
  atl_change_pct: number | null
}

export interface Community {
  reddit_subscribers: number | null
  twitter_followers: number | null
  telegram_user_count: number | null
}

export interface AssetLinks {
  homepage: string | null
  blockchain_site: string | null
  subreddit: string | null
  twitter: string | null
}

export interface TvlData {
  tvl: number | null
  tvl_1d_change: number | null
  tvl_7d_change: number | null
  kind: 'protocol' | 'chain'
  slug: string
  source: string
}

export interface AssetDetail extends CryptoAsset {
  categories: string[]
  description: string
  tokenomics: Tokenomics
  ath_atl: AthAtl
  community: Community
  links: AssetLinks
  tvl: TvlData | null
}

// ── Search ────────────────────────────────────────────────────────────────────
export interface SearchResult {
  id: string
  symbol: string
  name: string
  thumb: string | null
  market_cap_rank: number | null
}
