import type { AlarmInterval, EventPoint, ModeInterval, Payload } from '../types'
import { fmtDateTime, fmtDur, fmtTime } from '../lib/format'

interface Props {
  payload: Payload
  onZoom: (t0: number, t1: number) => void
  onOpenDetail: (kind: 'mode' | 'event', entry: ModeInterval | EventPoint) => void
}

const PAD_FRAC = 0.15 // extra room on each side of the zoomed-to span, like the old app's chip-click zoom

function zoomSpanFor(t0: number, t1: number): [number, number] {
  const span = Math.max(t1 - t0, 60_000)
  const pad = span * PAD_FRAC
  return [t0 - pad, t1 + pad]
}

export default function Ledger({ payload, onZoom, onOpenDetail }: Props) {
  return (
    <div className="ledger">
      <details className="ledger-sec" open>
        <summary className="ledger-h">Alarms — <b>{payload.alarms.length}</b> <span>· click one to jump to it</span></summary>
        <div className="chips">
          {payload.alarms.length === 0 && <span className="muted">no alarms</span>}
          {payload.alarms.map((a: AlarmInterval, i) => (
            <span
              key={i} className="chip" style={{ borderColor: payload.alarmColors[a[2]] || '#888', color: payload.alarmColors[a[2]] || '#888' }}
              onClick={() => onZoom(...zoomSpanFor(a[0], a[1]))}
              title={`${a[2]} · ${fmtDateTime(a[0])} → ${fmtDateTime(a[1])} (${fmtDur(a[1] - a[0])}) — click to jump`}
            >
              <b>{fmtTime(a[0])}</b> {fmtDur(a[1] - a[0])} {a[2]}
            </span>
          ))}
        </div>
      </details>

      <details className="ledger-sec" open>
        <summary className="ledger-h">Events — <b>{payload.events.length}</b> <span>· click a title to jump · ⓘ for full settings</span></summary>
        <div className="chips">
          {payload.events.length === 0 && <span className="muted">no logged events</span>}
          {payload.events.map((e: EventPoint, i) => (
            <span key={i} className="chip" onClick={() => onZoom(...zoomSpanFor(e[0], e[0]))}>
              <b>{fmtTime(e[0])}</b> {e[1]}
              <button type="button" className="chip-info" onClick={(ev) => { ev.stopPropagation(); onOpenDetail('event', e) }}>ⓘ</button>
            </span>
          ))}
        </div>
      </details>

      {payload.modes.length > 0 && (
        <details className="ledger-sec" open>
          <summary className="ledger-h">Mode changes — <b>{payload.modes.length}</b> <span>· ⓘ for full settings</span></summary>
          <div className="chips">
            {payload.modes.map((m: ModeInterval, i) => (
              <span
                key={i} className="chip mode"
                style={{ borderColor: payload.modeColors[m[2]] || '#6f42c1', color: payload.modeColors[m[2]] || '#6f42c1' }}
                onClick={() => onZoom(...zoomSpanFor(m[0], m[1]))}
                title={`${m[2]} · ${fmtDateTime(m[0])} → ${fmtDateTime(m[1])} (${fmtDur(m[1] - m[0])})`}
              >
                <b>{fmtTime(m[0])}</b> {fmtDur(m[1] - m[0])} {m[2]}
                <button type="button" className="chip-info" onClick={(ev) => { ev.stopPropagation(); onOpenDetail('mode', m) }}>ⓘ</button>
              </span>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}
