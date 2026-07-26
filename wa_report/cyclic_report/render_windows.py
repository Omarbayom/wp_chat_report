"""The windowed cyclic view — ``windows.html``.

One graph per fixed clock-aligned window (default 1 hour, or whatever the user
picks with the in-page **window-size selector**: 1/2/3/6/12/24h). Each window is
a card with stacked variable panels, an alarm swim-lane, photo-burst markers,
and a hover/lock value readout. A **variable picker** chooses which signals
(VTi/VTe/PIP/PEEP/RR/FIO2…) appear on the Y axis, live. Windows that contain
only alarms (recorded with no cyclic data) are shown too, so nothing is missed.

This is the "old windows" view; it sits beside the chat (``report.html``) and the
stock overview (``charts.html``) and links to both in named browser tabs
(``wa_report`` / ``wa_charts``). ``build_windows_html`` returns the HTML string.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Sequence

from .config import DEFAULT_VARIABLES
from .render_combined import _esc, build_payload

_WINDOW_CHOICES = [1, 2, 3, 6, 12, 24]


def _span(a, b) -> str:
    return f"{a:%d/%m/%Y %H:%M:%S} → {b:%d/%m/%Y %H:%M:%S}"


def _var_options(present, selected) -> str:
    return "".join(
        f"<label><input type='checkbox' value='{_esc(v)}'"
        f"{' checked' if v in selected else ''} onchange='onVarToggle()'> {_esc(v)}</label>"
        for v in present
    )


def build_windows_html(folders, cyclic_source, variables: Sequence[str],
                       device_label: str = "", alarms_source=None,
                       chat_href: str = "report.html",
                       stock_href: str = "charts.html", min_photos: int = 3,
                       window_minutes: int = 10, window_hours: int = 1,
                       out_path: Optional[Path] = None) -> str:
    """One graph per clock-aligned window. The window size and the plotted
    variables are chosen live in the browser; burst markers open *chat_href* at
    the matching image; a ``?t=<ms>`` query on load scrolls to and locks that
    moment. Alarm-only windows (no cyclic data) are included."""
    variables = list(variables) or list(DEFAULT_VARIABLES)
    payload, meta = build_payload(folders, cyclic_source, variables,
                                  alarms_source=alarms_source,
                                  min_photos=min_photos,
                                  window_minutes=window_minutes)
    initial = window_hours if window_hours in _WINDOW_CHOICES else 1
    payload["windowHours"] = initial
    choices = sorted(set(_WINDOW_CHOICES + [window_hours]))
    win_options = "".join(
        f"<option value='{h}'{' selected' if h == initial else ''}>{h} hour{'s' if h > 1 else ''}</option>"
        for h in choices
    )

    notes = ""
    if meta["n_bursts_dropped"]:
        notes += (
            f"<div class='warn'>{meta['n_bursts_dropped']} photo burst(s) fell "
            "outside the cyclic log and are hidden (no cyclic data behind "
            "them).</div>"
        )
    if meta["img_times"] and meta["n_bursts"] == 0:
        df = meta["df"]
        log_span = _span(df["DateTime"].min(), df["DateTime"].max())
        img_span = _span(min(meta["img_times"]), max(meta["img_times"]))
        notes += (
            "<div class='warn'>Note: no photo bursts fall inside this log's time "
            "range — the chat and cyclic CSV don't overlap in time, so the cyclic "
            "log (and any alarms) are shown on their own, without photo markers.<br>"
            f"&nbsp;• Chat images: <b>{_esc(img_span)}</b><br>"
            f"&nbsp;• Cyclic log: <b>{_esc(log_span)}</b><br>"
            "To see photo markers, pair a chat with a CSV from the <b>same device "
            "and dates</b>.</div>"
        )

    chat_link = (f'<a class="other" href="{_esc(chat_href)}" target="wa_report">Open chat ↗</a>'
                 if chat_href else "")
    doc = (_WINDOWS_PAGE
           .replace("__TITLE__", _esc(device_label) or "Cyclic windows")
           .replace("__DEVICE__", _esc(device_label) or "Cyclic windows")
           .replace("__CHATLINK__", chat_link)
           .replace("__CHATHREF__", _esc(chat_href))
           .replace("__STOCKHREF__", _esc(stock_href))
           .replace("__WINOPTS__", win_options)
           .replace("__VAROPTS__", _var_options(meta["present"], meta["default_sel"]))
           .replace("__NBURST__", str(meta["n_bursts"]))
           .replace("__NALARM__", str(meta["n_alarms"]))
           .replace("__NOTES__", notes)
           .replace("/*__DATA__*/", json.dumps(payload)))
    if out_path is not None:
        Path(out_path).write_text(doc, encoding="utf-8")
    return doc


_WINDOWS_PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — Cyclic windows</title>
<style>
  * { box-sizing:border-box; }
  body { margin:0; font-family:"Segoe UI",system-ui,Arial,sans-serif; color:#1d2733;
    background:#f4f6f9; font-size:14px; }
  header { background:#0a6ebd; color:#fff; padding:12px 20px; display:flex; align-items:center; gap:14px; flex-wrap:wrap; }
  header h1 { margin:0; font-size:18px; }
  header .sub { opacity:.9; font-size:12.5px; }
  header .ctl { margin-left:auto; display:flex; align-items:center; gap:10px; }
  header select { font:inherit; padding:4px 8px; border-radius:6px; border:0; }
  header a.other { color:#fff; background:rgba(255,255,255,.18); padding:6px 12px;
    border-radius:8px; text-decoration:none; font-size:13px; }
  header a.other:hover { background:rgba(255,255,255,.32); }
  .stats { display:flex; gap:8px; flex-wrap:wrap; padding:10px 20px 0; }
  .stat { background:#fff; border:1px solid #e3e8ee; border-radius:9px; padding:6px 12px; }
  .stat b { color:#0a6ebd; font-size:16px; } .stat span { color:#5b6b7b; font-size:11px; }
  .warn { margin:8px 20px 0; color:#8a5b00; background:#fff6e5; border:1px solid #ffe2a8;
    border-radius:8px; padding:6px 12px; font-size:13px; line-height:1.5; }
  .muted { color:#5b6b7b; font-style:italic; }
  .varbar { display:flex; gap:6px; align-items:center; flex-wrap:wrap;
    background:#fff; border:1px solid #e3e8ee; border-radius:10px; padding:8px 14px; margin:12px 20px 0; }
  .varbar .lbl { font-size:12px; color:#5b6b7b; font-weight:600; margin-right:4px; }
  .varbar label { font-size:13px; display:inline-flex; align-items:center; gap:4px;
    background:#f4f6f9; border:1px solid #e3e8ee; border-radius:20px; padding:3px 10px; cursor:pointer; }
  .varbar label:hover { border-color:#0a6ebd; }
  .controls { display:flex; gap:10px; align-items:flex-end; flex-wrap:wrap;
    background:#fff; border:1px solid #e3e8ee; border-radius:10px; padding:10px 14px; margin:12px 20px 0; }
  .controls label.q { display:flex; flex-direction:column; gap:3px; font-size:11px; color:#5b6b7b; }
  .controls input[type="datetime-local"] { font:inherit; font-size:13px; padding:5px 8px; border:1px solid #cfd8e3; border-radius:6px; color:#1d2733; }
  .controls button { font:inherit; font-size:13px; padding:6px 10px; border-radius:6px; border:1px solid #cfd8e3; background:#fff; cursor:pointer; }
  .controls button.primary { background:#0a6ebd; color:#fff; border-color:#0a6ebd; }
  .controls button:hover { border-color:#0a6ebd; }
  .controls .span { font-size:12px; color:#1d2733; margin-left:auto; text-align:right; line-height:1.4; }
  .controls .span b { color:#0a6ebd; }
  .charts { padding:12px 20px 24px; }
  .card { background:#fff; border:1px solid #e3e8ee; border-radius:10px; padding:8px 12px 12px; margin-bottom:14px; }
  .card-h { font-size:14px; font-weight:600; color:#0a6ebd; margin:2px 0 6px; }
  .lock-badge { font-size:11px; color:#c0392b; margin-left:8px; font-weight:600; }
  .alarm-only { font-size:11px; color:#8a5b00; margin-left:8px; font-weight:600; }
  .chart-row { display:flex; gap:10px; align-items:flex-start; }
  svg.chart { flex:1 1 auto; width:100%; height:auto; cursor:crosshair; }
  .readout { flex:0 0 160px; font-size:12px; }
  .readout table { border-collapse:collapse; width:100%; }
  .readout td { border-bottom:1px solid #eef2f6; padding:2px 4px; }
  .readout td.k { color:#5b6b7b; } .readout td.v { text-align:right; font-weight:600; }
  .readout td.al { text-align:left; font-weight:600; font-size:11px; line-height:1.35; }
  .readout .hint { color:#5b6b7b; font-style:italic; margin-top:6px; font-size:11px; }
  @media (max-width:720px){ .chart-row{ flex-direction:column; } .readout{ flex-basis:auto; width:100%; } }
</style></head><body>
<header><h1>__DEVICE__</h1><div class="sub">one graph per window · hover for values · click to lock</div>
  <div class="ctl">
    <label style="font-size:13px">Window
      <select id="winsize" onchange="render(+this.value)">__WINOPTS__</select>
    </label>
    <a class="other" href="__STOCKHREF__" target="wa_charts">Stock view ↗</a>
    __CHATLINK__
  </div></header>
<div class="stats">
  <div class="stat"><b id="stat-windows">–</b> <span>windows</span></div>
  <div class="stat"><b>__NBURST__</b> <span>photo bursts</span></div>
  <div class="stat"><b>__NALARM__</b> <span>alarms</span></div>
</div>
__NOTES__
<div class="varbar"><span class="lbl">Y axis:</span>__VAROPTS__</div>
<div class="controls">
  <label class="q">Range start (date & time)
    <input type="datetime-local" id="q-start" step="1">
  </label>
  <label class="q">Range end (date & time)
    <input type="datetime-local" id="q-end" step="1">
  </label>
  <button class="primary" id="q-apply">Show range</button>
  <button id="q-reset">Full range</button>
  <div class="span" id="span-lbl">—</div>
</div>
<div class="charts" id="charts"></div>
<script id="data" type="application/json">/*__DATA__*/</script>
<script>
const CHAT_HREF = "__CHATHREF__";
function jumpToChat(cid){ if(!cid || !CHAT_HREF) return; window.open(CHAT_HREF + '#' + cid, 'wa_report'); }
</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const VB_W = 1000, ML = 70, MR = 16, TOP = 8, PANEL_H = 78, PANEL_GAP = 6, XAXIS_H = 26, LANE_ROW = 14;
const ALLVARS = DATA.vars, UNITS = DATA.units;
const COL = {}; ALLVARS.forEach((v,i)=>{ COL[v]=i+1; });
let VARS = (DATA.defaultVars && DATA.defaultVars.length ? DATA.defaultVars : ALLVARS).slice();
const MODE_COLOR = '#6f42c1', EVENT_COLOR = '#0aa3a3';
function modeAt(t){ let m=null; for(const md of DATA.modes){ if(md[0]<=t) m=md[1]; else break; } return m; }
const DAY = 86400000;
let WINDOWS = [];
const CTRL = {};
// REGION = the searched extent; only windows overlapping it are listed. The
// window *size* stays a manual choice (the selector). Search sets REGION only.
let REGION = { r0: DATA.tMin, r1: DATA.tMax };
function pad(n){ return String(n).padStart(2,'0'); }
function fmtTime(ms){ const d=new Date(ms); return pad(d.getUTCHours())+':'+pad(d.getUTCMinutes()); }
function fmtDateTime(ms){ const d=new Date(ms);
  return pad(d.getUTCDate())+'/'+pad(d.getUTCMonth()+1)+'/'+d.getUTCFullYear()+' '
    +pad(d.getUTCHours())+':'+pad(d.getUTCMinutes())+':'+pad(d.getUTCSeconds()); }
function msToInput(ms){ const d=new Date(ms);
  return d.getUTCFullYear()+'-'+pad(d.getUTCMonth()+1)+'-'+pad(d.getUTCDate())+'T'+pad(d.getUTCHours())+':'+pad(d.getUTCMinutes())+':'+pad(d.getUTCSeconds()); }
function inputToMs(v){ if(!v) return null; const m=v.match(/(\d+)-(\d+)-(\d+)T(\d+):(\d+)(?::(\d+))?/);
  if(!m) return null; return Date.UTC(+m[1],+m[2]-1,+m[3],+m[4],+m[5],+(m[6]||0)); }
function fmtTimeS(ms){ const d=new Date(ms); return pad(d.getUTCHours())+':'+pad(d.getUTCMinutes())+':'+pad(d.getUTCSeconds()); }
function fmtDate(ms){ const d=new Date(ms); return pad(d.getUTCDate())+'/'+pad(d.getUTCMonth()+1)+'/'+d.getUTCFullYear(); }
function titleFor(t0,t1,hours){ if(hours>=24) return fmtDate(t0);
  const d0=fmtDate(t0), d1=fmtDate(t1-1);
  if(d0===d1) return d0+'  '+fmtTime(t0)+'–'+fmtTime(t1);
  return fmtDate(t0)+' '+fmtTime(t0)+' – '+fmtDate(t1)+' '+fmtTime(t1); }
function nearest(samples, t){ let lo=0, hi=samples.length-1; if(hi<0) return -1;
  while(lo<hi){ const m=(lo+hi)>>1; if(samples[m][0]<t) lo=m+1; else hi=m; }
  if(lo>0 && (t-samples[lo-1][0])<(samples[lo][0]-t)) return lo-1; return lo; }
function onVarToggle(){
  const boxes=[...document.querySelectorAll('.varbar input[type=checkbox]')];
  const sel=boxes.filter(b=>b.checked).map(b=>b.value);
  if(!sel.length) return;
  VARS = ALLVARS.filter(v=>sel.includes(v));
  render(+document.getElementById('winsize').value);
}
function makeWindows(hours){
  const step=hours*3600000;
  const align = Math.floor(DATA.tMin/DAY)*DAY + Math.floor((DATA.tMin - Math.floor(DATA.tMin/DAY)*DAY)/step)*step;
  const slot = t => Math.floor((t-align)/step);
  const map = new Map();
  const W = k => { if(!map.has(k)){ const t0=align+k*step; map.set(k,{k,t0,t1:t0+step,samples:[],alarms:[],bursts:[],modes:[],events:[]}); } return map.get(k); };
  for(const s of DATA.samples){ if(s[0]<REGION.r0||s[0]>REGION.r1) continue; W(slot(s[0])).samples.push(s); }
  for(const a of DATA.alarms){ if(a[0]<REGION.r0||a[0]>REGION.r1) continue; W(slot(a[0])).alarms.push(a); }
  for(const m of DATA.modes){ if(m[0]<REGION.r0||m[0]>REGION.r1) continue; W(slot(m[0])).modes.push(m); }
  for(const e of DATA.events){ if(e[0]<REGION.r0||e[0]>REGION.r1) continue; W(slot(e[0])).events.push(e); }
  for(const b of DATA.bursts){ if(b[0]<REGION.r0||b[0]>REGION.r1) continue; const w=map.get(slot(b[0])); if(w) w.bursts.push(b); }
  const wins=[...map.values()].filter(w=>w.samples.length || w.alarms.length || w.modes.length || w.events.length).sort((a,b)=>a.t0-b.t0);
  wins.forEach((w,i)=>{ w.i=i; w.title=titleFor(w.t0,w.t1,hours); w.alarmOnly=!w.samples.length; });
  return wins;
}
function cardHTML(w){ const badge = w.alarmOnly
    ? `<span class="alarm-only">alarms only — no cyclic data</span>`
    : `<span class="lock-badge" id="lock-${w.i}" hidden>🔒 locked</span>`;
  return `<div class="card" id="card-${w.i}"><div class="card-h">${w.title}${badge}</div>`
  + `<div class="chart-row"><svg class="chart" id="chart-${w.i}"></svg>`
  + `<div class="readout" id="readout-${w.i}"></div></div></div>`; }
function render(hours){
  WINDOWS = makeWindows(hours);
  const host = document.getElementById('charts');
  host.innerHTML = WINDOWS.length ? WINDOWS.map(cardHTML).join('')
    : '<p class="muted">No cyclic data or alarms in this region.</p>';
  for(const k in CTRL) delete CTRL[k];
  WINDOWS.forEach(buildChart);
  const sw=document.getElementById('stat-windows'); if(sw) sw.textContent=WINDOWS.length;
}
function curHours(){ return +document.getElementById('winsize').value; }
function updateRegionLbl(){
  const lbl=document.getElementById('span-lbl'); if(!lbl) return;
  const full = REGION.r0<=DATA.tMin && REGION.r1>=DATA.tMax;
  lbl.innerHTML = full ? 'Range: <b>full log</b>'
    : `Range: <b>${fmtDateTime(REGION.r0)}</b> → <b>${fmtDateTime(REGION.r1)}</b>`;
}
function applyRegion(a, b){
  a=Math.max(DATA.tMin, Math.min(a, DATA.tMax)); b=Math.max(DATA.tMin, Math.min(b, DATA.tMax));
  if(b<a){ const t=a; a=b; b=t; }
  REGION.r0=a; REGION.r1=b;
  document.getElementById('q-start').value=msToInput(a);
  document.getElementById('q-end').value=msToInput(b);
  updateRegionLbl(); render(curHours());
}
function resetRegion(){
  REGION.r0=DATA.tMin; REGION.r1=DATA.tMax;
  document.getElementById('q-start').value=msToInput(DATA.tMin);
  document.getElementById('q-end').value=msToInput(DATA.tMax);
  updateRegionLbl(); render(curHours());
}
document.getElementById('q-apply').addEventListener('click', ()=>{
  const a=inputToMs(document.getElementById('q-start').value);
  const b=inputToMs(document.getElementById('q-end').value);
  if(a==null||b==null){ alert('Enter both a region start and end date/time.'); return; }
  applyRegion(a, b);
});
document.getElementById('q-reset').addEventListener('click', resetRegion);
function buildChart(win){
  const svg = document.getElementById('chart-'+win.i);
  const alarmTypes = [...new Set(win.alarms.map(a=>a[1]))]
        .sort((a,b)=>Object.keys(DATA.alarmColors).indexOf(a)-Object.keys(DATA.alarmColors).indexOf(b));
  const laneH = alarmTypes.length ? alarmTypes.length*LANE_ROW + 8 : 0;
  const nV = VARS.length;
  const H = TOP + laneH + nV*(PANEL_H+PANEL_GAP) + XAXIS_H;
  svg.setAttribute('viewBox', `0 0 ${VB_W} ${H}`);
  const plotL = ML, plotR = VB_W - MR;
  const xOf = t => plotL + (t-win.t0)/(win.t1-win.t0)*(plotR-plotL);
  const ranges = VARS.map(v=>{ const c=COL[v]; let mn=Infinity, mx=-Infinity;
    for(const s of win.samples){ const y=s[c]; if(y==null) continue; if(y<mn)mn=y; if(y>mx)mx=y; }
    if(mn===Infinity){ mn=0; mx=1; } if(mn===mx){ mn-=1; mx+=1; }
    const pad=(mx-mn)*0.08; return [mn-pad, mx+pad]; });
  const panelTop = k => TOP + laneH + k*(PANEL_H+PANEL_GAP);
  const yOf = (k,val) => { const [mn,mx]=ranges[k]; return panelTop(k) + (1-(val-mn)/(mx-mn))*PANEL_H; };
  const panelsBottom = panelTop(nV-1) + PANEL_H;
  let parts = [];
  if(alarmTypes.length){ alarmTypes.forEach((a,r)=>{ const y = TOP + r*LANE_ROW + LANE_ROW/2;
    const col = DATA.alarmColors[a] || '#888';
    parts.push(`<text x="${plotL-6}" y="${y+3}" text-anchor="end" font-size="8" fill="${col}">${a}</text>`);
    for(const ev of win.alarms){ if(ev[1]!==a) continue;
      parts.push(`<rect x="${xOf(ev[0])-1.5}" y="${y-3}" width="3" height="6" fill="${col}"/>`); } }); }
  VARS.forEach((v,k)=>{ const c=COL[v], top=panelTop(k), [mn,mx]=ranges[k];
    parts.push(`<rect x="${plotL}" y="${top}" width="${plotR-plotL}" height="${PANEL_H}" fill="none" stroke="#e3e8ee"/>`);
    [mn,(mn+mx)/2,mx].forEach(val=>{ const y=yOf(k,val);
      parts.push(`<line x1="${plotL}" y1="${y}" x2="${plotR}" y2="${y}" stroke="#eef2f6"/>`);
      parts.push(`<text x="${plotL-5}" y="${y+3}" text-anchor="end" font-size="8" fill="#5b6b7b">${val.toFixed(0)}</text>`); });
    parts.push(`<text x="${plotL+4}" y="${top+11}" font-size="10" font-weight="bold" fill="#1d2733">${v} (${UNITS[v]||''})</text>`);
    let d='', pen=false;
    for(const s of win.samples){ const val=s[c]; if(val==null){ pen=false; continue; }
      const x=xOf(s[0]), y=yOf(k,val); d += (pen?'L':'M')+x.toFixed(1)+' '+y.toFixed(1)+' '; pen=true; }
    parts.push(`<path d="${d}" fill="none" stroke="#0a6ebd" stroke-width="1.4"/>`);
    parts.push(`<line class="hg" id="hg-${win.i}-${k}" x1="${plotL}" x2="${plotR}" y1="0" y2="0" stroke="#c0392b" stroke-width="0.8" stroke-dasharray="4 3" visibility="hidden"/>`);
    parts.push(`<circle class="dot" id="dot-${win.i}-${k}" r="3" fill="#c0392b" visibility="hidden"/>`); });
  const nTicks=6;
  for(let i=0;i<=nTicks;i++){ const t=win.t0+(win.t1-win.t0)*i/nTicks; const x=xOf(t);
    parts.push(`<line x1="${x}" y1="${panelsBottom}" x2="${x}" y2="${panelsBottom+4}" stroke="#5b6b7b"/>`);
    parts.push(`<text x="${x}" y="${panelsBottom+15}" text-anchor="middle" font-size="8.5" fill="#5b6b7b">${fmtTimeS(t)}</text>`); }
  for(const b of win.bursts){ const x=xOf(b[0]);
    parts.push(`<line x1="${x}" y1="${TOP}" x2="${x}" y2="${panelsBottom}" stroke="#c0392b" stroke-width="1.2" stroke-dasharray="5 3"/>`);
    parts.push(`<text x="${x}" y="${TOP-1}" text-anchor="middle" font-size="8" font-weight="bold" fill="#c0392b">${fmtTime(b[0])}</text>`);
    parts.push(`<rect class="burst-hit" x="${x-5}" y="${TOP}" width="10" height="${panelsBottom-TOP}" fill="transparent" style="cursor:pointer" data-cid="${b[2]||''}"><title>${b[1]} photos at ${fmtTimeS(b[0])} — click to see in chat</title></rect>`); }
  let lastMX=-1e9;
  for(const m of win.modes){ const x=xOf(m[0]);
    parts.push(`<line x1="${x}" y1="${TOP}" x2="${x}" y2="${panelsBottom}" stroke="${MODE_COLOR}" stroke-width="1" stroke-dasharray="2 2"><title>${m[1]} at ${fmtTimeS(m[0])}</title></line>`);
    if(x-lastMX>46){ parts.push(`<text x="${x+2}" y="${panelsBottom-2}" font-size="8" fill="${MODE_COLOR}" font-weight="bold">${m[1]}</text>`); lastMX=x; } }
  for(const e of win.events){ const x=xOf(e[0]);
    parts.push(`<line x1="${x}" y1="${TOP}" x2="${x}" y2="${TOP+6}" stroke="${EVENT_COLOR}" stroke-width="1.2"><title>${e[1]} at ${fmtTimeS(e[0])}</title></line>`); }
  parts.push(`<line class="cx" id="cx-${win.i}" x1="0" x2="0" y1="${TOP}" y2="${panelsBottom}" stroke="#111" stroke-width="0.8" visibility="hidden"/>`);
  svg.innerHTML = parts.join('');
  const ro = document.getElementById('readout-'+win.i);
  let rows = `<table><tr><td class="k">Time</td><td class="v" id="ro-${win.i}-t">—</td></tr>`;
  VARS.forEach((v,k)=>{ rows += `<tr><td class="k">${v}</td><td class="v" id="ro-${win.i}-${k}">—</td></tr>`; });
  rows += `<tr><td class="k">Mode</td><td class="v" id="ro-${win.i}-mode">—</td></tr>`;
  rows += `<tr><td class="k">Alarms</td><td class="v al" id="ro-${win.i}-al">—</td></tr>`;
  rows += `<tr><td class="k">Events</td><td class="v al" id="ro-${win.i}-ev">—</td></tr>`;
  rows += `</table><div class="hint" id="hint-${win.i}">hover to read · click to lock</div>`;
  ro.innerHTML = rows;
  CTRL[win.i] = { win, svg, xOf, yOf, locked:false };
  svg.addEventListener('mousemove', e=>{ const c=CTRL[win.i]; if(c.locked) return; updateAt(win.i, xToTime(win.i, e)); });
  svg.addEventListener('mouseleave', ()=>{ const c=CTRL[win.i]; if(!c.locked) hideCursor(win.i); });
  svg.addEventListener('click', e=>{
    if(e.target.classList.contains('burst-hit')){ const cid=e.target.getAttribute('data-cid'); if(cid) jumpToChat(cid); return; }
    const c=CTRL[win.i]; c.locked=!c.locked;
    const lb=document.getElementById('lock-'+win.i); if(lb) lb.hidden = !c.locked;
    document.getElementById('hint-'+win.i).textContent = c.locked ? 'locked · click to unlock' : 'hover to read · click to lock';
    if(c.locked) updateAt(win.i, xToTime(win.i, e)); });
}
function xToTime(i, e){ const c=CTRL[i]; const r=c.svg.getBoundingClientRect();
  const vbX=(e.clientX-r.left)/r.width*VB_W; const frac=(vbX-ML)/((VB_W-MR)-ML);
  return c.win.t0 + Math.max(0,Math.min(1,frac))*(c.win.t1-c.win.t0); }
function updateAt(i, t){ const c=CTRL[i], win=c.win; const idx=nearest(win.samples, t); if(idx<0) return;
  const s=win.samples[idx]; const x=c.xOf(s[0]);
  const cx=document.getElementById('cx-'+i); cx.setAttribute('x1',x); cx.setAttribute('x2',x); cx.setAttribute('visibility','visible');
  document.getElementById('ro-'+i+'-t').textContent = fmtTimeS(s[0]);
  VARS.forEach((v,k)=>{ const val=s[COL[v]]; const hg=document.getElementById('hg-'+i+'-'+k);
    const dot=document.getElementById('dot-'+i+'-'+k); const cell=document.getElementById('ro-'+i+'-'+k);
    if(val==null){ hg.setAttribute('visibility','hidden'); dot.setAttribute('visibility','hidden'); cell.textContent='—'; return; }
    const y=c.yOf(k,val);
    hg.setAttribute('y1',y); hg.setAttribute('y2',y); hg.setAttribute('visibility','visible');
    dot.setAttribute('cx',x); dot.setAttribute('cy',y); dot.setAttribute('visibility','visible');
    cell.textContent = val + (UNITS[v]? ' '+UNITS[v] : ''); });
  const n=win.samples.length;
  const lo = idx>0 ? (win.samples[idx-1][0]+s[0])/2 : -Infinity;
  const hi = idx<n-1 ? (s[0]+win.samples[idx+1][0])/2 : Infinity;
  const alc=document.getElementById('ro-'+i+'-al');
  if(alc){ const seen={};
    for(const a of win.alarms){ if(a[0]>lo && a[0]<=hi) seen[a[1]]=(seen[a[1]]||0)+1; }
    const types=Object.keys(seen);
    alc.innerHTML = types.length
      ? types.map(t=>`<span style="color:${DATA.alarmColors[t]||'#555'}">${t}${seen[t]>1?' ×'+seen[t]:''}</span>`).join('<br>')
      : '—';
  }
  const mc=document.getElementById('ro-'+i+'-mode'); if(mc) mc.textContent = modeAt(s[0]) || '—';
  const evc=document.getElementById('ro-'+i+'-ev');
  if(evc){ const list=[]; for(const e of win.events){ if(e[0]>lo && e[0]<=hi) list.push(e[1]); }
    evc.innerHTML = list.length ? list.map(x=>`<span style="color:${EVENT_COLOR}">${x}</span>`).join('<br>') : '—'; } }
function hideCursor(i){ document.getElementById('cx-'+i).setAttribute('visibility','hidden');
  VARS.forEach((v,k)=>{ document.getElementById('hg-'+i+'-'+k).setAttribute('visibility','hidden');
    document.getElementById('dot-'+i+'-'+k).setAttribute('visibility','hidden');
    document.getElementById('ro-'+i+'-'+k).textContent='—'; });
  document.getElementById('ro-'+i+'-t').textContent='—';
  const alc=document.getElementById('ro-'+i+'-al'); if(alc) alc.textContent='—';
  const mc=document.getElementById('ro-'+i+'-mode'); if(mc) mc.textContent='—';
  const evc=document.getElementById('ro-'+i+'-ev'); if(evc) evc.textContent='—'; }
function lockAtTime(ts){ if(!WINDOWS.length) return;
  let w=WINDOWS.find(w=>ts>=w.t0 && ts<w.t1);
  if(!w) w=WINDOWS.reduce((best,x)=> Math.abs((x.t0+x.t1)/2-ts)<Math.abs((best.t0+best.t1)/2-ts)?x:best);
  const card=document.getElementById('card-'+w.i); if(card) card.scrollIntoView({behavior:'smooth', block:'center'});
  const c=CTRL[w.i]; if(!c) return; c.locked=true;
  const lb=document.getElementById('lock-'+w.i); if(lb) lb.hidden=false;
  const hint=document.getElementById('hint-'+w.i); if(hint) hint.textContent='locked · click to unlock';
  updateAt(w.i, Math.max(w.t0, Math.min(ts, w.t1-1))); }
document.getElementById('q-start').value = msToInput(DATA.tMin);
document.getElementById('q-end').value = msToInput(DATA.tMax);
updateRegionLbl();
render(DATA.windowHours);
(function(){ const p=new URLSearchParams(location.search); const t=p.get('t');
  if(t) setTimeout(()=>lockAtTime(+t), 100); })();
</script>
</body></html>
"""
