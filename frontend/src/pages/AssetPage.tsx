import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Area, AreaChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { fetchDetail, fetchChart } from '../api/endpoints'
import type { AssetDetail, ChartPoint } from '../types'
import { ScoreBar } from '../components/ScoreBar'

// ── formatadores ──────────────────────────────────────────────────────────────
const usd     = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
const usdCmp  = new Intl.NumberFormat('en-US', { notation: 'compact', style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
const numCmp  = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 2 })
const pct = (v: number | null | undefined, dp = 1) =>
  v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(dp)}%`

function fmt(v: number | null | undefined): string {
  if (v == null) return '—'
  if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(2)}B`
  if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(2)}M`
  if (Math.abs(v) >= 1e3) return `$${(v / 1e3).toFixed(2)}K`
  return usd.format(v)
}

function fmtSupply(v: number | null | undefined): string {
  if (v == null) return '—'
  return numCmp.format(v)
}

// ── Score Radar (6 barras horizontais) ────────────────────────────────────────
function ScoreRadar({ asset }: { asset: AssetDetail }) {
  const dims: [string, number, string][] = [
    ['Adoção',       asset.adoption,   'Rank + liquidez'],
    ['Qualidade',    asset.quality,    'Market cap + rank'],
    ['Valuation',    asset.valuation,  'Distância ao ATH'],
    ['Mercado',      asset.market,     'Momentum multi-prazo'],
    ['Catalisadores', asset.catalysts, 'Volume spike + momentum'],
    ['Risco (inv.)', 100 - asset.risk, 'Inverso da volatilidade'],
  ]
  return (
    <div className="score-radar">
      {dims.map(([label, value, hint]) => (
        <div key={label} className="radar-row">
          <div className="radar-label">
            <span>{label}</span>
            <small>{hint}</small>
          </div>
          <div className="radar-bar-wrap">
            <div className="radar-bar" style={{ width: `${value}%`, background: barColor(value) }} />
          </div>
          <span className="radar-val" style={{ color: barColor(value) }}>{value.toFixed(0)}</span>
        </div>
      ))}
    </div>
  )
}

function barColor(v: number): string {
  if (v >= 70) return '#22c55e'
  if (v >= 50) return '#f59e0b'
  return '#fb7185'
}

// ── Tokenomics Panel ──────────────────────────────────────────────────────────
function TokenomicsPanel({ t, mcap }: { t: AssetDetail['tokenomics']; mcap: number | null }) {
  const circPct  = t.circulating_pct ?? 0
  const fdvRatio = t.fdv_ratio

  return (
    <div className="panel-grid">
      <div className="panel-item">
        <small>Circulação</small>
        <strong>{fmtSupply(t.circulating_supply)}</strong>
        {t.circulating_pct != null && (
          <>
            <div className="supply-bar-wrap">
              <div className="supply-bar" style={{ width: `${circPct}%` }} />
            </div>
            <span className="supply-hint">{circPct}% do supply máximo</span>
          </>
        )}
      </div>

      <div className="panel-item">
        <small>Total Supply</small>
        <strong>{fmtSupply(t.total_supply)}</strong>
      </div>

      <div className="panel-item">
        <small>Max Supply</small>
        <strong>{t.max_supply != null ? fmtSupply(t.max_supply) : '∞ Ilimitado'}</strong>
      </div>

      <div className="panel-item">
        <small>FDV</small>
        <strong>{fmt(t.fdv)}</strong>
        {fdvRatio != null && (
          <span className={`fdv-tag ${fdvRatio > 2 ? 'warn' : fdvRatio > 1.2 ? 'caution' : 'ok'}`}>
            {fdvRatio.toFixed(2)}× Market Cap
          </span>
        )}
      </div>

      {t.genesis_date && (
        <div className="panel-item">
          <small>Genesis</small>
          <strong>{t.genesis_date}</strong>
        </div>
      )}
    </div>
  )
}

// ── ATH/ATL Panel ─────────────────────────────────────────────────────────────
function AthAtlPanel({ aa }: { aa: AssetDetail['ath_atl'] }) {
  const athPct = aa.ath_change_pct ?? 0  // negativo — distância ao ATH
  const atlPct = aa.atl_change_pct ?? 0  // positivo — ganho desde ATL

  // Progresso entre ATL e ATH: onde está o preço actual?
  const progressToAth = athPct >= 0 ? 100 : Math.max(0, 100 + athPct)

  return (
    <div className="ath-atl-panel">
      <div className="ath-row">
        <div>
          <small>ATH (máximo histórico)</small>
          <strong>{aa.ath != null ? usd.format(aa.ath) : '—'}</strong>
          <span className="neg">{pct(aa.ath_change_pct)} do ATH</span>
        </div>
        <div>
          <small>ATL (mínimo histórico)</small>
          <strong>{aa.atl != null ? fmt(aa.atl) : '—'}</strong>
          <span className="pos">{pct(aa.atl_change_pct)} do ATL</span>
        </div>
      </div>

      <div>
        <small style={{ color: '#6b7fa0', marginBottom: 6, display: 'block' }}>
          Recuperação desde ATL → {progressToAth.toFixed(0)}% do caminho para o ATH
        </small>
        <div className="ath-progress-wrap">
          <div className="ath-progress-bar" style={{ width: `${progressToAth}%` }} />
        </div>
        <div className="ath-labels">
          <span>ATL</span>
          <span>ATH</span>
        </div>
      </div>
    </div>
  )
}

// ── TVL Panel ─────────────────────────────────────────────────────────────────
function TvlPanel({ tvl }: { tvl: AssetDetail['tvl'] }) {
  if (!tvl || !tvl.tvl) return null
  return (
    <div className="tvl-panel">
      <div className="tvl-header">
        <span className="tvl-badge">{tvl.kind === 'chain' ? '⛓ Chain' : '⬡ Protocol'}</span>
        <span className="tvl-source">DefiLlama</span>
      </div>
      <strong className="tvl-value">{fmt(tvl.tvl)}</strong>
      <small>Total Value Locked</small>
      {(tvl.tvl_1d_change != null || tvl.tvl_7d_change != null) && (
        <div className="tvl-changes">
          {tvl.tvl_1d_change != null && (
            <span className={tvl.tvl_1d_change >= 0 ? 'pos' : 'neg'}>24h {pct(tvl.tvl_1d_change)}</span>
          )}
          {tvl.tvl_7d_change != null && (
            <span className={tvl.tvl_7d_change >= 0 ? 'pos' : 'neg'}>7d {pct(tvl.tvl_7d_change)}</span>
          )}
        </div>
      )}
    </div>
  )
}

// ── Community Panel ───────────────────────────────────────────────────────────
function CommunityPanel({ c }: { c: AssetDetail['community'] }) {
  const items = [
    { label: 'Reddit', icon: '📡', value: c.reddit_subscribers, link: null },
    { label: 'Twitter/X', icon: '𝕏', value: c.twitter_followers, link: null },
    { label: 'Telegram', icon: '✈', value: c.telegram_user_count, link: null },
  ].filter(i => i.value != null)

  if (items.length === 0) return null
  return (
    <div className="community-grid">
      {items.map(i => (
        <div key={i.label} className="community-item">
          <span className="community-icon">{i.icon}</span>
          <div>
            <small>{i.label}</small>
            <strong>{numCmp.format(i.value!)}</strong>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Tooltip customizado do gráfico ────────────────────────────────────────────
function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#0d1a2e', border: '1px solid #263a5d', borderRadius: 10, padding: '8px 14px' }}>
      <small style={{ color: '#8da2c0' }}>{label}</small>
      <div style={{ fontWeight: 700 }}>{usd.format(payload[0].value)}</div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export function AssetPage() {
  const { id = '' } = useParams()
  const nav = useNavigate()
  const [asset,   setAsset]   = useState<AssetDetail | null>(null)
  const [chart,   setChart]   = useState<ChartPoint[]>([])
  const [days,    setDays]    = useState(90)
  const [loading, setLoading] = useState(true)
  const [err,     setErr]     = useState('')

  useEffect(() => {
    setLoading(true); setErr('')
    Promise.all([
      fetchDetail(id).then(setAsset).catch(() => setErr('Ativo não encontrado ou erro de rede')),
      fetchChart(id, days).then(setChart).catch(() => setChart([])),
    ]).finally(() => setLoading(false))
  }, [id, days])

  if (loading) return <div className="card loading-card">A carregar detalhe...</div>
  if (err || !asset) return (
    <div className="card" style={{ textAlign: 'center', padding: 48 }}>
      <p>{err || 'Ativo não encontrado'}</p>
      <button className="btn" style={{ marginTop: 16 }} onClick={() => nav('/')}>← Scanner</button>
    </div>
  )

  const chartData = chart.map(p => ({
    price: p.price,
    label: typeof p.date === 'number'
      ? new Date(p.date).toLocaleDateString('pt-PT', { day: '2-digit', month: 'short' })
      : String(p.date),
  }))

  return (
    <div className="stack">
      {/* Breadcrumb */}
      <button className="btn-ghost" style={{ alignSelf: 'flex-start' }} onClick={() => nav('/')}>
        ← Scanner
      </button>

      {/* Hero */}
      <section className="hero card">
        <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', gridColumn: '1' }}>
          {asset.image && <img src={asset.image} alt={asset.name} className="asset-logo" />}
          <div>
            <p className="kicker">Rank #{asset.rank} · {asset.categories.slice(0, 2).join(' · ')}</p>
            <h1>{asset.name} <span style={{ color: '#8da2c0', fontWeight: 400, fontSize: '0.6em' }}>{asset.symbol}</span></h1>
            <div className="hero-prices">
              <span className="hero-price">{asset.price != null ? usd.format(asset.price) : '—'}</span>
              <span className={asset.change_24h != null ? (asset.change_24h >= 0 ? 'pos' : 'neg') : ''}>
                {pct(asset.change_24h)} 24h
              </span>
              <span className={asset.change_7d != null ? (asset.change_7d >= 0 ? 'pos' : 'neg') : ''}>
                {pct(asset.change_7d)} 7d
              </span>
            </div>
            {asset.description && (
              <p className="asset-desc">{asset.description}</p>
            )}
            {/* Links */}
            <div className="asset-links">
              {asset.links.homepage   && <a href={asset.links.homepage} target="_blank" rel="noopener" className="link-chip">🌐 Website</a>}
              {asset.links.blockchain_site && <a href={asset.links.blockchain_site} target="_blank" rel="noopener" className="link-chip">⬡ Explorer</a>}
              {asset.links.twitter    && <a href={`https://twitter.com/${asset.links.twitter}`} target="_blank" rel="noopener" className="link-chip">𝕏 Twitter</a>}
              {asset.links.subreddit  && <a href={asset.links.subreddit} target="_blank" rel="noopener" className="link-chip">💬 Reddit</a>}
            </div>
          </div>
        </div>

        {/* Score + TVL à direita */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="score-big">
            <span>Score total</span>
            <strong style={{ color: barColor(asset.total_score) }}>{asset.total_score.toFixed(0)}</strong>
            <span className={`pill ${asset.state}`} style={{ display: 'inline-block', marginTop: 8 }}>{asset.state}</span>
          </div>
          {asset.tvl && <TvlPanel tvl={asset.tvl} />}
        </div>
      </section>

      {/* Métricas de market */}
      <div className="market-metrics">
        {[
          ['Market Cap',  fmt(asset.market_cap)],
          ['Volume 24h',  fmt(asset.volume_24h)],
          ['30d',         pct(asset.change_30d)],
          ['Dist. ATH',   pct(asset.ath_atl?.ath_change_pct)],
        ].map(([label, value]) => (
          <div key={label} className="card metric-chip">
            <small>{label}</small>
            <strong className={
              label.startsWith('30d') || label.startsWith('Dist') 
                ? (parseFloat(String(value)) >= 0 ? 'pos' : 'neg')
                : ''
            }>{value}</strong>
          </div>
        ))}
      </div>

      {/* Gráfico */}
      <section className="card">
        <div className="section-head">
          <h2>Preço</h2>
          <div className="filter-tabs">
            {[30, 90, 180, 365].map(d => (
              <button key={d} className={`tab ${days === d ? 'active' : ''}`} onClick={() => setDays(d)}>
                {d === 365 ? '1a' : d === 180 ? '6m' : d === 90 ? '3m' : '1m'}
              </button>
            ))}
          </div>
        </div>
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={chartData} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0}   />
              </linearGradient>
            </defs>
            <XAxis dataKey="label" hide tick={{ fill: '#6b7fa0', fontSize: 11 }} />
            <YAxis domain={['dataMin', 'dataMax']} hide />
            <Tooltip content={<ChartTooltip />} />
            <Area type="monotone" dataKey="price" stroke="#6366f1" strokeWidth={2}
              fill="url(#priceGrad)" dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </section>

      {/* Score breakdown + ATH/ATL */}
      <div className="grid2">
        <section className="card">
          <h2>Score breakdown</h2>
          <p style={{ color: '#8da2c0', fontSize: 13, margin: '4px 0 16px' }}>
            Total: {asset.total_score.toFixed(1)} · Prioridade: {asset.priority_score.toFixed(1)}
          </p>
          <ScoreRadar asset={asset} />
        </section>

        <section className="card">
          <h2>ATH / ATL</h2>
          <AthAtlPanel aa={asset.ath_atl} />
        </section>
      </div>

      {/* Tokenomics */}
      <section className="card">
        <h2>Tokenomics</h2>
        <p style={{ color: '#8da2c0', fontSize: 13, margin: '4px 0 16px' }}>
          Supply e distribuição
        </p>
        <TokenomicsPanel t={asset.tokenomics} mcap={asset.market_cap} />
      </section>

      {/* Community + Razões */}
      <div className="grid2">
        <section className="card">
          <h2>Comunidade</h2>
          <CommunityPanel c={asset.community} />
        </section>

        <section className="card">
          <h2>Análise do score</h2>
          <ul className="reasons-list">
            {asset.why_selected.map(r => <li key={r}>{r}</li>)}
          </ul>
        </section>
      </div>
    </div>
  )
}
