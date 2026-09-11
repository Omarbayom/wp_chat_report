import type { EventPoint, ModeInterval, Payload, Settings } from '../types'
import { coverTolerance, nearestTrendSample, splitSettings } from '../lib/report'
import { fmtDateTime, fmtDur, fmtTime } from '../lib/format'

interface Props {
  payload: Payload
  kind: 'mode' | 'event'
  entry: ModeInterval | EventPoint
  onClose: () => void
}

function SettingsTable({ vals, emptyMsg }: { vals: Settings; emptyMsg: string }) {
  const keys = Object.keys(vals)
  if (!keys.length) return <p className="muted small">{emptyMsg}</p>
  return (
    <table className="dm-t">
      <tbody>
        {keys.map((k) => <tr key={k}><td className="k">{k}</td><td className="v">{String(vals[k])}</td></tr>)}
      </tbody>
    </table>
  )
}

export default function DetailModal({ payload, kind, entry, onClose }: Props) {
  const isMode = kind === 'mode'
  const t0 = entry[0]
  const t1 = isMode ? (entry as ModeInterval)[1] : null
  const label = isMode ? (entry as ModeInterval)[2] : (entry as EventPoint)[1]
  const settings = isMode ? (entry as ModeInterval)[3] : (entry as EventPoint)[2]
  const { setVals, cycVals } = splitSettings(settings)
  const hasCyc = Object.keys(cycVals).length > 0

  let trendRows: [string, number][] = []
  let trendTime: number | null = null
  if (!hasCyc) {
    const trend = nearestTrendSample(payload, t0, coverTolerance(payload))
    if (trend) {
      trendTime = trend[0]
      trendRows = payload.vars
        .map((v, i): [string, number | null] => [v, trend[i + 1] as number | null])
        .filter((r): r is [string, number] => r[1] != null)
    }
  }

  return (
    <div className="dm-overlay" onClick={onClose}>
      <div className="dm-box" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="dm-close" onClick={onClose}>✕</button>
        <div className="dm-h">
          <b>{label}</b><br />
          {isMode ? <>{fmtDateTime(t0)} → {fmtDateTime(t1!)} <span className="muted">({fmtDur(t1! - t0)})</span></> : fmtDateTime(t0)}
        </div>

        <div className="dm-sec">Set values <span className="muted">— device settings, from the log file</span></div>
        <SettingsTable vals={setVals} emptyMsg="no set values recorded for this entry" />

        <div className="dm-sec">Cyclic readings <span className="muted">— the "Cyc." snapshot logged with this entry</span></div>
        <SettingsTable
          vals={cycVals}
          emptyMsg={'the device didn\'t echo a cyclic snapshot on this particular log entry — normal for most entry types; it mainly appears on "Standby Mode Activated" (the moment active ventilation stops)'}
        />

        {!hasCyc && trendRows.length > 0 && (
          <>
            <div className="dm-sec">
              Nearest cyclic trend sample{' '}
              <span className="muted">
                — from the cyclic data file (not this log row's own echo), at {fmtTime(trendTime!)}
                {Math.abs(trendTime! - t0) > 1000 ? ` (${fmtDur(Math.abs(trendTime! - t0))} away)` : ''}
              </span>
            </div>
            <table className="dm-t">
              <tbody>
                {trendRows.map(([v, val]) => (
                  <tr key={v}>
                    <td className="k">{v}</td>
                    <td className="v">{val} <span className="muted">{payload.units[v] || ''}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  )
}
