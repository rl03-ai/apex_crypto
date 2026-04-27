import { useEffect, useState } from 'react'
import { Activity, AlertCircle } from 'lucide-react'
import { fetchWhales, type WhaleMetric } from '../api/endpoints'

export function WhalesPage() {
  const [whales, setWhales] = useState<WhaleMetric[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await fetchWhales()
      setWhales(res.data || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro desconhecido')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 5 * 60 * 1000)
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
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <Activity className="w-8 h-8 text-blue-600" />
            <h1 className="text-3xl font-bold text-slate-900">🐳 Whale Tracking</h1>
          </div>
          <p className="text-slate-600">OI trends + funding rate + long/short positioning (Binance/Bybit/OKX fallback)</p>
        </div>

        <div className="mb-6 flex gap-3">
          <button
            onClick={load}
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

        {!loading && whales.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {whales.map((w) => (
              <div
                key={w.symbol}
                className={`rounded-lg border p-4 ${getSignalColor(w.whale_score.signal)} border-opacity-20`}
              >
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">{w.symbol}</h3>
                    <p className="text-xs text-slate-600 capitalize">{w.whale_score.signal.replace('_', ' ')}</p>
                  </div>
                  <div className={`text-2xl font-bold ${getScoreColor(w.whale_score.score)}`}>
                    {w.whale_score.score > 0 ? '+' : ''}{w.whale_score.score}
                  </div>
                </div>

                <p className="text-sm text-slate-700 mb-3">{w.whale_score.description}</p>

                {/* OI Metrics */}
                {w.metrics?.oi && (
                  <div className="mb-2 p-2 bg-slate-100 rounded text-sm">
                    <div className="font-semibold text-slate-800 mb-1 flex justify-between">
                      <span>OI Trend</span>
                      <span className="text-xs text-gray-500">{w.metrics.oi.source}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs text-slate-700">
                      <div>
                        <div className="text-gray-600">24h</div>
                        <div className={w.metrics.oi.oi_24h_change_pct > 0 ? 'text-green-600' : 'text-red-600'}>
                          {w.metrics.oi.oi_24h_change_pct > 0 ? '+' : ''}{w.metrics.oi.oi_24h_change_pct.toFixed(1)}%
                        </div>
                      </div>
                      <div>
                        <div className="text-gray-600">7d</div>
                        <div className={w.metrics.oi.oi_7d_change_pct > 0 ? 'text-green-600' : 'text-red-600'}>
                          {w.metrics.oi.oi_7d_change_pct > 0 ? '+' : ''}{w.metrics.oi.oi_7d_change_pct.toFixed(1)}%
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Funding Rate */}
                {w.metrics?.funding && (
                  <div className="mb-2 p-2 bg-slate-100 rounded text-sm">
                    <div className="font-semibold text-slate-800 mb-1">Funding Rate</div>
                    <div className="text-xs text-slate-700">
                      <div className={w.metrics.funding.funding_rate_pct > 0.02 ? 'text-orange-600' : w.metrics.funding.funding_rate_pct < -0.02 ? 'text-orange-600' : 'text-slate-700'}>
                        {w.metrics.funding.funding_rate_pct > 0 ? '+' : ''}{w.metrics.funding.funding_rate_pct.toFixed(4)}% per 8h
                      </div>
                      <div className="text-gray-600 text-xs">
                        Annualized: {w.metrics.funding.funding_rate_annualized_pct.toFixed(1)}%
                      </div>
                    </div>
                  </div>
                )}

                {/* Long/Short Ratio */}
                {w.metrics?.lsr && (
                  <div className="p-2 bg-slate-100 rounded text-sm">
                    <div className="font-semibold text-slate-800 mb-1">Whale Positioning (24h)</div>
                    <div className="text-xs text-slate-700">
                      <div className="flex justify-between">
                        <span>L/S Ratio</span>
                        <span className="font-semibold">{w.metrics.lsr.long_short_ratio.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between text-gray-600">
                        <span>Change 24h</span>
                        <span className={w.metrics.lsr.change_24h_pct > 0 ? 'text-green-600' : 'text-red-600'}>
                          {w.metrics.lsr.change_24h_pct > 0 ? '+' : ''}{w.metrics.lsr.change_24h_pct.toFixed(1)}%
                        </span>
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
            <p className="text-sm text-slate-500">
              Verificando logs do servidor — pode ser geo-block nos endpoints públicos.
            </p>
          </div>
        ) : null}
      </div>
    </div>
  )
}
