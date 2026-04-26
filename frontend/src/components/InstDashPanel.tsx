import type { InstDashAnalysis } from '../types'

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 4 })
const numFmt = (v: number, dp = 2) => v.toFixed(dp)

interface Props {
  data: InstDashAnalysis
}

export function InstDashPanel({ data }: Props) {
  const setupColor = setupColorFor(data.setup_quality)
  const scoreColor = scoreColorFor(data.score)

  return (
    <div className="instdash-panel">
      {/* Hero do InstDash */}
      <div className="instdash-hero">
        <div>
          <p className="kicker">InstDash · {data.interval} · HTF {data.htf_interval}</p>
          <h2>{data.symbol}</h2>
          <small style={{ color: '#8da2c0' }}>
            Última candle: {new Date(data.last_close_at).toLocaleString('pt-PT')}
          </small>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div className="instdash-score" style={{ color: scoreColor }}>
            <strong>{data.score >= 0 ? '+' : ''}{data.score}</strong>
            <small>/ 16</small>
          </div>
          <span className="instdash-signal-label" style={{ color: scoreColor }}>{data.signal}</span>
        </div>
      </div>

      {/* Setup destaque */}
      <div className="instdash-setup-card" style={{ borderColor: setupColor }}>
        <small>SETUP</small>
        <strong style={{ color: setupColor }}>{data.setup_quality}</strong>
        {data.setup_blocked_by !== 'OK' && (
          <span className="instdash-blocked">⚠ Bloqueado por: {data.setup_blocked_by}</span>
        )}
        {data.setup_quality === 'LONG valido' && (
          <div className="sl-tp-row">
            <span>SL: <strong>{usd.format(data.sl_long)}</strong></span>
            <span>TP: <strong>{usd.format(data.tp_long)}</strong></span>
          </div>
        )}
        {data.setup_quality === 'SHORT valido' && (
          <div className="sl-tp-row">
            <span>SL: <strong>{usd.format(data.sl_short)}</strong></span>
            <span>TP: <strong>{usd.format(data.tp_short)}</strong></span>
          </div>
        )}
      </div>

      {/* Linha de chips de estado */}
      <div className="instdash-row">
        <Chip label="LTF / HTF" value={`${data.ltf_trend} / ${data.htf_trend}`}
          color={data.aligned_bull ? '#22c55e' : data.aligned_bear ? '#fb7185' : '#facc15'} />
        <Chip label="Estrutura" value={structLabel(data.structure.struct_bias)}
          color={data.structure.struct_bias === 1 ? '#22c55e' : data.structure.struct_bias === -1 ? '#fb7185' : '#8da2c0'}
          extra={data.structure.event_bars_ago != null && data.structure.last_event !== 'none'
            ? `${data.structure.last_event} há ${data.structure.event_bars_ago}b`
            : undefined} />
        <Chip label="Squeeze" value={data.squeeze ? 'ATIVO' : 'Inactivo'}
          color={data.squeeze ? '#facc15' : '#8da2c0'} />
        <Chip label="VWAP" value={
          data.vwap_ext_up ? 'Sobre-ext. acima' :
          data.vwap_ext_dn ? 'Sobre-ext. abaixo' :
          data.above_vwap ? 'Acima' : 'Abaixo'
        } color={
          data.vwap_ext_up ? '#fb7185' :
          data.vwap_ext_dn ? '#22c55e' :
          data.above_vwap ? '#22c55e' : '#fb7185'
        } />
      </div>

      {/* Indicadores quantitativos */}
      <div className="instdash-row">
        <Stat label="RSI 14" value={numFmt(data.rsi, 1)}
          color={data.rsi >= 70 ? '#fb7185' : data.rsi <= 30 ? '#22c55e' : '#facc15'} />
        <Stat label="MACD" value={data.macd_bullish ? 'Bullish' : 'Bearish'}
          color={data.macd_bullish ? '#22c55e' : '#fb7185'} />
        <Stat label="ATR %" value={numFmt(data.atr_pct, 2) + '%'}
          color={data.atr_pct > 3 ? '#fb7185' : data.atr_pct > 1.5 ? '#facc15' : '#22c55e'} />
        <Stat label="Vol Rel" value={numFmt(data.vol_ratio, 2) + '×'}
          color={data.vol_ratio >= 1.5 ? '#22c55e' : '#8da2c0'} />
        <Stat label="ADX" value={data.adx != null ? numFmt(data.adx, 1) : '—'}
          color={data.adx == null ? '#8da2c0' : data.adx > 25 ? '#22c55e' : '#facc15'} />
        <Stat label="Delta" value={data.delta_volume >= 0 ? `+${(data.delta_volume / 1000).toFixed(0)}K` : `${(data.delta_volume / 1000).toFixed(0)}K`}
          color={data.delta_volume > 0 ? '#22c55e' : '#fb7185'} />
      </div>

      {/* Zonas: FVG / OB / Liquidity / S-R */}
      <div className="instdash-zones">
        <ZoneCard title="FVG"
          bullActive={data.fvg.in_bull_fvg}  bullRange={range(data.fvg.bull_bot, data.fvg.bull_top)}
          bearActive={data.fvg.in_bear_fvg}  bearRange={range(data.fvg.bear_bot, data.fvg.bear_top)} />
        <ZoneCard title="Order Blocks"
          bullActive={data.order_block.in_bull_ob}  bullRange={range(data.order_block.bull_bot, data.order_block.bull_top)}
          bearActive={data.order_block.in_bear_ob}  bearRange={range(data.order_block.bear_bot, data.order_block.bear_top)} />
        <ZoneCard title="Liquidity Sweeps"
          bullActive={data.liquidity.sweep_low || data.liquidity.near_liq_low}
          bullRange={data.liquidity.liq_low != null ? `Low: ${usd.format(data.liquidity.liq_low)}` : null}
          bearActive={data.liquidity.sweep_high || data.liquidity.near_liq_high}
          bearRange={data.liquidity.liq_high != null ? `High: ${usd.format(data.liquidity.liq_high)}` : null}
          extra={
            data.liquidity.sweep_low ? '⚠ Sweep Low!' :
            data.liquidity.sweep_high ? '⚠ Sweep High!' :
            data.liquidity.near_liq_low ? 'Perto Low' :
            data.liquidity.near_liq_high ? 'Perto High' : null
          } />
        <ZoneCard title="Suporte / Resistência"
          bullActive={data.support_resistance.near_sup}
          bullRange={data.support_resistance.sup_mid != null ? `${usd.format(data.support_resistance.sup_mid)}` : null}
          bearActive={data.support_resistance.near_res}
          bearRange={data.support_resistance.res_mid != null ? `${usd.format(data.support_resistance.res_mid)}` : null}
          extra={
            data.support_resistance.dist_to_sup_pct != null ?
              `Sup ${data.support_resistance.dist_to_sup_pct >= 0 ? '+' : ''}${data.support_resistance.dist_to_sup_pct.toFixed(1)}% · Res ${data.support_resistance.dist_to_res_pct! >= 0 ? '+' : ''}${data.support_resistance.dist_to_res_pct!.toFixed(1)}%`
              : null
          } />
      </div>

      {/* Volume Profile */}
      {data.volume_profile.poc != null && (
        <div className="instdash-vp">
          <div className="vp-line">
            <span>VAH</span>
            <strong>{usd.format(data.volume_profile.vah!)}</strong>
          </div>
          <div className={`vp-line vp-poc ${data.volume_profile.above_poc ? 'above' : 'below'}`}>
            <span>POC</span>
            <strong>{usd.format(data.volume_profile.poc)}</strong>
          </div>
          <div className="vp-line">
            <span>VAL</span>
            <strong>{usd.format(data.volume_profile.val!)}</strong>
          </div>
          <small style={{ marginLeft: 'auto', color: '#8da2c0' }}>
            {data.volume_profile.above_value_area ? 'Acima da Value Area' :
             data.volume_profile.below_value_area ? 'Abaixo da Value Area' :
             data.volume_profile.in_value_area ? 'Dentro da Value Area' : ''}
          </small>
        </div>
      )}

      {/* Breakdown dos 16 factores */}
      <details className="instdash-factors">
        <summary>Score breakdown · {Object.keys(data.factors).length} factores</summary>
        <div className="factors-grid">
          {Object.entries(data.factors).map(([key, val]) => (
            <div key={key} className={`factor-cell factor-${val > 0 ? 'pos' : val < 0 ? 'neg' : 'neu'}`}>
              <span>{factorLabel(key)}</span>
              <strong>{val > 0 ? '+' : ''}{val}</strong>
            </div>
          ))}
        </div>
      </details>
    </div>
  )
}

