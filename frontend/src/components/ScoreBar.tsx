export function ScoreBar({ value }: { value: number }) { return <div className="bar"><span style={{width: `${Math.max(0, Math.min(100, value))}%`}} /></div> }
