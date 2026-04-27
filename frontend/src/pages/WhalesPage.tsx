import React, { useEffect, useState } from 'react'
import { TrendingUp, TrendingDown, Activity, AlertCircle } from 'lucide-react'

interface WhaleMetric {
  symbol: string
  metrics: {
    oi: {
      oi_current_usd: number
      oi_24h_change_pct: number
      oi_7d_change_pct: number
    } | null
    liq: {
      total_liquidated_usd: number
      longs_pct: number
      shorts_pct: number
    } | null
  }
  whale_score: {
    score: number
    signal: 'whale_bull' | 'whale_bear' | 'whale_neutral'
    description: string
  }
}

export default function WhalesPage() {
  const [whales, setWhales] = useState<WhaleMetric[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchWhales = async () => {
    try {
      setLoading(true)
      const res = await fetch('/api/whales')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setWhales(data.data || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro desconhecido')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchWhales()
    const interval = setInterval(fetchWhales, 5 * 60 * 1000) // 5min
    return () => clearInterval(interval)
  }, [])

  const getSignalColor = (signal: string) => {
    if (signal === 'whale_bull') return 'text-green-500 bg-green-50'
    if (signal === 'whale_bear') return 'text-red-500 bg-red-50'
    return 'text-gray-500 bg-gray-50'
  }

  const getScoreColor = (score: number) => {
    if (score >= 5) return 'text-green-600'
    if (score >= 2) return 'text-green-500'
    if (score <= -5) return 'text-red-600'
    if (score <= -2) return 'text-red-500'
    return 'text-gray-600'
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <Activity className="w-8 h-8 text-blue-600" />
            <h1 className="text-3xl font-bold text-slate-900">🐳 Whale Tracking</h1>
          </div>
          <p className="text-slate-600">Smart money activity — OI trends + liquidation signals</p>
        </div>

        {/* Actions */}
        <div className="mb-6 flex gap-3">
          <button
            onClick={fetchWhales}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Carregando...' : 'Recarregar'}
          </button>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" />
            <div className="text-sm text-red-700">{error}</div>
          </div>
        )}

        {/* Whales Grid */}
        {!loading && whales.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {whales.map((w) => (
              <div
                key={w.symbol}
                className={`rounded-lg border p-4 ${getSignalColor(w.whale_score.signal)} border-opacity-20`}
              >
                {/* Symbol + Score */}
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">{w.symbol}</h3>
                    <p className="text-xs text-slate-600 capitalize">{w.whale_score.signal.replace('_', ' ')}</p>
                  </div>
                  <div className={`text-2xl font-bold ${getScoreColor(w.whale_score.score)}`}>
                    {w.whale_score.score > 0 ? '+' : ''}{w.whale_score.score}
                  </div>
                </div>

                {/* Description */}
                <p className="text-sm text-slate-700 mb-3">{w.whale_score.description}</p>

                {/* OI Metrics */}
                {w.metrics.oi && (
                  <div className="mb-3 p-2 bg-slate-100 rounded text-sm">
                    <div className="font-semibold text-slate-800 mb-1">OI Trend</div>
                    <div className="grid grid-cols-2 gap-2 text-xs text-slate-700">
                      <div>
                        <div className="text-gray-600">24h</div>
                        <div className={w.metrics.oi.oi_24h_change_pct > 0 ? 'text-green-600' : 'text-red-600'}>
                          {w.metrics.oi.oi_24h_change_pct > 0 ? '+' : ''}
                          {w.metrics.oi.oi_24h_change_pct.toFixed(1)}%
                        </div>
                      </div>
                      <div>
                        <div className="text-gray-600">7d</div>
                        <div className={w.metrics.oi.oi_7d_change_pct > 0 ? 'text-green-600' : 'text-red-600'}>
                          {w.metrics.oi.oi_7d_change_pct > 0 ? '+' : ''}
                          {w.metrics.oi.oi_7d_change_pct.toFixed(1)}%
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Liquidation Metrics */}
                {w.metrics.liq && (
                  <div className="p-2 bg-slate-100 rounded text-sm">
                    <div className="font-semibold text-slate-800 mb-1">Liquidations 24h</div>
                    <div className="space-y-1 text-xs text-slate-700">
                      <div className="flex justify-between">
                        <span>Shorts</span>
                        <span className="font-semibold text-green-600">{w.metrics.liq.shorts_pct.toFixed(1)}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Longs</span>
                        <span className="font-semibold text-red-600">{w.metrics.liq.longs_pct.toFixed(1)}%</span>
                      </div>
                      <div className="pt-1 text-gray-600">
                        Total: ${(w.metrics.liq.total_liquidated_usd / 1_000_000).toFixed(1)}M
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : !loading ? (
          <div className="text-center py-12 text-slate-600">
            <Activity className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <p>Sem dados whale disponíveis no momento.</p>
            <p className="text-sm text-slate-500">CoinGlass pode estar em rate limit (10 req/min).</p>
          </div>
        ) : null}
      </div>
    </div>
  )
}
