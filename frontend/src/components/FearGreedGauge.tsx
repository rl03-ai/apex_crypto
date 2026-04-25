import type { FearGreed } from '../types'

function color(v: number): string {
  if (v <= 25) return '#fb7185'   // extreme fear
  if (v <= 45) return '#f97316'   // fear
  if (v <= 55) return '#facc15'   // neutral
  if (v <= 75) return '#86efac'   // greed
  return '#34d399'                 // extreme greed
}

export function FearGreedGauge({ data }: { data: FearGreed | null }) {
  if (!data) return <div className="card stat"><span>Fear & Greed</span><strong>—</strong></div>

  const c = color(data.value)
  const deg = (data.value / 100) * 180 - 90  // -90 … +90

  return (
    <div className="card fg-card">
      <span className="fg-label-top">Fear &amp; Greed</span>
      <div className="fg-gauge">
        <svg viewBox="0 0 120 70" width="120" height="70">
          {/* arco de fundo */}
          <path d="M10,60 A50,50 0 0,1 110,60" fill="none" stroke="#1d2d49" strokeWidth="12" strokeLinecap="round"/>
          {/* arco colorido proporcional */}
          <path
            d="M10,60 A50,50 0 0,1 110,60"
            fill="none"
            stroke={c}
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={`${data.value * 1.57} 157`}
          />
          {/* agulha */}
          <line
            x1="60" y1="60"
            x2={60 + 38 * Math.cos((deg - 90) * Math.PI / 180)}
            y2={60 + 38 * Math.sin((deg - 90) * Math.PI / 180)}
            stroke={c} strokeWidth="2.5" strokeLinecap="round"
          />
          <circle cx="60" cy="60" r="4" fill={c} />
          <text x="60" y="52" textAnchor="middle" fontSize="18" fontWeight="700" fill={c}>{data.value}</text>
        </svg>
      </div>
      <strong style={{ color: c }}>{data.label}</strong>
    </div>
  )
}
