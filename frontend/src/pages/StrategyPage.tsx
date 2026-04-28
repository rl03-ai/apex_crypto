import { useEffect, useState } from 'react'
import { fetchStrategy, type StrategyResponse, type StrategyPick, type SectorData } from '../api/endpoints'

export function StrategyPage() {
  const [data, setData] = useState<StrategyResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [portfolioUsd, setPortfolioUsd] = useState(10000)
  const [profile, setProfile] = useState<'conservative' | 'balanced' | 'aggressive'>('aggressive')
  const [activeTab, setActiveTab] = useState<'picks' | 'sectors'>('picks')

  const load = async () => {
    try {
      setLoading(true); setError(null)
      const res = await fetchStrategy(portfolioUsd, profile, 100)
      setData(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [portfolioUsd, profile])

  const fmtUsd = (n: number) => `$${n.toLocaleString('en-US', { maximumFractionDigits: 0 })}`

  return (
    <div className="strategy-page">
      <div className="matrix-header">
        <div>
          <span className="kicker">Allocation · DCA · Sector rotation</span>
          <h1>🎯 Strategy</h1>
          <p>Top picks com allocation, DCA scheduler e rotação sectorial</p>
        </div>
      </div>

      <div className="risk-form card">
        <div className="risk-form-row">
          <label>
            <span>Portfolio (USD)</span>
            <input
              type="number"
              value={portfolioUsd}
              onChange={(e) => setPortfolioUsd(Number(e.target.value))}
              min={100}
              step={100}
            />
          </label>
          <label>
            <span>Profile</span>
            <select value={profile} onChange={(e) => setProfile(e.target.value as any)}>
              <option value="conservative">Conservative</option>
              <option value="balanced">Balanced</option>
              <option value="aggressive">Aggressive</option>
            </select>
          </label>
          <button onClick={load} disabled={loading} className="whale-refresh">
            {loading ? '↻ Carregando...' : '↻ Recarregar'}
          </button>
        </div>
      </div>

      {error && <div className="card" style={{ borderColor: '#fb7185', color: '#fb7185' }}>⚠ {error}</div>}

      {data && (
        <>
          <div className="whale-stats">
            <div className="whale-stat-card">
              <span className="whale-stat-label">Allocated</span>
              <span className="whale-stat-value">{data.total_alloc_pct.toFixed(0)}%</span>
            </div>
            <div className="whale-stat-card">
              <span className="whale-stat-label">Cash</span>
              <span className="whale-stat-value">{data.remaining_cash_pct.toFixed(0)}%</span>
            </div>
            <div className="whale-stat-card">
              <span className="whale-stat-label">Top picks</span>
              <span className="whale-stat-value">{data.top_picks.length}</span>
            </div>
            <div className="whale-stat-card">
              <span className="whale-stat-label">Rotation</span>
              <span className="whale-stat-value" style={{ fontSize: 14 }}>{data.sector_rotation.rotation_signal || '—'}</span>
            </div>
          </div>

          <div className="matrix-toolbar">
            <div className="matrix-tabs">
              <button onClick={() => setActiveTab('picks')} className={`matrix-tab ${activeTab === 'picks' ? 'active' : ''}`}>
                💎 Top Picks
              </button>
              <button onClick={() => setActiveTab('sectors')} className={`matrix-tab ${activeTab === 'sectors' ? 'active' : ''}`}>
                🔄 Sector Rotation
              </button>
            </div>
          </div>

          {activeTab === 'picks' && (
            <div className="strategy-picks">
              {data.top_picks.length > 0 ? data.top_picks.map((p) => (
                <PickCard key={p.symbol} pick={p} fmtUsd={fmtUsd} />
              )) : (
                <div className="whale-empty card">
                  <p>Sem top picks neste momento.</p>
                  <p style={{ fontSize: 12 }}>Profile {profile} é restritivo — tenta outro profile.</p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'sectors' && (
            <div className="strategy-sectors">
              {data.sector_rotation.sectors.map((s) => (
                <SectorCard key={s.sector} sector={s} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}


function PickCard({ pick, fmtUsd }: { pick: StrategyPick; fmtUsd: (n: number) => string }) {
  const dcaModeLabel = {
    lump_sum: '⚡ Lump Sum',
    dca: '📅 DCA',
    split: '⚖️ Split',
    wait: '⏸ Wait',
  }[pick.dca_mode]
  
  return (
    <div className="pick-card card">
      <div className="pick-head">
        <div>
          <div className="pick-symbol">{pick.symbol}</div>
          <div className="pick-meta">
            <span className="pick-sector">{pick.sector}</span>
            <span className={`matrix-tier ${pick.tier}`}>{pick.tier}</span>
            <span className={`matrix-action ${pick.action === 'STRONG BUY' ? 'strong-buy' : 'buy'}`}>{pick.action}</span>
          </div>
        </div>
        <div className="pick-alloc">
          <span className="pick-alloc-pct">{pick.alloc_pct.toFixed(1)}%</span>
          <span className="pick-alloc-usd">{fmtUsd(pick.alloc_usd)}</span>
        </div>
      </div>

      <div className="pick-stages">
        <span className="stage-pill">1D · {pick.stage_1d}</span>
        {pick.stage_1w && <span className="stage-pill">1W · {pick.stage_1w}</span>}
      </div>

      <div className="pick-dca">
        <div className="pick-dca-mode">{dcaModeLabel}</div>
        <p className="pick-dca-note">{pick.dca_note}</p>
        
        {pick.dca_mode !== 'wait' && (
          <div className="pick-dca-breakdown">
            {pick.lump_sum_usd > 0 && (
              <div className="pick-dca-row">
                <span>Lump sum agora</span>
                <strong>{fmtUsd(pick.lump_sum_usd)}</strong>
              </div>
            )}
            {pick.dca_total_usd > 0 && (
              <>
                <div className="pick-dca-row">
                  <span>DCA total ({pick.dca_weeks} semanas)</span>
                  <strong>{fmtUsd(pick.dca_total_usd)}</strong>
                </div>
                <div className="pick-dca-row">
                  <span>Cada compra semanal</span>
                  <strong>{fmtUsd(pick.dca_weekly_usd)}</strong>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}


function SectorCard({ sector }: { sector: SectorData }) {
  const signalClass = sector.signal === 'OVERWEIGHT' ? 'over' : sector.signal === 'UNDERWEIGHT' ? 'under' : 'neutral'
  
  return (
    <div className={`sector-card card sector-${signalClass}`}>
      <div className="sector-head">
        <div>
          <div className="sector-name">{sector.sector}</div>
          <div className="sector-meta">{sector.count} coins · avg score {sector.avg_score > 0 ? '+' : ''}{sector.avg_score.toFixed(1)}</div>
        </div>
        <span className={`sector-signal ${signalClass}`}>{sector.signal}</span>
      </div>

      <div className="sector-stats">
        <div className="sector-stat">
          <span className="sector-stat-label">Bullish</span>
          <span className="sector-stat-value bull">{sector.bullish_count}/{sector.count}</span>
        </div>
        <div className="sector-stat">
          <span className="sector-stat-label">Extended</span>
          <span className="sector-stat-value bear">{sector.extended_count}/{sector.count}</span>
        </div>
      </div>

      {sector.top_picks.length > 0 && (
        <div className="sector-picks">
          <span className="sector-picks-label">Top picks</span>
          <div className="sector-picks-list">
            {sector.top_picks.map((p) => (
              <div key={p.symbol} className="sector-pick">
                <span className="sector-pick-sym">{p.symbol.replace('USDT', '')}</span>
                <span className={`matrix-tier ${p.tier}`} style={{ width: 22, height: 22, fontSize: 10 }}>{p.tier}</span>
                <span className={`sector-pick-comp ${p.composite >= 0 ? 'pos' : 'neg'}`}>
                  {p.composite > 0 ? '+' : ''}{p.composite.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
