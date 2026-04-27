import { useEffect, useMemo, useState } from 'react'
import { fetchMatrix, type MatrixRow, type MatrixResponse } from '../api/endpoints'

type FilterTab = 'all' | 'long' | 'short' | 'tier_s' | 'tier_a'

export function MatrixPage() {
  const [data, setData] = useState<MatrixResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<FilterTab>('all')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const load = async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await fetchMatrix()
      setData(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 10 * 60 * 1000) // refresh 10min
    return () => clearInterval(t)
  }, [])

  const filtered = useMemo(() => {
    if (!data) return []
    let rows = data.data
    if (filter === 'long') rows = rows.filter(r => r.composite > 0)
    else if (filter === 'short') rows = rows.filter(r => r.composite < 0)
    else if (filter === 'tier_s') rows = rows.filter(r => r.tier === 'S')
    else if (filter === 'tier_a') rows = rows.filter(r => r.tier === 'S' || r.tier === 'A')
    return rows
  }, [data, filter])

  const toggle = (sym: string) => {
    setExpanded(prev => {
      const s = new Set(prev)
      s.has(sym) ? s.delete(sym) : s.add(sym)
      return s
    })
  }

  return (
    <div className="matrix-page">
      <div className="matrix-header">
        <div>
          <span className="kicker">Composite signal · institutional + whale</span>
          <h1>⚡ Decision Matrix</h1>
          <p>InstDash 60% + Whale 40% → Composite · Tier · Action</p>
        </div>
        <button onClick={load} disabled={loading} className="whale-refresh">
          {loading ? '↻ Carregando...' : '↻ Recarregar'}
        </button>
      </div>

      {data && (
        <div className="whale-stats">
          <div className="whale-stat-card">
            <span className="whale-stat-label">Tracked</span>
            <span className="whale-stat-value">{data.count}</span>
          </div>
          <div className="whale-stat-card">
            <span className="whale-stat-label">Bullish</span>
            <span className="whale-stat-value bull">{data.stats.bullish}</span>
          </div>
          <div className="whale-stat-card">
            <span className="whale-stat-label">Bearish</span>
            <span className="whale-stat-value bear">{data.stats.bearish}</span>
          </div>
          <div className="whale-stat-card">
            <span className="whale-stat-label">Tier S/A</span>
            <span className="whale-stat-value">{data.stats.tier_s + data.stats.tier_a}</span>
          </div>
        </div>
      )}

      <div className="matrix-toolbar">
        <div className="matrix-tabs">
          <button onClick={() => setFilter('all')} className={`matrix-tab ${filter === 'all' ? 'active' : ''}`}>All</button>
          <button onClick={() => setFilter('long')} className={`matrix-tab ${filter === 'long' ? 'active' : ''}`}>Long</button>
          <button onClick={() => setFilter('short')} className={`matrix-tab ${filter === 'short' ? 'active' : ''}`}>Short</button>
          <button onClick={() => setFilter('tier_s')} className={`matrix-tab ${filter === 'tier_s' ? 'active' : ''}`}>Tier S</button>
          <button onClick={() => setFilter('tier_a')} className={`matrix-tab ${filter === 'tier_a' ? 'active' : ''}`}>Tier S+A</button>
        </div>
      </div>

      {error && (
        <div className="card" style={{ borderColor: '#fb7185', color: '#fb7185' }}>
          ⚠ {error}
        </div>
      )}

      {!loading && filtered.length > 0 ? (
        <div className="matrix-table-wrap">
          <table className="matrix-table">
            <thead>
              <tr>
                <th></th>
                <th>Symbol</th>
                <th className="r">Price · 24h</th>
                <th className="c">InstDash</th>
                <th className="c">Whale</th>
                <th className="r">Composite</th>
                <th className="c">Tier</th>
                <th className="c">Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <MatrixRowComponent
                  key={r.symbol}
                  row={r}
                  expanded={expanded.has(r.symbol)}
                  onToggle={() => toggle(r.symbol)}
                />
              ))}
            </tbody>
          </table>
        </div>
      ) : !loading && !error ? (
        <div className="whale-empty card">
          <p>Sem sinais nesta selecção.</p>
        </div>
      ) : null}
    </div>
  )
}


