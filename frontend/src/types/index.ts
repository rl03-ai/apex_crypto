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
  technical: Technical | null
}

// ── Search ────────────────────────────────────────────────────────────────────
export interface SearchResult {
  id: string
  symbol: string
  name: string
  thumb: string | null
  market_cap_rank: number | null
}

// ── Technical Analysis ────────────────────────────────────────────────────────
export interface Technical {
  trend: 'uptrend' | 'downtrend' | 'range'
  rsi: number | null
  rsi_zone: 'oversold' | 'neutral' | 'overbought'
  adx: number | null
  adx_strength: 'weak' | 'moderate' | 'strong'
  di_plus: number | null
  di_minus: number | null
  bb_width: number | null
  bb_position: number | null     // 0..100, posição entre lower e upper band
  supertrend: 'up' | 'down'
  donchian: 'up' | 'down' | 'flat'
  swing_lows: number[]
  swing_highs: number[]
  bull_signals: number           // 0-4
}

// ── InstDash analysis ─────────────────────────────────────────────────────────
export interface InstDashStructure {
  last_hh: number | null
  prev_hh: number | null
  last_ll: number | null
  prev_ll: number | null
  choch_bull: boolean
  choch_bear: boolean
  bos_bull: boolean
  bos_bear: boolean
  struct_bias: number   // -1, 0, 1
  last_event: string
  event_bars_ago: number | null
}

export interface InstDashFvg {
  bull_top: number | null
  bull_bot: number | null
  bear_top: number | null
  bear_bot: number | null
  in_bull_fvg: boolean
  in_bear_fvg: boolean
}

export interface InstDashOb {
  bull_top: number | null
  bull_bot: number | null
  bear_top: number | null
  bear_bot: number | null
  in_bull_ob: boolean
  in_bear_ob: boolean
}

export interface InstDashLiq {
  sweep_high: boolean
  sweep_low: boolean
  liq_high: number | null
  liq_low: number | null
  near_liq_high: boolean
  near_liq_low: boolean
}

export interface InstDashSr {
  res_top: number | null; res_mid: number | null; res_bot: number | null
  sup_top: number | null; sup_mid: number | null; sup_bot: number | null
  dist_to_res_pct: number | null
  dist_to_sup_pct: number | null
  near_res: boolean
  near_sup: boolean
}

export interface InstDashVp {
  poc: number | null
  vah: number | null
  val: number | null
  above_poc: boolean
  in_value_area: boolean
  above_value_area: boolean
  below_value_area: boolean
}

export interface InstDashAnalysis {
  symbol: string
  interval: string
  htf_interval: string
  last_close_at: string

  price: number
  change_24h_pct: number

  rsi: number
  macd_bullish: boolean
  atr_pct: number
  adx: number | null
  di_plus: number | null
  di_minus: number | null
  vol_ratio: number
  delta_volume: number

  ltf_trend: string
  htf_trend: string
  aligned_bull: boolean
  aligned_bear: boolean

  score: number
  score_pct: number
  signal: string
  factors: Record<string, number>

  setup_quality: string
  setup_blocked_by: string
  sl_long: number; tp_long: number
  sl_short: number; tp_short: number

  bb_basis: number; bb_upper: number; bb_lower: number
  squeeze: boolean

  vwap: number | null
  above_vwap: boolean
  vwap_ext_up: boolean
  vwap_ext_dn: boolean

  structure: InstDashStructure
  fvg: InstDashFvg
  order_block: InstDashOb
  liquidity: InstDashLiq
  support_resistance: InstDashSr
  volume_profile: InstDashVp
}

// ── Signal ────────────────────────────────────────────────────────────────────
export interface Signal {
  id: string
  symbol: string
  coin_id: string | null
  interval: string
  direction: 'long' | 'short' | 'exit' | string
  setup_type: string
  score: number
  signal_label: string
  price: number
  sl: number | null
  tp: number | null
  title: string
  description: string
  is_active: boolean
  detected_at: string
  expires_at: string | null
}