// ── Sub-componentes ──────────────────────────────────────────────────────────

function Chip({ label, value, color, extra }: { label: string; value: string; color: string; extra?: string }) {
  return (
    <div className="instdash-chip" style={{ borderLeftColor: color }}>
      <small>{label}</small>
      <strong style={{ color }}>{value}</strong>
      {extra && <span className="chip-extra">{extra}</span>}
    </div>
  )
}

function Stat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="instdash-stat">
      <small>{label}</small>
      <strong style={{ color }}>{value}</strong>
    </div>
  )
}

function ZoneCard({ title, bullActive, bullRange, bearActive, bearRange, extra }: {
  title: string
  bullActive: boolean
  bullRange: string | null
  bearActive: boolean
  bearRange: string | null
  extra?: string | null
}) {
  return (
    <div className="zone-card">
      <small>{title}</small>
      <div className={`zone-line ${bullActive ? 'active-bull' : ''}`}>
        <span>↗ Bull</span>
        <strong>{bullRange ?? '—'}</strong>
      </div>
      <div className={`zone-line ${bearActive ? 'active-bear' : ''}`}>
        <span>↘ Bear</span>
        <strong>{bearRange ?? '—'}</strong>
      </div>
      {extra && <small className="zone-extra">{extra}</small>}
    </div>
  )
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function range(bot: number | null, top: number | null): string | null {
  if (bot == null || top == null) return null
  return `${usd.format(bot)} – ${usd.format(top)}`
}

function structLabel(bias: number): string {
  return bias === 1 ? 'Bullish' : bias === -1 ? 'Bearish' : 'Indefinida'
}

function setupColorFor(setup: string): string {
  if (setup === 'LONG valido') return '#22c55e'
  if (setup === 'SHORT valido') return '#fb7185'
  if (setup === 'Aguardar zona') return '#facc15'
  if (setup === 'Aguarda SQ') return '#f59e0b'
  if (setup === 'TF divergente') return '#fb923c'
  return '#6b7fa0'
}

function scoreColorFor(score: number): string {
  if (score >= 8) return '#22c55e'
  if (score >= 5) return '#86efac'
  if (score <= -8) return '#fb7185'
  if (score <= -5) return '#fda4af'
  return '#facc15'
}

const FACTOR_LABELS: Record<string, string> = {
  ltf_trend:    'LTF Trend',
  htf_trend:    'HTF Trend',
  structure:    'Estrutura',
  macd:         'MACD',
  rsi:          'RSI',
  bb_position:  'BB Pos',
  vwap:         'VWAP',
  volume_dir:   'Volume Dir',
  delta:        'Delta',
  vol_divergence: 'Vol Div',
  htf_rsi:      'HTF RSI',
  vwap_extended: 'VWAP Ext',
  fvg:          'FVG',
  ob:           'Order Block',
  vp_position:  'VP Position',
  sweep:        'Sweep',
}
function factorLabel(key: string) { return FACTOR_LABELS[key] || key }
