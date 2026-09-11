// Mirrors the JSON shapes the FastAPI backend returns (webapp/backend/app/main.py),
// which in turn mirror the payload the existing static charts.html embeds
// (wa_report/cyclic_report/render_combined.py's build_payload) — see that
// module's docstring for the authoritative field-by-field description.

/** One cyclic sample row: [epochMs, ...values in `vars` order]. A value is
 * `null` where that variable's reading is missing for this row. */
export type SampleRow = [number, ...(number | null)[]]

/** [startMs, endMs, alarmType] */
export type AlarmInterval = [number, number, string]

/** [startMs, endMs, modeLabel, settings | null] */
export type ModeInterval = [number, number, string, Settings | null]

/** [ms, text, settings] */
export type EventPoint = [number, string, Settings]

/** [ms, count, burstId] */
export type BurstPoint = [number, number, string]

/** [ms, {var: [min, max]}] */
export type LimitPoint = [number, Record<string, [number, number]>]

export type Settings = Record<string, string | number>

export interface PatientSegment {
  id: string
  label: string
  color: string
  t0: number
  t1: number
  nSamples: number
  nAlarms: number
  info: [string, string][]
}

export interface Payload {
  vars: string[]
  defaultVars: string[]
  units: Record<string, string>
  alarmColors: Record<string, string>
  modeColors: Record<string, string>
  samples: SampleRow[]
  alarms: AlarmInterval[]
  bursts: BurstPoint[]
  modes: ModeInterval[]
  events: EventPoint[]
  limits: LimitPoint[]
  limitVars: string[]
  tMin: number
  tMax: number
  sampleMin: number
  sampleMax: number
  patients: PatientSegment[]
}

export interface Meta {
  missing: string[]
  present: string[]
  defaultSel: string[]
  nSamples: number
  nAlarms: number
  nBursts: number
  nBurstsDropped: number
  nModes: number
  nEvents: number
  nLimitChanges: number
  patient: [string, string][]
}

export interface ReportResponse {
  payload: Payload
  meta: Meta
}

export interface ConfigResponse {
  allVariables: string[]
  units: Record<string, string>
  defaultVariables: string[]
  alarmColors: Record<string, string>
  modeColorPalette: string[]
}
