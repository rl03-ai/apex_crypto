import { useNavigate } from 'react-router-dom'
import type { CryptoAsset, WatchlistEntry } from '../types'
import { ScoreBar } from './ScoreBar'

const usd    = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 })
const pct = (v: number | null | undefined) =>
  v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`

interface Props {
  rows: CryptoAsset[]
  watchlistIds?: Set<string>
  onWatchlistToggle?: (coin: CryptoAsset) => void
}

export function CryptoTable({ rows, watchlistIds, onWatchlistToggle }: Props) {
  const nav    = useNavigate()
  const showWL = !!onWatchlistToggle

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th><th>Ativo</th><th>Preço</th>
            <th>24h</th><th>7d</th><th>30d</th>
            <th>Market Cap</th><th>Score</th><th>Estado</th>
            {showWL && <th></th>}
          </tr>
        </thead>
        <tbody>
          {rows.map(r => {
            const starred = watchlistIds?.has(r.id) ?? false
            return (
              <tr key={r.id} onClick={() => nav(`/asset/${r.id}`)}>
                <td>{r.rank}</td>
                <td><strong>{r.symbol}</strong><small>{r.name}</small></td>
                <td>{usd.format(r.price)}</td>
                <td className={r.change_24h >= 0 ? 'pos' : 'neg'}>{pct(r.change_24h)}</td>
                <td className={r.change_7d  >= 0 ? 'pos' : 'neg'}>{pct(r.change_7d)}</td>
                <td className={r.change_30d >= 0 ? 'pos' : 'neg'}>{pct(r.change_30d)}</td>
                <td>{compact.format(r.market_cap)}</td>
                <td><b>{r.total_score.toFixed(0)}</b><ScoreBar value={r.total_score} /></td>
                <td><span className={`pill ${r.state}`}>{r.state}</span></td>
                {showWL && (
                  <td onClick={e => { e.stopPropagation(); onWatchlistToggle(r) }}>
                    <button className={`star-btn ${starred ? 'starred' : ''}`}
                      title={starred ? 'Remover da watchlist' : 'Adicionar à watchlist'}>
                      {starred ? '★' : '☆'}
                    </button>
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
