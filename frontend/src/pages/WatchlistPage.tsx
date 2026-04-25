import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  fetchWatchlistEnriched,
  updateWatchlistEntry,
  removeFromWatchlist,
} from '../api/endpoints'
import type { WatchlistEnriched } from '../types'
import { ScoreBar } from '../components/ScoreBar'

const usd     = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
const pct = (v: number | null | undefined) =>
  v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`

export function WatchlistPage() {
  const nav = useNavigate()
  const [entries, setEntries]     = useState<WatchlistEnriched[]>([])
  const [loading, setLoading]     = useState(true)
  const [editing, setEditing]     = useState<string | null>(null)   // watchlist_id em edição
  const [draft,   setDraft]       = useState<Partial<WatchlistEnriched>>({})

  const load = () =>
    fetchWatchlistEnriched()
      .then(setEntries)
      .catch(() => setEntries([]))
      .finally(() => setLoading(false))

  useEffect(() => { load() }, [])

  async function handleRemove(id: string) {
    await removeFromWatchlist(id)
    setEntries(prev => prev.filter(e => e.id !== id))
  }

  function startEdit(e: WatchlistEnriched) {
    setEditing(e.id)
    setDraft({ notes: e.notes, alert_price_above: e.alert_price_above, alert_price_below: e.alert_price_below, alert_score_above: e.alert_score_above })
  }

  async function saveEdit(id: string) {
    const updated = await updateWatchlistEntry(id, draft)
    setEntries(prev => prev.map(e => e.id === id ? { ...e, ...updated } : e))
    setEditing(null)
  }

  if (loading) return <div className="card loading-card">A carregar watchlist...</div>
  if (entries.length === 0) return (
    <div className="stack">
      <div className="card" style={{ textAlign: 'center', padding: '60px' }}>
        <p style={{ fontSize: 48, margin: 0 }}>☆</p>
        <h2>Watchlist vazia</h2>
        <p style={{ color: '#8da2c0' }}>Adiciona moedas com a estrela (★) no scanner.</p>
        <button className="btn" onClick={() => nav('/')}>Ir ao Scanner</button>
      </div>
    </div>
  )

  return (
    <div className="stack">
      <section className="card">
        <div className="section-head">
          <h2>Watchlist</h2>
          <span style={{ color: '#8da2c0' }}>{entries.length} moeda{entries.length !== 1 ? 's' : ''}</span>
        </div>
      </section>

      {entries.map(e => {
        const isEditing = editing === e.id
        const score = e.total_score ?? null
        return (
          <div key={e.id} className="card wl-card">
            {/* Cabeçalho da moeda */}
            <div className="wl-header">
              <div className="wl-identity" onClick={() => nav(`/asset/${e.coin_id}`)} style={{ cursor: 'pointer' }}>
                <span className="wl-symbol">{e.symbol}</span>
                <div>
                  <strong>{e.name}</strong>
                  <small style={{ color: '#8da2c0' }}>{e.coin_id}</small>
                </div>
              </div>
              <div className="wl-actions">
                <button className="btn-ghost" onClick={() => isEditing ? setEditing(null) : startEdit(e)}>
                  {isEditing ? '✕ Cancelar' : '✎ Editar alertas'}
                </button>
                <button className="btn-ghost danger" onClick={() => handleRemove(e.id)}>✕</button>
              </div>
            </div>

            {/* Dados live */}
            <div className="wl-metrics">
              <div className="wl-metric">
                <small>Preço</small>
                <strong>{e.price != null ? usd.format(e.price) : '—'}</strong>
              </div>
              <div className="wl-metric">
                <small>24h</small>
                <strong className={e.change_24h != null ? (e.change_24h >= 0 ? 'pos' : 'neg') : ''}>
                  {pct(e.change_24h)}
                </strong>
              </div>
              <div className="wl-metric">
                <small>7d</small>
                <strong className={e.change_7d != null ? (e.change_7d >= 0 ? 'pos' : 'neg') : ''}>
                  {pct(e.change_7d)}
                </strong>
              </div>
              <div className="wl-metric">
                <small>Score</small>
                <strong>{score != null ? score.toFixed(0) : '—'}</strong>
                {score != null && <ScoreBar value={score} />}
              </div>
              {e.state && (
                <div className="wl-metric">
                  <small>Estado</small>
                  <span className={`pill ${e.state}`}>{e.state}</span>
                </div>
              )}
            </div>

            {/* Alertas activos */}
            {!isEditing && (e.alert_price_above != null || e.alert_price_below != null || e.alert_score_above != null) && (
              <div className="wl-alerts-row">
                {e.alert_price_above  != null && <span className="alert-chip">↑ Preço &gt; {usd.format(e.alert_price_above)}</span>}
                {e.alert_price_below  != null && <span className="alert-chip">↓ Preço &lt; {usd.format(e.alert_price_below)}</span>}
                {e.alert_score_above  != null && <span className="alert-chip">⬡ Score &gt; {e.alert_score_above}</span>}
              </div>
            )}

            {/* Painel de edição inline */}
            {isEditing && (
              <div className="wl-edit-panel">
                <div className="edit-row">
                  <label>Notas</label>
                  <input value={draft.notes ?? ''} onChange={ev => setDraft(d => ({ ...d, notes: ev.target.value }))} placeholder="Tese de investimento..." />
                </div>
                <div className="edit-row edit-row-3">
                  <div>
                    <label>Alerta preço acima ($)</label>
                    <input type="number" value={draft.alert_price_above ?? ''} onChange={ev => setDraft(d => ({ ...d, alert_price_above: ev.target.value ? +ev.target.value : null }))} placeholder="ex: 70000" />
                  </div>
                  <div>
                    <label>Alerta preço abaixo ($)</label>
                    <input type="number" value={draft.alert_price_below ?? ''} onChange={ev => setDraft(d => ({ ...d, alert_price_below: ev.target.value ? +ev.target.value : null }))} placeholder="ex: 50000" />
                  </div>
                  <div>
                    <label>Alerta score acima</label>
                    <input type="number" value={draft.alert_score_above ?? ''} onChange={ev => setDraft(d => ({ ...d, alert_score_above: ev.target.value ? +ev.target.value : null }))} placeholder="ex: 75" />
                  </div>
                </div>
                <button className="btn" onClick={() => saveEdit(e.id)}>Guardar</button>
              </div>
            )}

            {/* Notas (quando não está a editar) */}
            {!isEditing && e.notes && (
              <p className="wl-notes">"{e.notes}"</p>
            )}
          </div>
        )
      })}
    </div>
  )
}
