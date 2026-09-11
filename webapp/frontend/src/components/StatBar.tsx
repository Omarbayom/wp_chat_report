import type { Meta } from '../types'

export default function StatBar({ meta }: { meta: Meta }) {
  const stats: [string, number][] = [
    ['cyclic samples', meta.nSamples],
    ['mode changes', meta.nModes],
    ['events', meta.nEvents],
    ['alarms', meta.nAlarms],
  ]
  return (
    <div className="statbar">
      {stats.map(([label, n]) => (
        <div className="stat" key={label}>
          <b>{n.toLocaleString()}</b>
          <span>{label}</span>
        </div>
      ))}
      {meta.nBurstsDropped > 0 && (
        <div className="stat muted-stat" title="Photo bursts outside cyclic data coverage">
          <b>{meta.nBurstsDropped}</b>
          <span>bursts dropped</span>
        </div>
      )}
    </div>
  )
}
