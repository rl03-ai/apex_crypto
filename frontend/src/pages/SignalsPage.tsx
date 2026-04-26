import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchSignals, triggerScanInstDash } from '../api/endpoints'
import type { Signal } from '../types'

const TIME_FMT = new Intl.DateTimeFormat('pt-PT', { dateStyle: 'short', timeStyle: 'short' })

export function SignalsPage() {
  const nav = useNavigate()
  const [signals, setSignals] = useState<Signal[]>([])
  const [loading, setLoading] = useState(true)
  const [filter,  setFilter]  = useState<'all' | 'long' | 'short' | 'exit'>('all')
  const [scanning, setScanning] = useState(false)

  const load = () => {
    setLoading(true)
    fetchSignals(filter !== 'all' ? { direction: filter } : {})
      .then(setSignals)
      .catch(() => setSignals([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [filter])

  async function runScan() {
    setScanning(true)
    try {
      await triggerScanInstDash()
      // O scan corre em background ~1-2 min, refresh depois
      setTimeout(load, 90_000)
    } finally {
      setTimeout(() => setScanning(false), 90_000)
    }
  }

  const counts = {
    all: signals.length,
    long: signals.filter(s => s.direction === 'long').length,
    short: signals.filter(s => s.direction === 'short').length,
    exit: signals.filter(s => s.direction === 'exit').length,
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Sinais activos</h2>
            <small style={{ color: '#8da2c0' }}>
              Detectados pelo motor InstDash · {signals.length} activos
            </small>
          </div>
          <button className="btn" onClick={runScan} disabled={scanning}>
            {scanning ? '↻ A correr…' : '↻ Forçar scan'}
          </button>
        </div>

        <div className="filter-tabs" style={{ marginTop: 12 }}>
          {(['all', 'long', 'short', 'exit'] as const).map(f => (
            <button key={f} className={`tab ${filter === f ? 'active' : ''}`}
              onClick={() => setFilter(f)}>
              {f === 'all' ? `Todos (${counts.all})` :
               f === 'long' ? `↗ Long (${counts.long})` :
               f === 'short' ? `↘ Short (${counts.short})` :
               `⚠ Exit (${counts.exit})`}
            </button>
          ))}
        </div>
      </section>

      {loading && <div className="card loading-card">A carregar sinais...</div>}

      {!loading && signals.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: 48 }}>
          <p style={{ fontSize: 48, margin: 0 }}>🎯</p>
          <h2>Sem sinais activos</h2>
          <p style={{ color: '#8da2c0' }}>
            Os scans correm de 4 em 4 horas. Podes forçar um agora.
          </p>
        </div>
      )}

      {signals.map(s => (
        <div key={s.id} className={`card signal-card signal-${s.direction}`}
          onClick={() => {
            // tentar navegar para asset page usando o symbol Binance (BTCUSDT → bitcoin)
            const base = s.symbol.replace(/USDT$/, '').toLowerCase()
            nav(`/asset/${binanceToCoinId(base)}`)
          }}
          style={{ cursor: 'pointer' }}
        >
          <div className="signal-header">
            <div className="signal-bar" data-direction={s.direction} />
            <div className="signal-content">
              <div className="signal-meta">
                <span className={`pill ${s.direction === 'long' ? 'confirming' : s.direction === 'short' ? 'avoid' : ''}`}>
                  {s.direction === 'long' ? '↗ LONG' :
                   s.direction === 'short' ? '↘ SHORT' : '⚠ EXIT'}
                </span>
                <span className="signal-symbol">{s.symbol}</span>
                <span className="signal-interval">{s.interval}</span>
                <span className="signal-score" style={{ color: s.score >= 0 ? '#22c55e' : '#fb7185' }}>
                  {s.score >= 0 ? '+' : ''}{s.score} / 16
                </span>
                <span className="signal-time">{TIME_FMT.format(new Date(s.detected_at))}</span>
              </div>
              <strong className="signal-title">{s.title}</strong>
              <p className="signal-desc">{s.description}</p>
              {(s.sl != null || s.tp != null) && (
                <div className="signal-targets">
                  {s.sl != null && <span>SL: <strong>{s.sl.toFixed(4)}</strong></span>}
                  {s.tp != null && <span>TP: <strong>{s.tp.toFixed(4)}</strong></span>}
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// Mapeamento básico para nav. Se não souber, usa o próprio symbol em lowercase.
function binanceToCoinId(base: string): string {
  const map: Record<string, string> = {
    btc: 'bitcoin', eth: 'ethereum', bnb: 'binancecoin', xrp: 'ripple',
    ada: 'cardano', sol: 'solana', dot: 'polkadot', doge: 'dogecoin',
    avax: 'avalanche-2', matic: 'matic-network', link: 'chainlink',
    ltc: 'litecoin', trx: 'tron', atom: 'cosmos', uni: 'uniswap',
  }
  return map[base] ?? base
}
