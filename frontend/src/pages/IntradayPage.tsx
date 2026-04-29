import { useEffect, useMemo, useState } from 'react'
import { fetchIntraday, type IntradayRow, type IntradayResponse, type IntradayStage } from '../api/endpoints'

type IntradayMode = 'scalping' | 'day'
type FilterTab = 'all' | 'trend_bo' | 'vwap' | 'pullback' | 'sweep' | 'overnight' | 'tier_sa' | 'hide_avoid'

const STAGE_EMOJI: Record<string, string> = {
  TREND_BO: '💥',
  VWAP_RECLAIM: '🌊',
  MICRO_PULLBACK: '🔵',
  LIQ_SWEEP: '🎣',
  SQUEEZE_BO: '🎯',
  EXHAUSTION: '🟠',
  BEARISH: '🔴',
  NO_SETUP: '⚪',
}

const STAGE_LABEL: Record<string, string> = {
  TREND_BO: 'TREND BO',
  VWAP_RECLAIM: 'VWAP',
  MICRO_PULLBACK: 'PULLBACK',
  LIQ_SWEEP: 'SWEEP',
  SQUEEZE_BO: 'SQUEEZE',
  EXHAUSTION: 'EXHAUST',
  BEARISH: 'BEARISH',
  NO_SETUP: 'NO SETUP',
}

