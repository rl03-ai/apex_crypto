import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchScanner, fetchFearGreed, fetchWatchlist, addToWatchlist, removeFromWatchlist } from '../api/endpoints'
import type { CryptoAsset, FearGreed, WatchlistEntry } from '../types'
import { CryptoTable } from '../components/CryptoTable'
import { FearGreedGauge } from '../components/FearGreedGauge'
import { StatCard } from '../components/StatCard'
import { ScoreBreakdown } from '../components/ScoreBreakdown'

const REFRESH_INTERVAL_MS = 60_000  // 1 min

function timeAgo(ts: number): string {
  const sec = Math.floor((Date.now() - ts) / 1000)
  if (sec < 5)   return 'agora mesmo'
  if (sec < 60)  return `há ${sec}s`
  if (sec < 3600) return `há ${Math.floor(sec / 60)}min`
  return `há ${Math.floor(sec / 3600)}h`
}

export function DashboardPage() {
  const [rows,        setRows]        = useState<CryptoAsset[]>([])
  const [fg,          setFg]          = useState<FearGreed | null>(null)
  const [wl,          setWl]          = useState<WatchlistEntry[]>([])
  const [loading,     setLoading]     = useState(true)
  const [refreshing,  setRefreshing]  = useState(false)
  const [filter,      setFilter]      = useState<'all' | 'confirming' | 'watchlist'>('all')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [lastUpdate,  setLastUpdate]  = useState<number>(Date.now())
  const [, forceTick] = useState(0)
  const refreshTimer = useRef<number | null>(null)

  const loadData = useCallback(async (silent = false) => {
    if (!silent) setRefreshing(true)
    try {
      const [scanRows, fgData, wlData] = await Promise.all([
        fetchScanner(100),
        fetchFearGreed().catch(() => null),
        fetchWatchlist().catch(() => [] as WatchlistEntry[]),
      ])
      setRows(scanRows)
      if (fgData) setFg(fgData)
      setWl(wlData)
      setLastUpdate(Date.now())
    } finally {
      if (!silent) setRefreshing(false)
      setLoading(false)
    }
  }, [])

  // Carga inicial
  useEffect(() => { loadData() }, [loadData])

  // Auto-refresh
  useEffect(() => {
    if (refreshTimer.current) {
      window.clearInterval(refreshTimer.current)
      refreshTimer.current = null
    }
    if (autoRefresh) {
      refreshTimer.current = window.setInterval(() => loadData(true), REFRESH_INTERVAL_MS)
    }
    return () => { if (refreshTimer.current) window.clearInterval(refreshTimer.current) }
  }, [autoRefresh, loadData])

  // Tick de 5 em 5 s para o "há Xs" se actualizar visualmente
  useEffect(() => {
    const t = window.setInterval(() => forceTick(n => n + 1), 5000)
    return () => window.clearInterval(t)
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
          <div>
            <h2>Scanner</h2>
            <small className="freshness">
              Actualizado {timeAgo(lastUpdate)}
              {refreshing && ' · a actualizar…'}
            </small>
          </div>
          <div className="scanner-controls">
            <label className="auto-refresh-toggle" title="Auto-refresh a cada 60s">
              <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} />
              <span>Auto</span>
            </label>
            <button className="btn-ghost" onClick={() => loadData()} disabled={refreshing} title="Actualizar agora">
              {refreshing ? '↻' : '↻'} Refresh
            </button>
            <div className="filter-tabs">
              {(['all', 'confirming', 'watchlist'] as const).map(f => (
                <button key={f} className={`tab ${filter === f ? 'active' : ''}`} onClick={() => setFilter(f)}>
                  {f === 'all' ? `Todos (${rows.length})` : f === 'confirming' ? `Confirming (${stats.confirming})` : 'Watchlist state'}
                </button>
              ))}
            </div>
          </div>
        </div>
        <CryptoTable rows={visible} watchlistIds={wlIds} onWatchlistToggle={toggleWatchlist} />
      </section>
    </div>
  )
}
