import { useMemo, useState } from 'react'
import type { EventPoint, Meta, ModeInterval, Payload } from '../types'
import Plot from '../Plot'
import { buildFigure } from '../lib/report'
import StatBar from './StatBar'
import PatientBanner from './PatientBanner'
import VariablePicker from './VariablePicker'
import Ledger from './Ledger'
import DetailModal from './DetailModal'

interface Props {
  payload: Payload
  meta: Meta
  onReset: () => void
}

type LaneVisible = { alarms: boolean; modes: boolean; events: boolean }

export default function ReportView({ payload, meta, onReset }: Props) {
  const [selectedVars, setSelectedVars] = useState<string[]>(payload.defaultVars)
  const [laneVisible, setLaneVisible] = useState<LaneVisible>({ alarms: true, modes: true, events: true })
  const [xRange, setXRange] = useState<[number, number] | null>(null)
  const [modal, setModal] = useState<{ kind: 'mode' | 'event'; entry: ModeInterval | EventPoint } | null>(null)

  const { data, layout } = useMemo(() => {
    const fig = buildFigure(payload, selectedVars, laneVisible)
    fig.layout.xaxis.range = xRange || [payload.tMin, payload.tMax]
    fig.layout.xaxis.autorange = false
    return fig
  }, [payload, selectedVars, laneVisible, xRange])

  const handleRelayout = (ev: any) => {
    const lo = ev['xaxis.range[0]']
    const hi = ev['xaxis.range[1]']
    if (lo != null && hi != null) {
      setXRange([new Date(lo).getTime(), new Date(hi).getTime()])
    } else if (ev['xaxis.autorange']) {
      setXRange(null)
    }
  }

  return (
    <div className="report-view">
      <header className="report-header">
        <h1>Cyclic Ventilator Report</h1>
        <button type="button" className="ghost" onClick={onReset}>⬆ Upload different files</button>
      </header>

      <StatBar meta={meta} />
      <PatientBanner patient={meta.patient} />

      <VariablePicker
        payload={payload}
        selected={selectedVars}
        onChange={setSelectedVars}
        laneVisible={laneVisible}
        onLaneChange={setLaneVisible}
      />

      <div className="chart-toolbar">
        <button type="button" className="ghost" onClick={() => setXRange(null)}>Reset zoom</button>
        <span className="hint">Drag on the chart (or the bar underneath it) to zoom · double-click to reset</span>
      </div>

      <div className="plot-host">
        <Plot
          data={data}
          layout={layout}
          config={{ displaylogo: false, responsive: true }}
          style={{ width: '100%', height: `${Math.max(420, 90 + selectedVars.length * 130)}px` }}
          onRelayout={handleRelayout}
          onClick={(ev: any) => {
            const pt = ev?.points?.[0]
            if (!pt) return
            const traceName = pt.data?.name
            if (traceName === 'Events') {
              const e = payload.events.find((ev2) => ev2[0] === pt.x || new Date(ev2[0]).getTime() === new Date(pt.x).getTime())
              if (e) setModal({ kind: 'event', entry: e })
            } else if (traceName === 'Mode') {
              const idx = pt.pointIndex
              const m = payload.modes[idx]
              if (m) setModal({ kind: 'mode', entry: m })
            }
          }}
        />
      </div>

      <Ledger
        payload={payload}
        onZoom={(t0, t1) => setXRange([t0, t1])}
        onOpenDetail={(kind, entry) => setModal({ kind, entry })}
      />

      {modal && (
        <DetailModal payload={payload} kind={modal.kind} entry={modal.entry} onClose={() => setModal(null)} />
      )}
    </div>
  )
}
