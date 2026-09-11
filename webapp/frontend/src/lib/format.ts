// Ported 1:1 from wa_report/cyclic_report/render_pages.py's fmt* helpers.
// Payload timestamps are epoch-ms produced by render_combined.py's `_ms()`,
// which treats the (naive, no-timezone) device timestamp as if it were a
// UTC wall-clock reading — so formatting must read back with the UTC
// getters, never the viewer's local timezone, or the clock would drift by
// whatever offset the browser happens to be in.
const pad = (n: number) => String(n).padStart(2, '0')

export function fmtTime(ms: number): string {
  const d = new Date(ms)
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`
}

export function fmtDate(ms: number): string {
  const d = new Date(ms)
  return `${pad(d.getUTCDate())}/${pad(d.getUTCMonth() + 1)}/${d.getUTCFullYear()}`
}

export function fmtDateTime(ms: number): string {
  return `${fmtDate(ms)} ${fmtTime(ms)}`
}

export function fmtDur(ms: number): string {
  const s = Math.round(ms / 1000)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = s % 60
  return (h ? `${h}h ` : '') + (m ? `${m}m ` : '') + (h ? '' : `${ss}s`)
}
