import type { Payload } from '../types'

interface Props {
  payload: Payload
  selected: string[]
  onChange: (vars: string[]) => void
  laneVisible: { alarms: boolean; modes: boolean; events: boolean }
  onLaneChange: (lanes: { alarms: boolean; modes: boolean; events: boolean }) => void
}

export default function VariablePicker({ payload, selected, onChange, laneVisible, onLaneChange }: Props) {
  const toggle = (v: string) => {
    onChange(selected.includes(v) ? selected.filter((x) => x !== v) : [...selected, v])
  }
  const toggleLane = (k: keyof typeof laneVisible) => onLaneChange({ ...laneVisible, [k]: !laneVisible[k] })

  return (
    <div className="varbar">
      <span className="lbl">Lanes:</span>
      {(['alarms', 'modes', 'events'] as const).map((k) => (
        <label key={k} className="chk">
          <input type="checkbox" checked={laneVisible[k]} onChange={() => toggleLane(k)} />
          {k[0].toUpperCase() + k.slice(1)}
        </label>
      ))}
      <span className="lbl" style={{ marginLeft: 14 }}>Y axis:</span>
      {payload.vars.map((v) => (
        <label key={v} className="chk">
          <input type="checkbox" checked={selected.includes(v)} onChange={() => toggle(v)} />
          {v}
        </label>
      ))}
    </div>
  )
}