function MatrixRowComponent({ row, expanded, onToggle }: {
  row: MatrixRow
  expanded: boolean
  onToggle: () => void
}) {
  const compSign = row.composite > 0 ? '+' : ''
  const compClass = row.composite >= 1 ? 'bull' : row.composite <= -1 ? 'bear' : 'neutral'
  const compBarWidth = Math.min(100, Math.abs(row.composite) * 10) / 2 // 0-50% half bar
  
  const instdashSign = row.instdash.score > 0 ? '+' : ''
  const instdashClass = row.instdash.score >= 2 ? 'bull' : row.instdash.score <= -2 ? 'bear' : 'neutral'
  
  const whaleSign = row.whale && row.whale.score > 0 ? '+' : ''
  const whaleClass = row.whale && row.whale.score >= 2 ? 'bull' : row.whale && row.whale.score <= -2 ? 'bear' : 'neutral'
  
  const actionClass = {
    'STRONG BUY': 'strong-buy',
    'BUY': 'buy',
    'HOLD': 'hold',
    'SELL': 'sell',
    'STRONG SELL': 'strong-sell',
  }[row.action]

  const fmt = (n: number | null | undefined, dec = 2) =>
    n === null || n === undefined ? '—' : n.toFixed(dec)
  
  const fmtPrice = (n: number) => {
    if (n >= 1000) return n.toLocaleString('en-US', { maximumFractionDigits: 0 })
    if (n >= 1) return n.toFixed(2)
    if (n >= 0.01) return n.toFixed(4)
    return n.toFixed(6)
  }

  return (
    <>
      <tr className={expanded ? 'expanded' : ''} onClick={onToggle}>
        <td style={{ width: 32 }}>
          <span className={`matrix-chevron ${expanded ? 'open' : ''}`}>▶</span>
        </td>
        <td>
          <div className="matrix-symbol">{row.symbol}</div>
        </td>
        <td className="r">
          <div className="matrix-price">${fmtPrice(row.price)}</div>
          <div className={`matrix-change ${row.change_24h >= 0 ? 'pos' : 'neg'}`} style={{ fontSize: 10 }}>
            {row.change_24h >= 0 ? '+' : ''}{row.change_24h.toFixed(1)}%
          </div>
        </td>
        <td className="c">
          <span className={`matrix-score ${instdashClass}`}>
            {instdashSign}{row.instdash.score}
          </span>
        </td>
        <td className="c">
          {row.whale ? (
            <span className={`matrix-score ${whaleClass}`}>
              {whaleSign}{row.whale.score}
            </span>
          ) : <span style={{ color: '#4d6280' }}>—</span>}
        </td>
        <td className="r">
          <div className="matrix-composite">
            <span className={`matrix-composite-num ${compClass}`}>
              {compSign}{row.composite.toFixed(1)}
            </span>
            <div className="matrix-composite-bar">
              <div
                className={`matrix-composite-bar-fill ${row.composite >= 0 ? 'bull' : 'bear'}`}
                style={{
                  width: `${compBarWidth}%`,
                  [row.composite >= 0 ? 'left' : 'right']: '50%',
                }}
              />
            </div>
          </div>
        </td>
        <td className="c">
          <span className={`matrix-tier ${row.tier}`}>{row.tier}</span>
        </td>
        <td className="c">
          <span className={`matrix-action ${actionClass}`}>{row.action}</span>
        </td>
      </tr>
      {expanded && (
        <tr className="matrix-expanded">
          <td colSpan={8}>
            <div className="matrix-expanded-content">
              {/* InstDash Section */}
              <div className="matrix-expanded-section">
                <h3>📊 InstDash Analysis</h3>
                <div className="matrix-expanded-row">
                  <span>Setup quality</span>
                  <span className={`matrix-setup-pill ${row.instdash.setup_quality?.includes('LONG') ? 'long' : row.instdash.setup_quality?.includes('SHORT') ? 'short' : ''}`}>
                    {row.instdash.setup_quality || '—'}
                  </span>
                </div>
                <div className="matrix-expanded-row">
                  <span>Score</span>
                  <strong className={instdashClass === 'bull' ? 'pos' : instdashClass === 'bear' ? 'neg' : ''}>
                    {instdashSign}{row.instdash.score}/16 ({row.instdash.score_norm.toFixed(1)} norm)
                  </strong>
                </div>
                <div className="matrix-expanded-row">
                  <span>RSI · ADX</span>
                  <strong>{fmt(row.instdash.rsi, 1)} · {fmt(row.instdash.adx, 1)}</strong>
                </div>
                <div className="matrix-expanded-row">
                  <span>LTF · HTF Trend</span>
                  <strong>
                    <span className={row.instdash.ltf_trend === 'bull' ? 'pos' : row.instdash.ltf_trend === 'bear' ? 'neg' : ''}>{row.instdash.ltf_trend}</span>
                    {' · '}
                    <span className={row.instdash.htf_trend === 'bull' ? 'pos' : row.instdash.htf_trend === 'bear' ? 'neg' : ''}>{row.instdash.htf_trend}</span>
                  </strong>
                </div>
                {row.instdash.aligned && (
                  <div className="matrix-expanded-row">
                    <span>Alignment</span>
                    <strong className="pos">✓ Aligned</strong>
                  </div>
                )}
                {(row.instdash.sl_long || row.instdash.sl_short) && (
                  <div className="matrix-expanded-row" style={{ paddingTop: 8, borderTop: '1px dashed #182842', marginTop: 4 }}>
                    <span>Targets</span>
                    <strong style={{ fontSize: 11 }}>
                      {row.instdash.sl_long && row.instdash.tp_long && (
                        <span className="pos">L: SL ${fmtPrice(row.instdash.sl_long)} · TP ${fmtPrice(row.instdash.tp_long)}</span>
                      )}
                      {row.instdash.sl_short && row.instdash.tp_short && (
                        <span className="neg">S: SL ${fmtPrice(row.instdash.sl_short)} · TP ${fmtPrice(row.instdash.tp_short)}</span>
                      )}
                    </strong>
                  </div>
                )}
              </div>

              {/* Whale Section */}
              <div className="matrix-expanded-section">
                <h3>🐳 Whale Activity</h3>
                {row.whale ? (
                  <>
                    <div className="matrix-expanded-row">
                      <span>Signal</span>
                      <strong className={whaleClass === 'bull' ? 'pos' : whaleClass === 'bear' ? 'neg' : ''}>
                        {whaleSign}{row.whale.score}/10 · {row.whale.signal.replace('whale_', '')}
                      </strong>
                    </div>
                    <div className="matrix-expanded-row">
                      <span style={{ fontSize: 11, color: '#6e88a8' }}>{row.whale.description}</span>
                    </div>
                    <div className="matrix-expanded-row">
                      <span>OI 24h · 7d</span>
                      <strong>
                        <span className={(row.whale.oi_24h ?? 0) > 0 ? 'pos' : 'neg'}>{row.whale.oi_24h !== null ? `${(row.whale.oi_24h >= 0 ? '+' : '')}${row.whale.oi_24h.toFixed(1)}%` : '—'}</span>
                        {' · '}
                        <span className={(row.whale.oi_7d ?? 0) > 0 ? 'pos' : 'neg'}>{row.whale.oi_7d !== null ? `${(row.whale.oi_7d >= 0 ? '+' : '')}${row.whale.oi_7d.toFixed(1)}%` : '—'}</span>
                      </strong>
                    </div>
                    <div className="matrix-expanded-row">
                      <span>Funding</span>
                      <strong className={Math.abs(row.whale.funding ?? 0) > 0.02 ? 'warn' : ''}>
                        {row.whale.funding !== null ? `${(row.whale.funding >= 0 ? '+' : '')}${row.whale.funding.toFixed(4)}%` : '—'}
                        {row.whale.funding_apr !== null && (
                          <span style={{ color: '#6e88a8', fontSize: 10, marginLeft: 6 }}>
                            ({row.whale.funding_apr.toFixed(0)}% APR)
                          </span>
                        )}
                      </strong>
                    </div>
                    <div className="matrix-expanded-row">
                      <span>L/S Ratio · 24h</span>
                      <strong>
                        {fmt(row.whale.lsr, 2)}
                        {' · '}
                        <span className={(row.whale.lsr_change ?? 0) > 0 ? 'pos' : 'neg'}>
                          {row.whale.lsr_change !== null ? `${(row.whale.lsr_change >= 0 ? '+' : '')}${row.whale.lsr_change.toFixed(1)}%` : '—'}
                        </span>
                      </strong>
                    </div>
                  </>
                ) : (
                  <div style={{ color: '#6e88a8', fontSize: 12, fontStyle: 'italic' }}>
                    Whale metrics indisponíveis (geo-block ou rate limit)
                  </div>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
