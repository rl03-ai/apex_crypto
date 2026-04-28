import { useEffect, useMemo, useState } from 'react'
import { fetchMatrix, type MatrixRow, type MatrixResponse, type StageData } from '../api/endpoints'

type FilterTab = 'all' | 'accumulation' | 'early' | 'avoid_extended' | 'tier_sa'

const STAGE_EMOJI: Record<string, string> = {
  ACCUMULATION: '🟢',
  MARKUP_EARLY: '🔵',
  MARKUP_MATURE: '🟡',
  EXTENDED: '🟠',
  DISTRIBUTION: '🟠',
  MARKDOWN: '🔴',
  CHOP: '⚪',
}

const STAGE_LABEL: Record<string, string> = {
  ACCUMULATION: 'ACCUM',
  MARKUP_EARLY: 'EARLY',
  MARKUP_MATURE: 'MATURE',
  EXTENDED: 'EXTENDED',
  DISTRIBUTION: 'DISTRIB',
  MARKDOWN: 'MARKDOWN',
  CHOP: 'CHOP',
}

export function MatrixPage() {
  const [data, setData] = useState<MatrixResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<FilterTab>('all')
  const [limit, setLimit] = useState<number>(100)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const load = async (lim?: number) => {
    try {
      setLoading(true); setError(null)
      const res = await fetchMatrix({ limit: lim ?? limit })
      setData(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load(limit)
    const t = setInterval(() => load(limit), 10 * 60 * 1000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [limit])

  const filtered = useMemo(() => {
    if (!data) return []
    let rows = data.data
    if (filter === 'accumulation') {
      rows = rows.filter(r =>
        r.stage_1d.stage === 'ACCUMULATION' ||
        (r.stage_1w && r.stage_1w.stage === 'ACCUMULATION')
      )
    } else if (filter === 'early') {
      rows = rows.filter(r =>
        r.stage_1d.stage === 'MARKUP_EARLY' ||
        (r.stage_1w && r.stage_1w.stage === 'MARKUP_EARLY')
      )
    } else if (filter === 'avoid_extended') {
      rows = rows.filter(r => r.action !== 'AVOID')
    } else if (filter === 'tier_sa') {
      rows = rows.filter(r => r.tier === 'S' || r.tier === 'A')
    }
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
          <span className="kicker">Stage detector · holds semanas/meses</span>
          <h1>⚡ Decision Matrix</h1>
          <p>Dual TF (1d + 1w) · Stages · Penaliza setups esticados</p>
        </div>
        <button onClick={() => load(limit)} disabled={loading} className="whale-refresh">
          {loading ? '↻ Carregando...' : '↻ Recarregar'}
        </button>
      </div>

      {data && (
        <div className="whale-stats">
          <div className="whale-stat-card">
            <span className="whale-stat-label">Tracked / Requested</span>
            <span className="whale-stat-value">{data.count} / {data.requested}</span>
          </div>
          <div className="whale-stat-card">
            <span className="whale-stat-label">🟢 Accumulating</span>
            <span className="whale-stat-value bull">{data.stats.accumulating}</span>
          </div>
          <div className="whale-stat-card">
            <span className="whale-stat-label">🔵 Early Markup</span>
            <span className="whale-stat-value bull">{data.stats.early_markup}</span>
          </div>
          <div className="whale-stat-card">
            <span className="whale-stat-label">🟠 Extended (avoid)</span>
            <span className="whale-stat-value bear">{data.stats.extended}</span>
          </div>
        </div>
      )}

      <div className="matrix-toolbar">
        <div className="matrix-tabs">
          <button onClick={() => setFilter('all')} className={`matrix-tab ${filter === 'all' ? 'active' : ''}`}>All</button>
          <button onClick={() => setFilter('accumulation')} className={`matrix-tab ${filter === 'accumulation' ? 'active' : ''}`}>🟢 Accumul</button>
          <button onClick={() => setFilter('early')} className={`matrix-tab ${filter === 'early' ? 'active' : ''}`}>🔵 Early</button>
          <button onClick={() => setFilter('avoid_extended')} className={`matrix-tab ${filter === 'avoid_extended' ? 'active' : ''}`}>Hide AVOID</button>
          <button onClick={() => setFilter('tier_sa')} className={`matrix-tab ${filter === 'tier_sa' ? 'active' : ''}`}>Tier S+A</button>
        </div>
        <div className="matrix-tabs" style={{ marginLeft: 'auto' }}>
          <span style={{ color: '#6e88a8', fontSize: 11, fontWeight: 600, alignSelf: 'center', marginRight: 8 }}>SYMBOLS:</span>
          {[50, 100, 150, 200].map(n => (
            <button key={n} onClick={() => setLimit(n)} className={`matrix-tab ${limit === n ? 'active' : ''}`} disabled={loading}>
              {n}
            </button>
          ))}
        </div>
      </div>

      {limit >= 150 && loading && (
        <div className="card" style={{ borderColor: '#f7b955', color: '#f7b955', fontSize: 12 }}>
          ⚠ Processing {limit} symbols on dual TF — pode demorar 60-120s
        </div>
      )}

      {error && (
        <div className="card" style={{ borderColor: '#fb7185', color: '#fb7185' }}>⚠ {error}</div>
      )}

      {!loading && filtered.length > 0 ? (
        <div className="matrix-table-wrap">
          <table className="matrix-table">
            <thead>
              <tr>
                <th></th>
                <th>Symbol</th>
                <th className="r">Price · 24h</th>
                <th className="c">Stage 1D</th>
                <th className="c">Stage 1W</th>
                <th className="c">Whale</th>
                <th className="r">Composite</th>
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


function StageBadge({ stage }: { stage: StageData | null | undefined }) {
  if (!stage) return <span style={{ color: '#4d6280' }}>—</span>
  
  const cls = stage.stage.toLowerCase().replace('_', '-')
  return (
    <div className={`stage-badge stage-${cls}`} title={stage.reasons.join(' · ')}>
      <span className="stage-emoji">{STAGE_EMOJI[stage.stage]}</span>
      <span className="stage-label">{STAGE_LABEL[stage.stage]}</span>
      <span className="stage-score">{stage.score > 0 ? '+' : ''}{stage.score}</span>
    </div>
  )
}


function MatrixRowComponent({ row, expanded, onToggle }: {
  row: MatrixRow; expanded: boolean; onToggle: () => void
}) {
  const compClass = row.composite >= 1 ? 'bull' : row.composite <= -1 ? 'bear' : 'neutral'
  const compBarWidth = Math.min(100, Math.abs(row.composite) * 10) / 2
  
  const actionClass: Record<string, string> = {
    'STRONG BUY': 'strong-buy',
    'BUY': 'buy',
    'HOLD': 'hold',
    'WATCH': 'hold',
    'AVOID': 'avoid',
  }

  const fmtPrice = (n: number) => {
    if (n >= 1000) return n.toLocaleString('en-US', { maximumFractionDigits: 0 })
    if (n >= 1) return n.toFixed(2)
    if (n >= 0.01) return n.toFixed(4)
    return n.toFixed(6)
  }
  const fmt = (n: number | null | undefined, dec = 2) =>
    n === null || n === undefined ? '—' : n.toFixed(dec)

  const whaleScore = row.whale?.score ?? 0
  const whaleClass = whaleScore >= 2 ? 'bull' : whaleScore <= -2 ? 'bear' : 'neutral'

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
        <td className="c"><StageBadge stage={row.stage_1d} /></td>
        <td className="c"><StageBadge stage={row.stage_1w} /></td>
        <td className="c">
          {row.whale ? (
            <span className={`matrix-score ${whaleClass}`}>
              {whaleScore > 0 ? '+' : ''}{whaleScore}
            </span>
          ) : <span style={{ color: '#4d6280' }}>—</span>}
        </td>
        <td className="r">
          <div className="matrix-composite">
            <span className={`matrix-composite-num ${compClass}`}>
              {row.composite > 0 ? '+' : ''}{row.composite.toFixed(1)}
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
          <span className={`matrix-action ${actionClass[row.action] || 'hold'}`}>{row.action}</span>
        </td>
      </tr>
      {expanded && (
        <tr className="matrix-expanded">
          <td colSpan={8}>
            <div className="matrix-expanded-content">
              {/* Stage Reasoning */}
              <div className="matrix-expanded-section">
                <h3>📈 Stage Analysis</h3>
                <div className="matrix-expanded-row">
                  <span>1D Stage</span>
                  <strong>{STAGE_EMOJI[row.stage_1d.stage]} {row.stage_1d.stage_label} · Tier {row.stage_1d.tier}</strong>
                </div>
                {row.stage_1d.reasons.map((r, i) => (
                  <div key={i} style={{ fontSize: 11, color: '#9fb0c8', paddingLeft: 12, lineHeight: 1.5 }}>· {r}</div>
                ))}
                {row.stage_1w && (
                  <>
                    <div className="matrix-expanded-row" style={{ marginTop: 10 }}>
                      <span>1W Stage</span>
                      <strong>{STAGE_EMOJI[row.stage_1w.stage]} {row.stage_1w.stage_label} · Tier {row.stage_1w.tier}</strong>
                    </div>
                    {row.stage_1w.reasons.map((r, i) => (
                      <div key={i} style={{ fontSize: 11, color: '#9fb0c8', paddingLeft: 12, lineHeight: 1.5 }}>· {r}</div>
                    ))}
                  </>
                )}
                <div className="matrix-expanded-row" style={{ paddingTop: 8, borderTop: '1px dashed #182842', marginTop: 8 }}>
                  <span>Final Action</span>
                  <strong className={row.action === 'STRONG BUY' || row.action === 'BUY' ? 'pos' : row.action === 'AVOID' ? 'neg' : ''}>
                    {row.action}
                  </strong>
                </div>
              </div>

              {/* Indicators */}
              <div className="matrix-expanded-section">
                <h3>📊 Indicators</h3>
                <div className="matrix-expanded-row">
                  <span>Structure</span>
                  <strong className={row.instdash.struct_bias === 1 ? 'pos' : row.instdash.struct_bias === -1 ? 'neg' : ''}>
                    {row.instdash.struct_bias === 1 ? '🟢 BULLISH' : row.instdash.struct_bias === -1 ? '🔴 BEARISH' : '⚪ NEUTRAL'}
                    {row.instdash.last_event !== 'none' && (
                      <span style={{ fontSize: 10, color: '#9fb0c8', marginLeft: 6, fontFamily: 'JetBrains Mono, monospace' }}>
                        ({row.instdash.last_event})
                      </span>
                    )}
                  </strong>
                </div>
                <div className="matrix-expanded-row">
                  <span>RSI · ADX</span>
                  <strong>{fmt(row.instdash.rsi, 1)} · {fmt(row.instdash.adx, 1)}</strong>
                </div>
                <div className="matrix-expanded-row">
                  <span>LTF · HTF Trend</span>
                  <strong>
                    <span className={row.instdash.ltf_trend === 'ALTA' ? 'pos' : row.instdash.ltf_trend === 'BAIXA' ? 'neg' : ''}>{row.instdash.ltf_trend}</span>
                    {' · '}
                    <span className={row.instdash.htf_trend === 'ALTA' ? 'pos' : row.instdash.htf_trend === 'BAIXA' ? 'neg' : ''}>{row.instdash.htf_trend}</span>
                  </strong>
                </div>
                <div className="matrix-expanded-row">
                  <span>% above MA200d</span>
                  <strong className={(row.instdash.ext_above_ma200_pct ?? 0) > 60 ? 'warn' : ''}>
                    {row.instdash.ext_above_ma200_pct !== null ? `${row.instdash.ext_above_ma200_pct >= 0 ? '+' : ''}${row.instdash.ext_above_ma200_pct.toFixed(0)}%` : '—'}
                  </strong>
                </div>
                {row.instdash.aligned && (
                  <div className="matrix-expanded-row">
                    <span>Alignment</span>
                    <strong className="pos">✓ Aligned</strong>
                  </div>
                )}
                
                {row.whale && (
                  <>
                    <div className="matrix-expanded-row" style={{ marginTop: 10, paddingTop: 8, borderTop: '1px dashed #182842' }}>
                      <span>🐳 Whale</span>
                      <strong className={whaleClass === 'bull' ? 'pos' : whaleClass === 'bear' ? 'neg' : ''}>
                        {whaleScore > 0 ? '+' : ''}{whaleScore}/10
                      </strong>
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
                      </strong>
                    </div>
                  </>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
