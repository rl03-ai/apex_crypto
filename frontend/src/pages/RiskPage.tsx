import { useState } from 'react'
import { fetchPositionSize, type PositionResult } from '../api/endpoints'

export function RiskPage() {
  const [symbol, setSymbol] = useState('BTC')
  const [portfolioUsd, setPortfolioUsd] = useState(10000)
  const [profile, setProfile] = useState<'conservative' | 'balanced' | 'aggressive'>('aggressive')
  const [result, setResult] = useState<PositionResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const calculate = async () => {
    if (!symbol.trim()) return
    try {
      setLoading(true); setError(null)
      const r = await fetchPositionSize(symbol.trim(), portfolioUsd, profile)
      setResult(r)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro')
    } finally {
      setLoading(false)
    }
  }

  const fmtUsd = (n: number) => `$${n.toLocaleString('en-US', { maximumFractionDigits: 2 })}`
  const fmtPrice = (n: number) => {
    if (n >= 1000) return n.toLocaleString('en-US', { maximumFractionDigits: 0 })
    if (n >= 1) return n.toFixed(2)
    return n.toFixed(6)
  }

  return (
    <div className="risk-page">
      <div className="matrix-header">
        <div>
          <span className="kicker">Position sizing · SL/TP · Portfolio constraints</span>
          <h1>🛡️ Risk Model</h1>
          <p>Calcula tamanho de posição, stops dinâmicos e exposição</p>
        </div>
      </div>

      <div className="risk-form card">
        <div className="risk-form-row">
          <label>
            <span>Symbol</span>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              placeholder="BTC"
              onKeyDown={(e) => e.key === 'Enter' && calculate()}
            />
          </label>
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
              <option value="conservative">Conservative (3% risk)</option>
              <option value="balanced">Balanced (5% risk)</option>
              <option value="aggressive">Aggressive (10% risk)</option>
            </select>
          </label>
          <button onClick={calculate} disabled={loading} className="whale-refresh">
            {loading ? 'Calculando...' : 'Calcular'}
          </button>
        </div>
      </div>

      {error && (
        <div className="card" style={{ borderColor: '#fb7185', color: '#fb7185' }}>⚠ {error}</div>
      )}

      {result && (
        <>
          <div className="risk-result-hero card">
            <div>
              <div style={{ fontSize: 11, color: '#6e88a8', textTransform: 'uppercase', letterSpacing: '0.12em', fontWeight: 700 }}>
                {result.symbol} · ${fmtPrice(result.price)}
              </div>
              <div style={{ fontSize: 13, color: '#9fb0c8', marginTop: 6 }}>
                Stage <strong style={{ color: '#e5eefc' }}>{result.stage}</strong> · Tier <strong style={{ color: '#e5eefc' }}>{result.tier}</strong>
              </div>
            </div>
            <span className={`matrix-action ${result.action === 'STRONG BUY' ? 'strong-buy' : result.action === 'BUY' ? 'buy' : result.action === 'AVOID' ? 'avoid' : 'hold'}`}>
              {result.action}
            </span>
          </div>

          {/* Stops */}
          <div className="card" style={{ padding: 20 }}>
            <h3 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.14em', color: '#6e88a8', fontWeight: 700, marginBottom: 14 }}>📐 Stop Levels</h3>
            
            {result.stops.recommended ? (
              <>
                <div className="risk-stops-grid">
                  <div className="risk-stop-card entry">
                    <span className="risk-stop-label">Entry</span>
                    <span className="risk-stop-value">${fmtPrice(result.stops.entry!)}</span>
                  </div>
                  <div className="risk-stop-card sl">
                    <span className="risk-stop-label">Stop Loss</span>
                    <span className="risk-stop-value">${fmtPrice(result.stops.sl!)}</span>
                    <span className="risk-stop-pct neg">{result.stops.sl_pct!.toFixed(2)}%</span>
                  </div>
                  <div className="risk-stop-card tp1">
                    <span className="risk-stop-label">TP1 (50%)</span>
                    <span className="risk-stop-value">${fmtPrice(result.stops.tp1!)}</span>
                    <span className="risk-stop-pct pos">+{result.stops.tp1_pct!.toFixed(2)}%</span>
                    <span className="risk-stop-r">R: {result.stops.r_multiple_1}x</span>
                  </div>
                  <div className="risk-stop-card tp2">
                    <span className="risk-stop-label">TP2 (full)</span>
                    <span className="risk-stop-value">${fmtPrice(result.stops.tp2!)}</span>
                    <span className="risk-stop-pct pos">+{result.stops.tp2_pct!.toFixed(2)}%</span>
                    <span className="risk-stop-r">R: {result.stops.r_multiple_2}x</span>
                  </div>
                </div>
                <p style={{ fontSize: 12, color: '#9fb0c8', fontStyle: 'italic', marginTop: 12 }}>{result.stops.note}</p>
              </>
            ) : (
              <div style={{ color: '#fb923c', fontSize: 13 }}>⚠ {result.stops.reason}</div>
            )}
          </div>

          {/* Position size */}
          {result.position && (
            <div className="card" style={{ padding: 20 }}>
              <h3 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.14em', color: '#6e88a8', fontWeight: 700, marginBottom: 14 }}>💰 Position Sizing</h3>
              
              {result.position.recommended ? (
                <>
                  <div className="risk-position-grid">
                    <div className="risk-position-stat">
                      <span className="risk-position-label">Position size</span>
                      <span className="risk-position-value bull">{fmtUsd(result.position.position_usd!)}</span>
                      <span className="risk-position-sub">{result.position.allocated_pct}% portfolio</span>
                    </div>
                    <div className="risk-position-stat">
                      <span className="risk-position-label">Coins to buy</span>
                      <span className="risk-position-value">{result.position.coins}</span>
                    </div>
                    <div className="risk-position-stat">
                      <span className="risk-position-label">Risk if SL hit</span>
                      <span className="risk-position-value bear">{fmtUsd(result.position.risk_usd!)}</span>
                      <span className="risk-position-sub">{result.position.risk_pct}% portfolio</span>
                    </div>
                    <div className="risk-position-stat">
                      <span className="risk-position-label">Multipliers</span>
                      <span className="risk-position-value">Tier {result.position.tier_mult}x · Stage {result.position.stage_mult}x</span>
                    </div>
                  </div>
                  {result.position.warnings && result.position.warnings.length > 0 && (
                    <div style={{ marginTop: 12, fontSize: 12, color: '#f7b955' }}>
                      {result.position.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
                    </div>
                  )}
                </>
              ) : (
                <div style={{ color: '#fb923c', fontSize: 13 }}>⚠ {result.position.reason}</div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
