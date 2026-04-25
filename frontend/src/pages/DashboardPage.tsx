import { useEffect, useMemo, useState } from 'react'
import { fetchScanner, fetchFearGreed, fetchWatchlist, addToWatchlist, removeFromWatchlist } from '../api/endpoints'
import type { CryptoAsset, FearGreed, WatchlistEntry } from '../types'
import { CryptoTable } from '../components/CryptoTable'
import { FearGreedGauge } from '../components/FearGreedGauge'
import { StatCard } from '../components/StatCard'
import { ScoreBreakdown } from '../components/ScoreBreakdown'

export function DashboardPage() {
  const [rows,    setRows]    = useState<CryptoAsset[]>([])
  const [fg,      setFg]      = useState<FearGreed | null>(null)
  const [wl,      setWl]      = useState<WatchlistEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [filter,  setFilter]  = useState<'all' | 'confirming' | 'watchlist'>('all')

  useEffect(() => {
    Promise.all([
      fetchScanner(100).then(setRows),
      fetchFearGreed().then(setFg).catch(() => {}),
      fetchWatchlist().then(setWl).catch(() => {}),
    ]).finally(() => setLoading(false))
  }, [])

  const wlIds = useMemo(() => new Set(wl.map(e => e.coin_id)), [wl])

  const visible = useMemo(() => {
    if (filter === 'confirming') return rows.filter(r => r.state === 'confirming')
    if (filter === 'watchlist')  return rows.filter(r => r.state === 'watchlist')
    return rows
  }, [rows, filter])

  const stats = useMemo(() => ({
    confirming: rows.filter(r => r.state === 'confirming').length,
    avg: rows.length ? rows.reduce((s, r) => s + r.total_score, 0) / rows.length : 0,
    risk: rows.length ? rows.reduce((s, r) => s + r.risk, 0) / rows.length : 0,
  }), [rows])

  async function toggleWatchlist(coin: CryptoAsset) {
    const existing = wl.find(e => e.coin_id === coin.id)
    if (existing) {
      await removeFromWatchlist(existing.id)
      setWl(prev => prev.filter(e => e.id !== existing.id))
    } else {
      const entry = await addToWatchlist(coin.id, coin.symbol, coin.name)
      setWl(prev => [...prev, entry])
    }
  }

  const top = rows[0]

  if (loading) return <div className="card loading-card">A carregar scanner...</div>

  return (
    <div className="stack">
      {/* Hero */}
      <section className="hero card">
        <div>
          <p className="kicker">Apex Crypto · Scanner</p>
          <h1>Dashboard de oportunidades</h1>
          <p>Ranking por score composto: adoção, qualidade, valuation, momentum, catalisadores e risco.</p>
        </div>
        {top && (
          <div className="hero-box">
            <small>Top oportunidade</small>
            <strong>{top.symbol}</strong>
            <span>{top.name}</span>
            <ScoreBreakdown asset={top as unknown as Record<string, number>} />
          </div>
        )}
      </section>

      {/* Stats */}
      <div className="stats">
        <FearGreedGauge data={fg} />
        <StatCard label="Confirming"   value={String(stats.confirming)} hint="Score + momentum fortes" />
        <StatCard label="Score médio"  value={stats.avg.toFixed(1)}     hint={`de ${rows.length} ativos`} />
        <StatCard label="Risco médio"  value={stats.risk.toFixed(1)}    hint="0 = seguro, 100 = extremo" />
      </div>

      {/* Scanner */}
      <section className="card">
        <div className="section-head">
          <h2>Scanner</h2>
          <div className="filter-tabs">
            {(['all', 'confirming', 'watchlist'] as const).map(f => (
              <button key={f} className={`tab ${filter === f ? 'active' : ''}`} onClick={() => setFilter(f)}>
                {f === 'all' ? `Todos (${rows.length})` : f === 'confirming' ? `Confirming (${stats.confirming})` : 'Watchlist state'}
              </button>
            ))}
          </div>
        </div>
        <CryptoTable rows={visible} watchlistIds={wlIds} onWatchlistToggle={toggleWatchlist} />
      </section>
    </div>
  )
}
