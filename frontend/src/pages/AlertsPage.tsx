import { useEffect, useState } from 'react'
import { fetchAlerts, markRead, markAllRead, deleteAlert } from '../api/endpoints'
import type { Alert } from '../types'

const TIME_FMT = new Intl.DateTimeFormat('pt-PT', { dateStyle: 'short', timeStyle: 'short' })

const SEVERITY_COLOR: Record<string, string> = {
  info:     '#60a5fa',
  warning:  '#facc15',
  critical: '#fb7185',
}

const TYPE_LABEL: Record<string, string> = {
  price_above: '↑ Preço',
  price_below: '↓ Preço',
  score_above: '⬡ Score',
  system:      '⚙ Sistema',
}

export function AlertsPage() {
  const [alerts,   setAlerts]  = useState<Alert[]>([])
  const [loading,  setLoading] = useState(true)
  const [showAll,  setShowAll] = useState(false)

  const load = () =>
    fetchAlerts(showAll)
      .then(setAlerts)
      .catch(() => setAlerts([]))
      .finally(() => setLoading(false))

  useEffect(() => { load() }, [showAll])

  async function handleMarkRead(id: string) {
    const updated = await markRead(id)
    setAlerts(prev => prev.map(a => a.id === id ? updated : a))
  }

  async function handleMarkAll() {
    await markAllRead()
    setAlerts(prev => prev.map(a => ({ ...a, is_read: true })))
  }

  async function handleDelete(id: string) {
    await deleteAlert(id)
    setAlerts(prev => prev.filter(a => a.id !== id))
  }

  const unread = alerts.filter(a => !a.is_read).length

  if (loading) return <div className="card loading-card">A carregar alertas...</div>

  return (
    <div className="stack">
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Alertas {unread > 0 && <span className="badge">{unread}</span>}</h2>
            <small style={{ color: '#8da2c0' }}>Preço, score e notificações do sistema</small>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center', color: '#8da2c0', cursor: 'pointer' }}>
              <input type="checkbox" checked={showAll} onChange={e => setShowAll(e.target.checked)} />
              Mostrar lidos
            </label>
            {unread > 0 && (
              <button className="btn-ghost" onClick={handleMarkAll}>✓ Marcar todos como lidos</button>
            )}
          </div>
        </div>
      </section>

      {alerts.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px' }}>
          <p style={{ fontSize: 48, margin: 0 }}>◎</p>
          <h2>{showAll ? 'Sem alertas' : 'Sem alertas não lidos'}</h2>
          <p style={{ color: '#8da2c0' }}>
            {showAll
              ? 'Ainda não foram gerados alertas.'
              : 'Todos os alertas foram lidos.'}
          </p>
          {!showAll && <button className="btn-ghost" onClick={() => setShowAll(true)}>Ver histórico</button>}
        </div>
      ) : (
        alerts.map(a => (
          <div key={a.id} className={`card alert-card ${a.is_read ? 'read' : ''}`}>
            <div className="alert-bar" style={{ background: SEVERITY_COLOR[a.severity] ?? '#60a5fa' }} />
            <div className="alert-body">
              <div className="alert-meta">
                <span className="alert-type">{TYPE_LABEL[a.alert_type] ?? a.alert_type}</span>
                {a.coin_id && <span className="alert-coin">{a.coin_id.toUpperCase()}</span>}
                <span className="alert-time">{TIME_FMT.format(new Date(a.created_at))}</span>
              </div>
              <strong className="alert-title">{a.title}</strong>
              <p className="alert-msg">{a.message}</p>
            </div>
            <div className="alert-actions">
              {!a.is_read && (
                <button className="btn-ghost" onClick={() => handleMarkRead(a.id)} title="Marcar como lido">✓</button>
              )}
              <button className="btn-ghost danger" onClick={() => handleDelete(a.id)} title="Eliminar">✕</button>
            </div>
          </div>
        ))
      )}
    </div>
  )
}
