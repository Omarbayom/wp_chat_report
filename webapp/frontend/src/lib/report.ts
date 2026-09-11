import type { Payload, Settings } from '../types'

// ---------------------------------------------------------------------
// Nearest-sample lookup, ported from render_pages.py (SAMPLE_GAP / COVER_TOL
// / nearest()) — used both for "is there cyclic coverage near time t" and
// for the detail modal's trend-sample fallback (see splitSettings below).
// ---------------------------------------------------------------------

/** Binary search: index of the sample in `samples` nearest to `t`. */
function nearestIndex(samples: Payload['samples'], t: number): number {
  let lo = 0
  let hi = samples.length - 1
  if (hi < 0) return -1
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (samples[mid][0] < t) lo = mid + 1
    else hi = mid
  }
  if (lo > 0 && t - samples[lo - 1][0] < samples[lo][0] - t) return lo - 1
  return lo
}

/** Median-gap-based coverage tolerance, same rule the original hover
 * readout uses to decide "is there really cyclic data at this moment" vs.
 * snapping onto a sample that's actually far away in a data gap. */
export function coverTolerance(payload: Payload): number {
  const s = payload.samples
  if (!s || s.length < 3) return 60_000
  const gaps: number[] = []
  const step = Math.max(1, Math.floor(s.length / 500)) // sample the gaps, full scan isn't needed
  for (let i = step; i < s.length; i += step) gaps.push(s[i][0] - s[i - step][0])
  gaps.sort((a, b) => a - b)
  const medianGap = (gaps[Math.floor(gaps.length / 2)] || 60_000) / step
  return Math.max(medianGap * 4, 15_000)
}

/** The cyclic trend sample nearest time `t`, or null if the nearest one is
 * farther away than normal coverage (a real gap, not "no data at all"). */
export function nearestTrendSample(
  payload: Payload,
  t: number,
  tol: number,
): Payload['samples'][number] | null {
  const idx = nearestIndex(payload.samples, t)
  if (idx < 0) return null
  const s = payload.samples[idx]
  return Math.abs(s[0] - t) <= tol ? s : null
}

// ---------------------------------------------------------------------
// Detail-modal helpers, ported from render_pages.py's splitSettings /
// fmtSettingsRows logic (by column name, not a hardcoded list, so it keeps
// working on an export with a different Cyc.*/set-value column set).
// ---------------------------------------------------------------------

export function splitSettings(settings: Settings | null | undefined): {
  setVals: Settings
  cycVals: Settings
} {
  const setVals: Settings = {}
  const cycVals: Settings = {}
  for (const k in settings || {}) {
    if (k.startsWith('Cyc.')) cycVals[k] = settings![k]
    else setVals[k] = settings![k]
  }
  return { setVals, cycVals }
}

// ---------------------------------------------------------------------
// Plotly figure: one shared time x-axis, thin Alarms/Modes/Events lanes on
// top, one stacked row per selected Y-axis variable underneath. A
// rangeslider on the shared x-axis replaces the old hand-rolled
// overview/brush entirely — native zoom/pan/reset, no more "window not
// moving" class of bugs to maintain.
// ---------------------------------------------------------------------

const LANE_KEYS = ['alarms', 'modes', 'events'] as const
type LaneKey = (typeof LANE_KEYS)[number]

export interface FigureResult {
  data: any[]
  layout: any
}

