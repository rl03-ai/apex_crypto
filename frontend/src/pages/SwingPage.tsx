import { useEffect, useMemo, useState } from 'react'
import { fetchSwing, type SwingRow, type SwingResponse, type SwingStage } from '../api/endpoints'

type SwingMode = 'short' | 'medium'
type FilterTab = 'all' | 'breakout' | 'pullback' | 'momentum' | 'tier_sa' | 'hide_avoid'

const STAGE_EMOJI: Record<string, string> = {
  BREAKOUT: '💥',
  PULLBACK: '🔵',
  MOMENTUM: '🟡',
  REVERSAL: '🔄',
  EXHAUSTION: '🟠',
  BEARISH: '🔴',
  NO_SETUP: '⚪',
}

const STAGE_LABEL: Record<string, string> = {
  BREAKOUT: 'BREAKOUT',
  PULLBACK: 'PULLBACK',
  MOMENTUM: 'MOMENTUM',
  REVERSAL: 'REVERSAL',
  EXHAUSTION: 'EXHAUST',
  BEARISH: 'BEARISH',
  NO_SETUP: 'NO SETUP',
}

export function SwingPage() {
  const [data, setData] = useState<SwingResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<SwingMode>('short')
  const [filter, setFilter] = useState<FilterTab>('all')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const load = async () => {
    try {
      setLoading(true); setError(null)
      const res = await fetchSwing({ mode, limit: 80 })
      setData(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 10 * 60 * 1000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode])

  const filtered = useMemo(() => {
    if (!data) return []
    let rows = data.data
    if (filter === 'breakout') rows = rows.filter(r => r.swing.stage === 'BREAKOUT')
    else if (filter === 'pullback') rows = rows.filter(r => r.swing.stage === 'PULLBACK')
    else if (filter === 'momentum') rows = rows.filter(r => r.swing.stage === 'MOMENTUM')
    else if (filter === 'tier_sa') rows = rows.filter(r => r.tier === 'S' || r.tier === 'A')
    else if (filter === 'hide_avoid') rows = rows.filter(r => r.action !== 'AVOID')
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
          <span className="kicker">Tri-TF · 3-14d (curto) ou 1-4 sem (médio)</span>
          <h1>📈 Swing Matrix</h1>
          <p>{mode === 'short' ? '1h + 4h + 1d · setup principal no 4h' : '4h + 1d + 1w · setup principal no 1d'}</p>
        </div>
        <button onClick={load} disabled={loading} className="whale-refresh">
          {loading ? '↻ Carregando...' : '↻ Recarregar'}
        </button>
      </div>

      {/* Mode toggle prominent */}
      <div className="card" style={{ padding: 16, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.14em', color: '#6e88a8', fontWeight: 700 }}>
          MODE
        </span>
        <div className="matrix-tabs">
          <button onClick={() => setMode('short')} className={`matrix-tab ${mode === 'short' ? 'active' : ''}`}>
            ⚡ Short (3-14d)
          </button>
          <button onClick={() => setMode('medium')} className={`matrix-tab ${mode === 'medium' ? 'active' : ''}`}>
            🎯 Medium (1-4 sem)
          </button>
        </div>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: '#9fb0c8' }}>
          Primary: <strong style={{ color: '#e5eefc', fontFamily: 'JetBrains Mono, monospace' }}>{mode === 'short' ? '4h' : '1d'}</strong>
          {' · '}
          Fast: <strong style={{ color: '#e5eefc', fontFamily: 'JetBrains Mono, monospace' }}>{mode === 'short' ? '1h' : '4h'}</strong>
          {' · '}
          Macro: <strong style={{ color: '#e5eefc', fontFamily: 'JetBrains Mono, monospace' }}>{mode === 'short' ? '1d' : '1w'}</strong>
        </span>
      </div>

      {data && (
        <div className="whale-stats">
          <div className="whale-stat-card">
            <span className="whale-stat-label">💥 Breakouts</span>
            <span className="whale-stat-value bull">{data.stats.breakouts}</span>
          </div>
          <div className="whale-stat-card">
            <span className="whale-stat-label">🔵 Pullbacks</span>
            <span className="whale-stat-value bull">{data.stats.pullbacks}</span>
          </div>
          <div className="whale-stat-card">
            <span className="whale-stat-label">🟡 Momentum</span>
            <span className="whale-stat-value">{data.stats.momentum}</span>
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
          <button onClick={() => setFilter('breakout')} className={`matrix-tab ${filter === 'breakout' ? 'active' : ''}`}>💥 Breakout</button>
          <button onClick={() => setFilter('pullback')} className={`matrix-tab ${filter === 'pullback' ? 'active' : ''}`}>🔵 Pullback</button>
          <button onClick={() => setFilter('momentum')} className={`matrix-tab ${filter === 'momentum' ? 'active' : ''}`}>🟡 Momentum</button>
          <button onClick={() => setFilter('tier_sa')} className={`matrix-tab ${filter === 'tier_sa' ? 'active' : ''}`}>Tier S+A</button>
          <button onClick={() => setFilter('hide_avoid')} className={`matrix-tab ${filter === 'hide_avoid' ? 'active' : ''}`}>Hide AVOID</button>
        </div>
      </div>

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
                <th className="c">Setup</th>
                <th className="c">{data?.mode === 'short' ? '1h' : '4h'}</th>
                <th className="c">{data?.mode === 'short' ? '4h' : '1d'}</th>
                <th className="c">{data?.mode === 'short' ? '1d' : '1w'}</th>
                <th className="r">Score</th>
                <th className="c">Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <SwingRowComponent
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
        <div className="whale-empty card"><p>Sem setups swing nesta selecção.</p></div>
      ) : null}
    </div>
  )
}


function SetupBadge({ swing }: { swing: SwingStage }) {
  const cls = swing.stage.toLowerCase().replace('_', '-')
  return (
    <div className={`stage-badge stage-${cls}`} title={swing.reasons.join(' · ')}>
      <span className="stage-emoji">{STAGE_EMOJI[swing.stage]}</span>
      <span className="stage-label">{STAGE_LABEL[swing.stage]}</span>
      <span className="stage-score">{swing.score > 0 ? '+' : ''}{swing.score}</span>
    </div>
  )
}


function StructIcon({ bias, label }: { bias: number; label: string }) {
  if (bias === 1) return <span style={{ color: '#22c55e', fontSize: 16, fontWeight: 700 }} title="Bullish">↑</span>
  if (bias === -1) return <span style={{ color: '#fb7185', fontSize: 16, fontWeight: 700 }} title="Bearish">↓</span>
  return <span style={{ color: '#9fb0c8', fontSize: 14 }} title="Neutral">→</span>
}


function SwingRowComponent({ row, expanded, onToggle }: {
  row: SwingRow; expanded: boolean; onToggle: () => void
}) {
  const compClass = row.composite >= 1 ? 'bull' : row.composite <= -1 ? 'bear' : 'neutral'
  const compBarWidth = Math.min(100, Math.abs(row.composite) * 10) / 2
  
  const actionClass: Record<string, string> = {
    'STRONG BUY': 'strong-buy',
    'BUY': 'buy',
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
        <td className="c"><SetupBadge swing={row.swing} /></td>
        <td className="c">
          {row.fast ? <StructIcon bias={row.fast.struct_bias} label={row.fast.tf} /> : '—'}
        </td>
        <td className="c">
          <StructIcon bias={row.primary.struct_bias} label={row.primary.tf} />
        </td>
        <td className="c">
          {row.macro ? <StructIcon bias={row.macro.struct_bias} label={row.macro.tf} /> : '—'}
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
          <td colSpan={9}>
            <div className="matrix-expanded-content">
              {/* Setup Reasoning */}
              <div className="matrix-expanded-section">
                <h3>📈 Setup Analysis</h3>
                <div className="matrix-expanded-row">
                  <span>Setup</span>
                  <strong>{STAGE_EMOJI[row.swing.stage]} {row.swing.stage_label} · Tier {row.swing.tier}</strong>
                </div>
                {row.swing.reasons.map((r, i) => (
                  <div key={i} style={{ fontSize: 11, color: '#9fb0c8', paddingLeft: 12, lineHeight: 1.5 }}>· {r}</div>
                ))}

                {row.stops && (
                  <>
                    <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px dashed #182842' }}>
                      <h3 style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.14em', color: '#6e88a8', fontWeight: 700, marginBottom: 8 }}>📐 Stop Levels (2×ATR)</h3>
                      <div className="matrix-expanded-row">
                        <span>Entry · SL</span>
                        <strong>${fmtPrice(row.stops.entry)} · <span className="neg">${fmtPrice(row.stops.sl)}</span> ({row.stops.sl_pct}%)</strong>
                      </div>
                      <div className="matrix-expanded-row">
                        <span>TP1 (3×ATR)</span>
                        <strong className="pos">${fmtPrice(row.stops.tp1)} (+{row.stops.tp1_pct}%) · 1.5R</strong>
                      </div>
                      <div className="matrix-expanded-row">
                        <span>TP2 (4×ATR)</span>
                        <strong className="pos">${fmtPrice(row.stops.tp2)} (+{row.stops.tp2_pct}%) · 2.0R</strong>
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* Tri-TF breakdown */}
              <div className="matrix-expanded-section">
                <h3>📊 Tri-TF Breakdown</h3>
                
                {row.fast && (
                  <>
                    <div className="matrix-expanded-row" style={{ marginTop: 4 }}>
                      <span>⚡ {row.fast.tf} (Fast)</span>
                      <strong>
                        Struct: <span className={row.fast.struct_bias === 1 ? 'pos' : row.fast.struct_bias === -1 ? 'neg' : ''}>
                          {row.fast.struct_bias === 1 ? '🟢' : row.fast.struct_bias === -1 ? '🔴' : '⚪'}
                        </span>
                        {row.fast.rsi !== null && row.fast.rsi !== undefined && (
                          <span style={{ marginLeft: 8 }}>RSI {row.fast.rsi.toFixed(0)}</span>
                        )}
                      </strong>
                    </div>
                  </>
                )}
                
                <div className="matrix-expanded-row">
                  <span>🎯 {row.primary.tf} (Primary)</span>
                  <strong>
                    Struct: <span className={row.primary.struct_bias === 1 ? 'pos' : row.primary.struct_bias === -1 ? 'neg' : ''}>
                      {row.primary.struct_bias === 1 ? '🟢 BULL' : row.primary.struct_bias === -1 ? '🔴 BEAR' : '⚪ NEUTRAL'}
                    </span>
                  </strong>
                </div>
                <div className="matrix-expanded-row" style={{ paddingLeft: 12 }}>
                  <span style={{ fontSize: 11 }}>RSI · ADX · MACD</span>
                  <strong style={{ fontSize: 12 }}>
                    {fmt(row.primary.rsi, 1)} · {fmt(row.primary.adx, 1)} · {row.primary.macd_bullish ? '🟢' : '🔴'}
                  </strong>
                </div>
                <div className="matrix-expanded-row" style={{ paddingLeft: 12 }}>
                  <span style={{ fontSize: 11 }}>Squeeze · Aligned</span>
                  <strong style={{ fontSize: 12 }}>
                    {row.primary.squeeze ? '🔒' : '—'}
                    {row.primary.squeeze_release ? ' 💥' : ''}
                    {' · '}
                    {row.primary.aligned_bull ? '✓' : '✗'}
                  </strong>
                </div>

                {row.macro && (
                  <div className="matrix-expanded-row" style={{ marginTop: 4 }}>
                    <span>🌍 {row.macro.tf} (Macro)</span>
                    <strong>
                      Struct: <span className={row.macro.struct_bias === 1 ? 'pos' : row.macro.struct_bias === -1 ? 'neg' : ''}>
                        {row.macro.struct_bias === 1 ? '🟢' : row.macro.struct_bias === -1 ? '🔴' : '⚪'}
                      </span>
                      {' · '}
                      <span className={row.macro.htf_trend === 'ALTA' ? 'pos' : row.macro.htf_trend === 'BAIXA' ? 'neg' : ''}>
                        {row.macro.htf_trend}
                      </span>
                    </strong>
                  </div>
                )}

                {row.whale && (
                  <div className="matrix-expanded-row" style={{ marginTop: 8, paddingTop: 8, borderTop: '1px dashed #182842' }}>
                    <span>🐳 Whale</span>
                    <strong className={row.whale.score >= 2 ? 'pos' : row.whale.score <= -2 ? 'neg' : ''}>
                      {row.whale.score > 0 ? '+' : ''}{row.whale.score}/10
                    </strong>
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
