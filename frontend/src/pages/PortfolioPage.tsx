import { useEffect, useState } from 'react'
import {
  fetchPortfolios, createPortfolio, fetchPortfolio,
  refreshPortfolio, createPosition, deletePosition,
} from '../api/endpoints'
import type { Portfolio, PortfolioSummary, Position } from '../types'
import { ScoreBar } from '../components/ScoreBar'

const usd     = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
const pctFmt  = (v: number | null | undefined) =>
  v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`

// ── Add Position Form ─────────────────────────────────────────────────────────
function AddPositionModal({ portfolioId, onClose, onSaved }: {
  portfolioId: string
  onClose: () => void
  onSaved: () => void
}) {
  const [form, setForm] = useState({
    coin_id: '', symbol: '', name: '',
    first_buy_date: new Date().toISOString().slice(0, 10),
    avg_cost: '', quantity: '',
    horizon: 'long', thesis: '', exchange: '',
    target_price: '', stop_loss: '',
  })
  const [saving, setSaving] = useState(false)
  const [err,    setErr]    = useState('')

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }))

  async function submit() {
    if (!form.coin_id || !form.avg_cost || !form.quantity) { setErr('coin_id, preço e quantidade são obrigatórios'); return }
    setSaving(true); setErr('')
    try {
      await createPosition(portfolioId, {
        ...form,
        avg_cost: parseFloat(form.avg_cost),
        quantity: parseFloat(form.quantity),
        target_price: form.target_price ? parseFloat(form.target_price) : null,
        stop_loss: form.stop_loss ? parseFloat(form.stop_loss) : null,
      })
      onSaved()
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Erro')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <div className="modal-head">
          <h3>Nova posição</h3>
          <button className="btn-ghost" onClick={onClose}>✕</button>
        </div>
        {err && <p className="err-msg">{err}</p>}
        <div className="modal-grid">
          <label>Coin ID (CoinGecko)<br/>
            <input placeholder="ex: bitcoin" value={form.coin_id} onChange={set('coin_id')} />
          </label>
          <label>Symbol<br/>
            <input placeholder="ex: BTC" value={form.symbol} onChange={set('symbol')} />
          </label>
          <label>Nome<br/>
            <input placeholder="ex: Bitcoin" value={form.name} onChange={set('name')} />
          </label>
          <label>Exchange<br/>
            <input placeholder="ex: Binance" value={form.exchange} onChange={set('exchange')} />
          </label>
          <label>Preço de compra ($)<br/>
            <input type="number" placeholder="42000" value={form.avg_cost} onChange={set('avg_cost')} />
          </label>
          <label>Quantidade<br/>
            <input type="number" placeholder="0.5" value={form.quantity} onChange={set('quantity')} />
          </label>
          <label>Data de compra<br/>
            <input type="date" value={form.first_buy_date} onChange={set('first_buy_date')} />
          </label>
          <label>Horizonte<br/>
            <select value={form.horizon} onChange={set('horizon')}>
              <option value="short">Short</option>
              <option value="swing">Swing</option>
              <option value="long">Long</option>
            </select>
          </label>
          <label>Target ($)<br/>
            <input type="number" placeholder="opcional" value={form.target_price} onChange={set('target_price')} />
          </label>
          <label>Stop Loss ($)<br/>
            <input type="number" placeholder="opcional" value={form.stop_loss} onChange={set('stop_loss')} />
          </label>
          <label className="span2">Tese<br/>
            <textarea placeholder="Razão do investimento..." value={form.thesis} onChange={set('thesis')} rows={2} />
          </label>
        </div>
        <div className="modal-footer">
          <button className="btn-ghost" onClick={onClose}>Cancelar</button>
          <button className="btn" onClick={submit} disabled={saving}>{saving ? 'A guardar…' : 'Abrir posição'}</button>
        </div>
      </div>
    </div>
  )
}

// ── Positions Table ───────────────────────────────────────────────────────────
function PositionsTable({ positions, portfolioId, onDeleted }: {
  positions: Position[]
  portfolioId: string
  onDeleted: (id: string) => void
}) {
  if (positions.length === 0)
    return <p style={{ color: '#8da2c0', padding: '16px 0' }}>Sem posições abertas. Adiciona a primeira posição acima.</p>

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Moeda</th><th>Qtd</th><th>Preço médio</th>
            <th>Preço actual</th><th>Investido</th><th>Valor actual</th>
            <th>P&L</th><th>P&L %</th><th>Horizonte</th><th></th>
          </tr>
        </thead>
        <tbody>
          {positions.map(p => (
            <tr key={p.id}>
              <td>
                <strong>{p.symbol || p.coin_id.toUpperCase()}</strong>
                <small>{p.name}</small>
              </td>
              <td>{p.quantity}</td>
              <td>{usd.format(p.avg_cost)}</td>
              <td>{p.current_price != null ? usd.format(p.current_price) : <span style={{color:'#8da2c0'}}>—</span>}</td>
              <td>{usd.format(p.invested_amount)}</td>
              <td>{p.current_value != null ? usd.format(p.current_value) : <span style={{color:'#8da2c0'}}>—</span>}</td>
              <td className={p.pnl != null ? (p.pnl >= 0 ? 'pos' : 'neg') : ''}>
                {p.pnl != null ? usd.format(p.pnl) : '—'}
              </td>
              <td className={p.pnl_pct != null ? (p.pnl_pct >= 0 ? 'pos' : 'neg') : ''}>
                {pctFmt(p.pnl_pct)}
              </td>
              <td><span className="pill">{p.horizon ?? '—'}</span></td>
              <td>
                <button className="btn-ghost danger" onClick={async () => {
                  if (!confirm(`Eliminar posição ${p.symbol}?`)) return
                  await deletePosition(portfolioId, p.id)
                  onDeleted(p.id)
                }}>✕</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Portfolio Detail ──────────────────────────────────────────────────────────
function PortfolioDetail({ portfolioId, onBack }: { portfolioId: string; onBack: () => void }) {
  const [summary,    setSummary]    = useState<PortfolioSummary | null>(null)
  const [loading,    setLoading]    = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [showAdd,    setShowAdd]    = useState(false)

  const load = () => fetchPortfolio(portfolioId).then(setSummary).finally(() => setLoading(false))
  useEffect(() => { load() }, [portfolioId])

  async function doRefresh() {
    setRefreshing(true)
    await refreshPortfolio(portfolioId)
    await load()
    setRefreshing(false)
  }

  if (loading || !summary) return <div className="card loading-card">A carregar portfolio...</div>

  const { portfolio, positions, total_invested, total_value, total_pnl, total_pnl_pct } = summary

  return (
    <div className="stack">
      <div className="card">
        <div className="section-head">
          <div>
            <button className="btn-ghost" onClick={onBack} style={{ marginBottom: 8 }}>← Portfolios</button>
            <h2>{portfolio.name}</h2>
            <small style={{ color: '#8da2c0' }}>{portfolio.base_currency}</small>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button className="btn-ghost" onClick={doRefresh} disabled={refreshing}>
              {refreshing ? '↻ A actualizar...' : '↻ Actualizar preços'}
            </button>
            <button className="btn" onClick={() => setShowAdd(true)}>+ Posição</button>
          </div>
        </div>

        {/* Sumário P&L */}
        <div className="pnl-grid">
          <div className="pnl-card">
            <small>Investido</small>
            <strong>{usd.format(total_invested)}</strong>
          </div>
          <div className="pnl-card">
            <small>Valor actual</small>
            <strong>{usd.format(total_value)}</strong>
          </div>
          <div className="pnl-card">
            <small>P&L</small>
            <strong className={total_pnl >= 0 ? 'pos' : 'neg'}>
              {usd.format(total_pnl)}
            </strong>
          </div>
          <div className="pnl-card">
            <small>P&L %</small>
            <strong className={total_pnl_pct >= 0 ? 'pos' : 'neg'}>
              {pctFmt(total_pnl_pct)}
            </strong>
          </div>
        </div>
      </div>

      {/* Exposição por moeda */}
      {positions.length > 0 && total_value > 0 && (
        <div className="card">
          <h3>Exposição</h3>
          <div className="exposure-bars">
            {positions
              .filter(p => p.current_value != null)
              .sort((a, b) => (b.current_value ?? 0) - (a.current_value ?? 0))
              .map(p => {
                const pct = ((p.current_value ?? 0) / total_value) * 100
                return (
                  <div key={p.id} className="exposure-row">
                    <span className="exposure-sym">{p.symbol || p.coin_id.toUpperCase()}</span>
                    <div className="exposure-bar-wrap">
                      <div className="exposure-bar" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="exposure-pct">{pct.toFixed(1)}%</span>
                    <span className="exposure-val">{usd.format(p.current_value ?? 0)}</span>
                  </div>
                )
              })}
          </div>
        </div>
      )}

      {/* Tabela de posições */}
      <div className="card">
        <h3>Posições</h3>
        <PositionsTable
          positions={positions}
          portfolioId={portfolio.id}
          onDeleted={id => setSummary(s => s ? { ...s, positions: s.positions.filter(p => p.id !== id) } : s)}
        />
      </div>

      {showAdd && (
        <AddPositionModal
          portfolioId={portfolioId}
          onClose={() => setShowAdd(false)}
          onSaved={() => { setShowAdd(false); load() }}
        />
      )}
    </div>
  )
}

// ── Main Portfolio Page ───────────────────────────────────────────────────────
export function PortfolioPage() {
  const [portfolios,  setPortfolios]  = useState<Portfolio[]>([])
  const [selected,    setSelected]    = useState<string | null>(null)
  const [loading,     setLoading]     = useState(true)
  const [newName,     setNewName]     = useState('')
  const [creating,    setCreating]    = useState(false)

  const load = () => fetchPortfolios().then(setPortfolios).finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  async function handleCreate() {
    if (!newName.trim()) return
    setCreating(true)
    const p = await createPortfolio(newName.trim())
    setPortfolios(prev => [...prev, p])
    setNewName('')
    setSelected(p.id)
    setCreating(false)
  }

  if (selected) return <PortfolioDetail portfolioId={selected} onBack={() => setSelected(null)} />

  if (loading) return <div className="card loading-card">A carregar portfolios...</div>

  return (
    <div className="stack">
      <section className="card">
        <div className="section-head">
          <h2>Portfolios</h2>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <input
              className="inline-input"
              placeholder="Nome do portfolio"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleCreate()}
            />
            <button className="btn" onClick={handleCreate} disabled={creating || !newName.trim()}>
              {creating ? '…' : '+ Criar'}
            </button>
          </div>
        </div>

        {portfolios.length === 0 ? (
          <p style={{ color: '#8da2c0', padding: '32px 0', textAlign: 'center' }}>
            Sem portfolios. Cria o primeiro acima.
          </p>
        ) : (
          <div className="portfolio-grid">
            {portfolios.map(p => (
              <button key={p.id} className="portfolio-card-btn" onClick={() => setSelected(p.id)}>
                <span className="portfolio-icon">◈</span>
                <strong>{p.name}</strong>
                <small>{p.base_currency}</small>
                <span className="portfolio-arrow">→</span>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