export function buildFigure(
  payload: Payload,
  selectedVars: string[],
  laneVisible: Record<LaneKey, boolean>,
): FigureResult {
  const activeLanes = LANE_KEYS.filter((k) => laneVisible[k])
  const rowKeys: (LaneKey | string)[] = [...activeLanes, ...selectedVars]
  const nRows = rowKeys.length || 1

  // Lanes are short and fixed-height; variable rows share what's left.
  const laneFrac = 0.05
  const gap = 0.018
  const laneTotal = activeLanes.length * laneFrac
  const varRows = Math.max(1, selectedVars.length)
  const varFrac = selectedVars.length
    ? (1 - laneTotal - gap * (nRows - 1)) / varRows
    : 0

  const domains: [number, number][] = []
  let top = 1
  for (const key of rowKeys) {
    const h = activeLanes.includes(key as LaneKey) ? laneFrac : varFrac
    const bottom = top - h
    domains.push([Math.max(0, bottom), top])
    top = bottom - gap
  }

  const data: any[] = []
  const layout: any = {
    margin: { l: 70, r: 20, t: 10, b: 40 },
    showlegend: false,
    hovermode: 'closest',
    xaxis: {
      type: 'date',
      rangeslider: { visible: true, thickness: 0.06 },
      showgrid: false,
    },
    grid: undefined,
  }

  rowKeys.forEach((key, i) => {
    const axisNum = i + 1
    const yKey = axisNum === 1 ? 'yaxis' : `yaxis${axisNum}`
    const yRef = axisNum === 1 ? 'y' : `y${axisNum}`
    const [d0, d1] = domains[i]

    if (key === 'alarms' || key === 'events') {
      const isAlarms = key === 'alarms'
      const items: [number, string][] = isAlarms
        ? payload.alarms.map((a) => [a[0], a[2]] as [number, string])
        : payload.events.map((e) => [e[0], e[1]] as [number, string])
      const colorOf = (label: string) =>
        isAlarms ? payload.alarmColors[label] || '#888' : '#0a8f6e'
      layout[yKey] = {
        domain: [d0, d1], range: [0, 1], fixedrange: true,
        showticklabels: false, showgrid: false, zeroline: false,
        title: { text: isAlarms ? 'Alarms' : 'Events', font: { size: 10 } },
      }
      data.push({
        type: 'scattergl', mode: 'markers', xaxis: 'x', yaxis: yRef,
        x: items.map((it) => it[0]), y: items.map(() => 0.5),
        text: items.map((it) => it[1]),
        hovertemplate: '%{text}<br>%{x}<extra></extra>',
        marker: { symbol: 'line-ns', size: 14, line: { width: 2, color: items.map((it) => colorOf(it[1])) } },
        name: isAlarms ? 'Alarms' : 'Events',
      })
    } else if (key === 'modes') {
      layout[yKey] = {
        domain: [d0, d1], range: [0, 1], fixedrange: true,
        showticklabels: false, showgrid: false, zeroline: false,
        title: { text: 'Mode', font: { size: 10 } },
      }
      const shapes = (layout.shapes ||= [])
      for (const m of payload.modes) {
        shapes.push({
          type: 'rect', xref: 'x', yref: yRef,
          x0: m[0], x1: m[1], y0: 0.1, y1: 0.9,
          fillcolor: payload.modeColors[m[2]] || '#6f42c1',
          opacity: 0.85, line: { width: 0 },
        })
      }
      // invisible trace just so hover/legend has something to bind mode names to
      data.push({
        type: 'scattergl', mode: 'markers', xaxis: 'x', yaxis: yRef,
        x: payload.modes.map((m) => (m[0] + m[1]) / 2), y: payload.modes.map(() => 0.5),
        text: payload.modes.map((m) => m[2]), opacity: 0,
        hovertemplate: '%{text}<extra></extra>', name: 'Mode',
      })
    } else {
      const varName = key
      const colIdx = payload.vars.indexOf(varName) + 1
      layout[yKey] = {
        domain: [d0, d1], title: { text: `${varName} ${payload.units[varName] ? `(${payload.units[varName]})` : ''}`, font: { size: 11 } },
        automargin: true,
      }
      data.push({
        type: 'scattergl', mode: 'lines', xaxis: 'x', yaxis: yRef,
        x: payload.samples.map((s) => s[0]),
        y: payload.samples.map((s) => s[colIdx] as number | null),
        line: { width: 1, color: '#0a6ebd' },
        name: varName,
        connectgaps: false,
      })
    }
  })

  return { data, layout }
}
