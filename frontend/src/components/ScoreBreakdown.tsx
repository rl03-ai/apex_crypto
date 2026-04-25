import { ScoreBar } from './ScoreBar'
const labels: Record<string,string> = {adoption:'Adoção', quality:'Qualidade', valuation:'Valuation', market:'Mercado', catalysts:'Catalisadores', risk:'Risco'}
export function ScoreBreakdown({asset}:{asset: Record<string, number>}) {
  return <div className="breakdown">{Object.keys(labels).map(k => <div className="metric" key={k}><div><span>{labels[k]}</span><b>{Number(asset[k]).toFixed(0)}</b></div><ScoreBar value={Number(asset[k])} /></div>)}</div>
}