export function IntradayPage() {
  const [data, setData] = useState<IntradayResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<IntradayMode>('day')
  const [filter, setFilter] = useState<FilterTab>('all')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const load = async () => {
    try {
      setLoading(true); setError(null)
      const res = await fetchIntraday({ mode, limit: 60 })
      setData(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // Intraday refresh mais frequente: 5 min
    const t = setInterval(load, 5 * 60 * 1000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode])

  const filtered = useMemo(() => {
    if (!data) return []
    let rows = data.data
    if (filter === 'trend_bo') rows = rows.filter(r => r.setup.stage === 'TREND_BO')
    else if (filter === 'vwap') rows = rows.filter(r => r.setup.stage === 'VWAP_RECLAIM')
    else if (filter === 'pullback') rows = rows.filter(r => r.setup.stage === 'MICRO_PULLBACK')
    else if (filter === 'sweep') rows = rows.filter(r => r.setup.stage === 'LIQ_SWEEP')
    else if (filter === 'overnight') rows = rows.filter(r => r.can_hold_overnight)
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
          <span className="kicker">Tri-TF · 1h a 24h · refresh 5min</span>
          <h1>⚡ Intraday Matrix</h1>
          <p>{mode === 'scalping' ? '5m + 15m + 1h · scalping' : '15m + 1h + 4h · day trading'}</p>
        </div>
        <button onClick={load} disabled={loading} className="whale-refresh">
          {loading ? '↻ Carregando...' : '↻ Recarregar'}
        </button>
      </div>

      {/* Mode toggle */}
      <div className="card" style={{ padding: 16, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.14em', color: '#6e88a8', fontWeight: 700 }}>
          MODE
        </span>
        <div className="matrix-tabs">
          <button onClick={() => setMode('scalping')} className={`matrix-tab ${mode === 'scalping' ? 'active' : ''}`}>
            ⚡ Scalping (5m+15m+1h)
          </button>
          <button onClick={() => setMode('day')} className={`matrix-tab ${mode === 'day' ? 'active' : ''}`}>
            🎯 Day (15m+1h+4h)
          </button>
        </div>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: '#9fb0c8' }}>
          Primary: <strong style={{ color: '#e5eefc', fontFamily: 'JetBrains Mono, monospace' }}>{mode === 'scalping' ? '5m' : '15m'}</strong>
          {' · '}
          Fast: <strong style={{ color: '#e5eefc', fontFamily: 'JetBrains Mono, monospace' }}>{mode === 'scalping' ? '15m' : '1h'}</strong>
          {' · '}
          Macro: <strong style={{ color: '#e5eefc', fontFamily: 'JetBrains Mono, monospace' }}>{mode === 'scalping' ? '1h' : '4h'}</strong>
        </span>
      </div>

      {data && (
        <div className="whale-stats">
          <div className="whale-stat-card">
            <span className="whale-stat-label">💥 Trend BO</span>
            <span className="whale-stat-value bull">{data.stats.trend_breakouts}</span>
          </div>
          <div className="whale-stat-card">
            <span className="whale-stat-label">🌊 VWAP</span>
            <span className="whale-stat-value bull">{data.stats.vwap_reclaims}</span>
          </div>
          <div className="whale-stat-card">
            <span className="whale-stat-label">🎣 Sweeps</span>
            <span className="whale-stat-value bull">{data.stats.liq_sweeps}</span>
          </div>
          <div className="whale-stat-card">
            <span className="whale-stat-label">🌙 Overnight OK</span>
            <span className="whale-stat-value">{data.stats.overnight_eligible}</span>
          </div>
        </div>
      )}

      <div className="matrix-toolbar">
        <div className="matrix-tabs">
          <button onClick={() => setFilter('all')} className={`matrix-tab ${filter === 'all' ? 'active' : ''}`}>All</button>
          <button onClick={() => setFilter('trend_bo')} className={`matrix-tab ${filter === 'trend_bo' ? 'active' : ''}`}>💥 Trend BO</button>
          <button onClick={() => setFilter('vwap')} className={`matrix-tab ${filter === 'vwap' ? 'active' : ''}`}>🌊 VWAP</button>
          <button onClick={() => setFilter('pullback')} className={`matrix-tab ${filter === 'pullback' ? 'active' : ''}`}>🔵 Pullback</button>
          <button onClick={() => setFilter('sweep')} className={`matrix-tab ${filter === 'sweep' ? 'active' : ''}`}>🎣 Sweep</button>
          <button onClick={() => setFilter('overnight')} className={`matrix-tab ${filter === 'overnight' ? 'active' : ''}`}>🌙 Overnight</button>
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
                <th className="c">{data?.mode === 'scalping' ? '5m' : '15m'}</th>
                <th className="c">{data?.mode === 'scalping' ? '15m' : '1h'}</th>
                <th className="c">{data?.mode === 'scalping' ? '1h' : '4h'}</th>
                <th className="c">Hold</th>
                <th className="r">Score</th>
                <th className="c">Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <IntradayRowComponent
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
        <div className="whale-empty card"><p>Sem setups intraday nesta selecção.</p></div>
      ) : null}
    </div>
  )
}


function SetupBadge({ setup }: { setup: IntradayStage }) {
  const cls = setup.stage.toLowerCase().replace('_', '-')
  return (
    <div className={`stage-badge stage-${cls}`} title={setup.reasons.join(' · ')}>
      <span className="stage-emoji">{STAGE_EMOJI[setup.stage]}</span>
      <span className="stage-label">{STAGE_LABEL[setup.stage]}</span>
      <span className="stage-score">{setup.score > 0 ? '+' : ''}{setup.score}</span>
    </div>
  )
}


function StructIcon({ bias }: { bias: number }) {
  if (bias === 1) return <span style={{ color: '#22c55e', fontSize: 16, fontWeight: 700 }} title="Bullish">↑</span>
  if (bias === -1) return <span style={{ color: '#fb7185', fontSize: 16, fontWeight: 700 }} title="Bearish">↓</span>
  return <span style={{ color: '#9fb0c8', fontSize: 14 }} title="Neutral">→</span>
}


function IntradayRowComponent({ row, expanded, onToggle }: {
  row: IntradayRow; expanded: boolean; onToggle: () => void
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
        <td className="c"><SetupBadge setup={row.setup} /></td>
        <td className="c"><StructIcon bias={row.primary.struct_bias} /></td>
        <td className="c">
          {row.fast ? <StructIcon bias={row.fast.struct_bias} /> : '—'}
        </td>
        <td className="c">
          {row.macro ? <StructIcon bias={row.macro.struct_bias} /> : '—'}
        </td>
        <td className="c">
          {row.can_hold_overnight ? (
            <span title="Pode aguentar overnight (Tier S/A)">🌙</span>
          ) : (
            <span style={{ color: '#6e88a8', fontSize: 11 }} title="Fechar no fim da sessão">☀</span>
          )}
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
          <td colSpan={10}>
            <div className="matrix-expanded-content">
              <div className="matrix-expanded-section">
                <h3>⚡ Setup Analysis</h3>
                <div className="matrix-expanded-row">
                  <span>Setup</span>
                  <strong>{STAGE_EMOJI[row.setup.stage]} {row.setup.stage_label} · Tier {row.setup.tier}</strong>
                </div>
                {row.setup.reasons.map((r, i) => (
                  <div key={i} style={{ fontSize: 11, color: '#9fb0c8', paddingLeft: 12, lineHeight: 1.5 }}>· {r}</div>
                ))}

                <div className="matrix-expanded-row" style={{ marginTop: 8, paddingTop: 8, borderTop: '1px dashed #182842' }}>
                  <span>Hold</span>
                  <strong className={row.can_hold_overnight ? 'pos' : ''}>
                    {row.can_hold_overnight ? '🌙 Overnight OK (S/A)' : '☀ Fechar na sessão'}
                  </strong>
                </div>

                {row.stops && (
                  <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px dashed #182842' }}>
                    <h3 style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.14em', color: '#6e88a8', fontWeight: 700, marginBottom: 8 }}>📐 Stops (1×ATR)</h3>
                    <div className="matrix-expanded-row">
                      <span>Entry · SL</span>
                      <strong>${fmtPrice(row.stops.entry)} · <span className="neg">${fmtPrice(row.stops.sl)}</span> ({row.stops.sl_pct}%)</strong>
                    </div>
                    <div className="matrix-expanded-row">
                      <span>TP1 (2×ATR)</span>
                      <strong className="pos">${fmtPrice(row.stops.tp1)} (+{row.stops.tp1_pct}%) · 2.0R</strong>
                    </div>
                    <div className="matrix-expanded-row">
                      <span>TP2 (3×ATR)</span>
                      <strong className="pos">${fmtPrice(row.stops.tp2)} (+{row.stops.tp2_pct}%) · 3.0R</strong>
                    </div>
                  </div>
                )}
              </div>

              <div className="matrix-expanded-section">
                <h3>📊 Tri-TF Breakdown</h3>
                
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
                  <span style={{ fontSize: 11 }}>VWAP · Vol burst · Sweep</span>
                  <strong style={{ fontSize: 12 }}>
                    {row.primary.above_vwap ? '🌊 above' : '— below'}
                    {' · '}
                    {row.primary.vol_burst ? '💥' : '—'}
                    {' · '}
                    {row.primary.sweep_low ? '🎣 low' : row.primary.sweep_high ? '🎣 high' : '—'}
                  </strong>
                </div>

                {row.fast && (
                  <div className="matrix-expanded-row" style={{ marginTop: 4 }}>
                    <span>⚡ {row.fast.tf} (Fast)</span>
                    <strong style={{ fontSize: 12 }}>
                      <span className={row.fast.struct_bias === 1 ? 'pos' : row.fast.struct_bias === -1 ? 'neg' : ''}>
                        {row.fast.struct_bias === 1 ? '🟢' : row.fast.struct_bias === -1 ? '🔴' : '⚪'}
                      </span>
                      {row.fast.rsi !== null && row.fast.rsi !== undefined && (
                        <span style={{ marginLeft: 8 }}>RSI {row.fast.rsi.toFixed(0)}</span>
                      )}
                      {row.fast.above_vwap && <span style={{ marginLeft: 8 }}>🌊</span>}
                    </strong>
                  </div>
                )}

                {row.macro && (
                  <div className="matrix-expanded-row" style={{ marginTop: 4 }}>
                    <span>🌍 {row.macro.tf} (Macro)</span>
                    <strong style={{ fontSize: 12 }}>
                      <span className={row.macro.struct_bias === 1 ? 'pos' : row.macro.struct_bias === -1 ? 'neg' : ''}>
                        {row.macro.struct_bias === 1 ? '🟢' : row.macro.struct_bias === -1 ? '🔴' : '⚪'}
                      </span>
                      {' · '}
                      <span className={row.macro.htf_trend === 'ALTA' ? 'pos' : row.macro.htf_trend === 'BAIXA' ? 'neg' : ''}>
                        {row.macro.htf_trend}
                      </span>
                      {row.macro.above_vwap && <span style={{ marginLeft: 6 }}>🌊</span>}
                    </strong>
                  </div>
                )}

                {row.whale && (
                  <div className="matrix-expanded-row" style={{ marginTop: 8, paddingTop: 8, borderTop: '1px dashed #182842' }}>
                    <span>🐳 Whale</span>
                    <strong className={row.whale.score >= 2 ? 'pos' : row.whale.score <= -2 ? 'neg' : ''}>
                      {row.whale.score > 0 ? '+' : ''}{row.whale.score}/10
                      {row.whale.funding !== null && (
                        <span style={{ marginLeft: 8, fontSize: 11, color: '#9fb0c8' }}>
                          fund {row.whale.funding > 0 ? '+' : ''}{row.whale.funding.toFixed(3)}%
                        </span>
                      )}
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
