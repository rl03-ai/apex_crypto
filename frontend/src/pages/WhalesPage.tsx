import { useEffect, useMemo, useState } from 'react'
import { fetchWhales, type WhaleMetric } from '../api/endpoints'

export function WhalesPage() {
  const [whales, setWhales] = useState<WhaleMetric[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await fetchWhales()
      setWhales(res.data || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro desconhecido')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])

  // Aggregate stats
  const stats = useMemo(() => {
    const bullish = whales.filter(w => w.whale_score.score >= 2).length
    const bearish = whales.filter(w => w.whale_score.score <= -2).length
    const topBull = [...whales].sort((a, b) => b.whale_score.score - a.whale_score.score)[0]
    const topBear = [...whales].sort((a, b) => a.whale_score.score - b.whale_score.score)[0]
    return { bullish, bearish, topBull, topBear, total: whales.length }
  }, [whales])

  return (
    <div className="whale-page">
      {/* Header */}
      <div className="whale-header">
        <div>
          <span className="kicker">Smart money tracker</span>
          <h1>🐳 Whale Tracking</h1>
          <p>Open Interest · Funding Rate · Top trader positioning</p>
        </div>
        <button onClick={load} disabled={loading} className="whale-refresh">
          {loading ? '↻ Carregando...' : '↻ Recarregar'}
        </button>
      </div>

      {/* Aggregate stats */}
      {whales.length > 0 && (
        <div className="whale-stats">
          <div className="whale-stat-card">
            <span className="whale-stat-label">Tracked</span>
            <span className="whale-stat-value">{stats.total}</span>
          </div>
          <div className="whale-stat-card">
            <span className="whale-stat-label">Bullish</span>
            <span className="whale-stat-value bull">{stats.bullish}</span>
          </div>
          <div className="whale-stat-card">
            <span className="whale-stat-label">Bearish</span>
            <span className="whale-stat-value bear">{stats.bearish}</span>
          </div>
          <div className="whale-stat-card">
            <span className="whale-stat-label">Top signal</span>
            <span className="whale-stat-value">
              {stats.topBull && stats.topBull.whale_score.score >= 2 ? stats.topBull.symbol :
               stats.topBear && stats.topBear.whale_score.score <= -2 ? stats.topBear.symbol : '—'}
            </span>
          </div>
        </div>
      )}

      {error && (
        <div className="card" style={{ borderColor: '#fb7185', color: '#fb7185' }}>
          ⚠ {error}
        </div>
      )}

      {/* Whales Grid */}
      {!loading && whales.length > 0 ? (
        <div className="whale-grid">
          {whales.map((w) => (
            <WhaleCard key={w.symbol} whale={w} />
          ))}
        </div>
      ) : !loading && !error ? (
        <div className="whale-empty card">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M16.69 7.44a6.973 6.973 0 0 0-1.69-1.32M6 19a3 3 0 0 1-3-3v-3a8 8 0 0 1 16 0v3a3 3 0 0 1-3 3H6Z"/>
            <path d="M9 13h.01M15 13h.01"/>
          </svg>
          <p style={{ marginBottom: 8, color: '#9fb0c8' }}>
            Sem dados whale disponíveis no momento.
          </p>
          <p style={{ fontSize: 12 }}>
            Os endpoints públicos podem estar geo-bloqueados — verifica os logs do servidor.
          </p>
        </div>
      ) : null}
    </div>
  )
}

function WhaleCard({ whale }: { whale: WhaleMetric }) {
  const { symbol, metrics, whale_score } = whale
  const signalClass = whale_score.signal === 'whale_bull' ? 'bull' :
                      whale_score.signal === 'whale_bear' ? 'bear' : 'neutral'
  
  const scoreSign = whale_score.score > 0 ? '+' : ''
  
  return (
    <article className={`whale-card ${signalClass}`}>
      <div className="whale-card-head">
        <div>
          <div className="whale-symbol">{symbol}</div>
          <div className="whale-signal">
            {whale_score.signal === 'whale_bull' && '↗ Whale bull'}
            {whale_score.signal === 'whale_bear' && '↘ Whale bear'}
            {whale_score.signal === 'whale_neutral' && '— Neutral'}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div className="whale-score">{scoreSign}{whale_score.score}</div>
          <div className="whale-score-suffix">/ 10</div>
        </div>
      </div>

      <div className="whale-desc">{whale_score.description}</div>

      <div className="whale-metrics">
        {/* OI */}
        {metrics?.oi && (
          <div className="whale-metric">
            <div className="whale-metric-label">
              OI Trend
              <span className="whale-metric-source">{metrics.oi.source}</span>
            </div>
            <div className="whale-metric-body">
              <PercentBar pct={metrics.oi.oi_7d_change_pct} max={30} />
              <div className="whale-row">
                <span>24h</span>
                <strong className={metrics.oi.oi_24h_change_pct > 0 ? 'pos' : 'neg'}>
                  {metrics.oi.oi_24h_change_pct > 0 ? '+' : ''}{metrics.oi.oi_24h_change_pct.toFixed(1)}%
                </strong>
                <span style={{ marginLeft: 12 }}>7d</span>
                <strong className={metrics.oi.oi_7d_change_pct > 0 ? 'pos' : 'neg'}>
                  {metrics.oi.oi_7d_change_pct > 0 ? '+' : ''}{metrics.oi.oi_7d_change_pct.toFixed(1)}%
                </strong>
              </div>
            </div>
          </div>
        )}

        {/* Funding */}
        {metrics?.funding && (
          <div className="whale-metric">
            <div className="whale-metric-label">
              Funding
              <span className="whale-metric-source">{metrics.funding.source}</span>
            </div>
            <div className="whale-metric-body">
              <PercentBar pct={metrics.funding.funding_rate_pct * 100} max={5} />
              <div className="whale-row">
                <strong className={
                  metrics.funding.funding_rate_pct > 0.02 ? 'warn' :
                  metrics.funding.funding_rate_pct < -0.02 ? 'warn' :
                  metrics.funding.funding_rate_pct > 0 ? 'pos' : 'neg'
                }>
                  {metrics.funding.funding_rate_pct > 0 ? '+' : ''}{metrics.funding.funding_rate_pct.toFixed(4)}%
                </strong>
                <span>per 8h · {metrics.funding.funding_rate_annualized_pct.toFixed(1)}% APR</span>
              </div>
            </div>
          </div>
        )}

        {/* LSR */}
        {metrics?.lsr && (
          <div className="whale-metric">
            <div className="whale-metric-label">
              L/S Ratio
              <span className="whale-metric-source">top traders</span>
            </div>
            <div className="whale-metric-body">
              <RatioBar long={metrics.lsr.long_account_ratio} short={metrics.lsr.short_account_ratio} />
              <div className="whale-row">
                <strong>{metrics.lsr.long_short_ratio.toFixed(2)}</strong>
                <span>24h shift</span>
                <strong className={metrics.lsr.change_24h_pct > 0 ? 'pos' : 'neg'}>
                  {metrics.lsr.change_24h_pct > 0 ? '+' : ''}{metrics.lsr.change_24h_pct.toFixed(1)}%
                </strong>
              </div>
            </div>
          </div>
        )}
      </div>
    </article>
  )
}

/* Mini bar that fills from center: positive right (green), negative left (red) */
function PercentBar({ pct, max }: { pct: number; max: number }) {
  const clamped = Math.max(-max, Math.min(max, pct))
  const widthPct = Math.abs(clamped) / max * 50  // % of half width
  const isPositive = clamped >= 0
  
  return (
    <div className="whale-bar">
      <div
        className={`whale-bar-fill ${isPositive ? 'pos' : 'neg'}`}
        style={{
          width: `${widthPct}%`,
          [isPositive ? 'left' : 'right']: '50%',
        }}
      />
    </div>
  )
}

/* Stacked bar showing long vs short proportion */
function RatioBar({ long, short }: { long: number; short: number }) {
  const total = long + short || 1
  const longPct = (long / total) * 100
  
  return (
    <div className="whale-bar" style={{ background: '#fb7185' }}>
      <div
        style={{
          position: 'absolute', top: 0, bottom: 0, left: 0,
          width: `${longPct}%`,
          background: 'linear-gradient(90deg, #22c55e, #34d399)',
          borderRadius: '999px 0 0 999px',
        }}
      />
    </div>
  )
}
