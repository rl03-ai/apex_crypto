/**
 * Mini-gráfico de linha em SVG puro (sem dependências).
 * Usado no scanner para mostrar tendência de 7 dias num espaço pequeno.
 */
export function Sparkline({ data, width = 80, height = 24, positive }: {
  data: number[]
  width?: number
  height?: number
  positive?: boolean   // override; senão calcula pelo first vs last
}) {
  if (!data || data.length < 2) {
    return <svg width={width} height={height} />
  }

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const stepX = width / (data.length - 1)

  const points = data
    .map((v, i) => `${(i * stepX).toFixed(1)},${(height - ((v - min) / range) * height).toFixed(1)}`)
    .join(' ')

  const isPos = positive ?? (data[data.length - 1] >= data[0])
  const stroke = isPos ? '#22c55e' : '#fb7185'
  const fill = isPos ? 'rgba(34, 197, 94, 0.12)' : 'rgba(251, 113, 133, 0.12)'

  // Polígono fechado para o fill (do gráfico até à base)
  const fillPoints = `0,${height} ${points} ${width},${height}`

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <polygon points={fillPoints} fill={fill} />
      <polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}
