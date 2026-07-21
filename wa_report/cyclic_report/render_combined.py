"""Combined interactive report: cyclic charts + chat, cross-linked, in one file.

A single self-contained HTML page with two panes:

  * **Charts** (left) — one interactive SVG per 12-hour window. Moving the cursor
    shows a **time crosshair** across all panels, a **value guide** on each panel,
    and a live **value table**; **clicking locks** the crosshair + table (click
    again to unlock). Photo-burst markers are clickable.
  * **Chat** (right) — the transcript with image thumbnails.

Cross-navigation both ways:
  * click a **photo-burst marker** on a chart -> jumps to those images in the chat;
  * click the **📈 button** on a chat image -> jumps to that moment on the chart
    and locks the crosshair there.

The charts are drawn client-side from data embedded as JSON, so no server or
external asset is needed (works from a downloaded file).
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import List, Optional, Sequence

import pandas as pd

from .. import media
from ..parser import load_and_merge
from .alarms import load_alarms
from .bursts import detect_bulk_events
from .config import ALARM_COLORS, DEFAULT_VARIABLES, VARIABLE_UNITS
from .data_loader import load_cyclic
from .plotting import window_title
from .windowing import split_windows

_EPOCH = pd.Timestamp("1970-01-01")


def _esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def _ms(dt) -> int:
    """Milliseconds since 1970 treating the (naive) timestamp as wall-clock.

    Used only as a consistent numeric axis shared by cyclic samples, alarms,
    bursts and chat messages — never as a real UTC instant.
    """
    return int((pd.Timestamp(dt) - _EPOCH).total_seconds() * 1000)


def build_combined_html(folders, cyclic_source, variables: Sequence[str],
                        device_label: str = "", alarms_source=None,
                        min_photos: int = 3, window_minutes: int = 10,
                        window_hours: int = 12, max_img_dim: int = 480,
                        out_path: Optional[Path] = None) -> str:
    variables = list(variables) or list(DEFAULT_VARIABLES)

    # --- Chat + cyclic + alarms + bursts -------------------------------------
    msgs, _ = load_and_merge(folders)
    df, missing = load_cyclic(cyclic_source, variables)
    present = [v for v in variables if v not in missing]
    alarms = load_alarms(alarms_source)

    img_times = sorted(
        m.dt for m in msgs
        if not m.is_system and m.attachment and media.is_image(m.attachment)
    )
    events = detect_bulk_events(img_times, min_photos=min_photos,
                                window_minutes=window_minutes)

    # --- Chat pane HTML + a ts -> message-id map for burst links -------------
    cache = media.MediaCache(max_dim=max_img_dim)
    paths = [
        p for m in msgs if m.attachment and media.is_image(m.attachment)
        for p in [media.resolve(m.attachment, m.source_dir)] if p
    ]
    if paths:
        cache.prewarm(paths)

    chat_parts: List[str] = []
    img_ts_to_id: dict[int, str] = {}
    cur_day = None
    idx = 0
    n_imgs = 0
    for m in msgs:
        if m.is_system or m.is_deleted:
            continue
        idx += 1
        mid = f"m{idx}"
        day = m.dt.strftime("%d/%m/%Y")
        if day != cur_day:
            cur_day = day
            chat_parts.append(f"<div class='c-day' id='day-{_esc(day)}'>{_esc(day)}</div>")
        speaker = _esc(m.sender or "System")
        tstr = m.dt.strftime("%H:%M")
        tsms = _ms(m.dt)
        if m.attachment and media.is_image(m.attachment):
            p = media.resolve(m.attachment, m.source_dir)
            uri = cache.data_uri(p) if p else None
            img_ts_to_id.setdefault(tsms, mid)
            n_imgs += 1
            body = (f"<img class='c-img' src='{uri}' loading='lazy' alt=''>"
                    if uri else "<span class='c-missing'>[image not found]</span>")
            jump = (f"<button class='c-jump' title='Show this moment on the chart' "
                    f"onclick='jumpToChart({tsms})'>📈</button>")
            chat_parts.append(
                f"<div class='c-msg' id='{mid}' data-ts='{tsms}'>"
                f"<div class='c-meta'><b>{speaker}</b><span>{tstr}</span>{jump}</div>"
                f"{body}</div>"
            )
        else:
            lines = [l for l in m.text_lines() if l.strip()]
            if m.is_media_omitted:
                lines = ["[media omitted]"]
            if not lines:
                continue
            txt = "<br>".join(_esc(l) for l in lines)
            chat_parts.append(
                f"<div class='c-msg' id='{mid}' data-ts='{tsms}'>"
                f"<div class='c-meta'><b>{speaker}</b><span>{tstr}</span></div>"
                f"<div class='c-text' dir='auto'>{txt}</div></div>"
            )

    # --- Per-window chart data ----------------------------------------------
    windows_json: List[dict] = []
    cards: List[str] = []
    for wi, (start, end, sub) in enumerate(split_windows(df, hours=window_hours)):
        dts = [_ms(t) for t in sub["DateTime"]]
        cols = {v: sub[v].tolist() for v in present}
        samples = []
        for r, t in enumerate(dts):
            row = [t]
            for v in present:
                x = cols[v][r]
                row.append(None if pd.isna(x) else round(float(x), 2))
            samples.append(row)
        if not alarms.empty:
            aw = alarms[(alarms["DateTime"] >= start) & (alarms["DateTime"] < end)]
            al = [[_ms(dt), a] for dt, a in zip(aw["DateTime"], aw["Alarm"])]
        else:
            al = []
        bl = [[_ms(e.start), e.count, img_ts_to_id.get(_ms(e.start))]
              for e in events if start <= e.start < end]
        windows_json.append({
            "i": wi, "title": window_title(start, end),
            "t0": _ms(start), "t1": _ms(end),
            "samples": samples, "alarms": al, "bursts": bl,
        })
        cards.append(
            f"<div class='card' id='card-{wi}'>"
            f"<div class='card-h'>{_esc(window_title(start, end))}"
            f"<span class='lock-badge' id='lock-{wi}' hidden>🔒 locked</span></div>"
            f"<div class='chart-row'><svg class='chart' id='chart-{wi}'></svg>"
            f"<div class='readout' id='readout-{wi}'></div></div></div>"
        )

    data = {
        "vars": present,
        "units": {v: VARIABLE_UNITS.get(v, "") for v in present},
        "alarmColors": ALARM_COLORS,
        "windows": windows_json,
    }

    missing_note = (
        f"<div class='warn'>Variables not in the CSV, skipped: {_esc(', '.join(missing))}.</div>"
        if missing else ""
    )
    overlap_note = ""
    if img_times and not any(w["bursts"] for w in windows_json):
        overlap_note = ("<div class='warn'>No photo bursts fall inside the log's "
                        "time range — the chat and cyclic CSV don't overlap in time.</div>")

    doc = (_PAGE
           .replace("__TITLE__", _esc(device_label) or "Combined report")
           .replace("__DEVICE__", _esc(device_label) or "Cyclic ⟷ Chat")
           .replace("__NWIN__", str(len(windows_json)))
           .replace("__NBURST__", str(sum(len(w["bursts"]) for w in windows_json)))
           .replace("__NIMG__", str(n_imgs))
           .replace("__NALARM__", str(int(len(alarms))))
           .replace("__NOTES__", missing_note + overlap_note)
           .replace("__CARDS__", "\n".join(cards) or "<p class='muted'>No cyclic data to plot.</p>")
           .replace("__CHAT__", "\n".join(chat_parts) or "<p class='muted'>No chat messages.</p>")
           .replace("/*__DATA__*/", json.dumps(data)))

    if out_path is not None:
        Path(out_path).write_text(doc, encoding="utf-8")
    return doc


# The page: CSS + markup + JS. Kept as a plain string (tokens replaced above) so
# the JS/CSS braces don't need escaping.
_PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — Combined report</title>
<style>
  * { box-sizing:border-box; }
  body { margin:0; font-family:"Segoe UI",system-ui,Arial,sans-serif; color:#1d2733;
    background:#f4f6f9; font-size:14px; }
  header { background:#0a6ebd; color:#fff; padding:12px 20px; }
  header h1 { margin:0; font-size:18px; }
  header .sub { opacity:.9; font-size:12.5px; margin-top:2px; }
  .stats { display:flex; gap:8px; flex-wrap:wrap; padding:10px 20px 0; }
  .stat { background:#fff; border:1px solid #e3e8ee; border-radius:9px; padding:6px 12px; }
  .stat b { color:#0a6ebd; font-size:16px; } .stat span { color:#5b6b7b; font-size:11px; }
  .warn { margin:8px 20px 0; color:#8a5b00; background:#fff6e5; border:1px solid #ffe2a8;
    border-radius:8px; padding:6px 12px; font-size:13px; }
  .muted { color:#5b6b7b; font-style:italic; }
  .wrap { display:flex; gap:14px; padding:12px 20px 20px; align-items:flex-start; }
  .charts { flex:1 1 auto; min-width:0; max-height:calc(100vh - 120px); overflow:auto; }
  .chat { flex:0 0 360px; width:360px; max-height:calc(100vh - 120px); overflow:auto;
    background:#fff; border:1px solid #e3e8ee; border-radius:10px; padding:10px; }
  .card { background:#fff; border:1px solid #e3e8ee; border-radius:10px; padding:8px 12px 12px;
    margin-bottom:14px; }
  .card-h { font-size:14px; font-weight:600; color:#0a6ebd; margin:2px 0 6px; }
  .lock-badge { font-size:11px; color:#c0392b; margin-left:8px; font-weight:600; }
  .chart-row { display:flex; gap:10px; align-items:flex-start; }
  svg.chart { flex:1 1 auto; width:100%; height:auto; cursor:crosshair; }
  .readout { flex:0 0 150px; font-size:12px; }
  .readout table { border-collapse:collapse; width:100%; }
  .readout td { border-bottom:1px solid #eef2f6; padding:2px 4px; }
  .readout td.k { color:#5b6b7b; } .readout td.v { text-align:right; font-weight:600; }
  .readout .hint { color:#5b6b7b; font-style:italic; margin-top:6px; font-size:11px; }
  .c-day { position:sticky; top:0; background:#eef4fb; color:#0a6ebd; font-weight:600;
    padding:4px 8px; border-radius:6px; margin:8px 0 6px; font-size:12.5px; z-index:2; }
  .c-msg { padding:4px 6px; border-radius:8px; margin-bottom:4px; }
  .c-msg.flash { animation:flash 1.6s ease-out; }
  @keyframes flash { 0%{ background:#fff3bf; } 100%{ background:transparent; } }
  .c-meta { display:flex; gap:6px; align-items:center; font-size:12px; color:#5b6b7b; }
  .c-meta b { color:#1d2733; } .c-meta span { font-size:11px; }
  .c-jump { margin-left:auto; border:0; background:#eef4fb; border-radius:6px; cursor:pointer;
    font-size:12px; padding:1px 6px; }
  .c-jump:hover { background:#d7e8fa; }
  .c-img { max-width:100%; max-height:220px; border-radius:6px; border:1px solid #e3e8ee;
    margin-top:3px; display:block; }
  .c-text { white-space:pre-wrap; word-wrap:break-word; }
  .c-missing { color:#5b6b7b; font-style:italic; }
  @media (max-width:900px){ .wrap{ flex-direction:column; } .chat{ width:100%; flex-basis:auto; }
    .charts,.chat{ max-height:none; } }
</style></head><body>
<header><h1>__DEVICE__</h1><div class="sub">Interactive cyclic charts ⟷ WhatsApp chat · hover a chart for values, click to lock</div></header>
<div class="stats">
  <div class="stat"><b>__NWIN__</b> <span>windows</span></div>
  <div class="stat"><b>__NBURST__</b> <span>photo bursts</span></div>
  <div class="stat"><b>__NIMG__</b> <span>chat images</span></div>
  <div class="stat"><b>__NALARM__</b> <span>alarms</span></div>
</div>
__NOTES__
<div class="wrap">
  <div class="charts" id="charts">__CARDS__</div>
  <div class="chat" id="chat">__CHAT__</div>
</div>
<script id="data" type="application/json">/*__DATA__*/</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const SVGNS = 'http://www.w3.org/2000/svg';
const VB_W = 1000, ML = 70, MR = 16, TOP = 8, PANEL_H = 78, PANEL_GAP = 6,
      XAXIS_H = 22, LANE_ROW = 14;
const VARS = DATA.vars, UNITS = DATA.units;

function el(tag, attrs){ const e=document.createElementNS(SVGNS, tag);
  for(const k in attrs) e.setAttribute(k, attrs[k]); return e; }
function fmtTime(ms){ const d=new Date(ms);
  const p=n=>String(n).padStart(2,'0'); return p(d.getUTCHours())+':'+p(d.getUTCMinutes()); }
function nearest(samples, t){ let lo=0, hi=samples.length-1; if(hi<0) return -1;
  while(lo<hi){ const m=(lo+hi)>>1; if(samples[m][0]<t) lo=m+1; else hi=m; }
  if(lo>0 && (t-samples[lo-1][0])<(samples[lo][0]-t)) return lo-1; return lo; }

const CTRL = {};   // per-window controller state

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

  // ranges per variable
  const ranges = VARS.map((v,k)=>{
    let mn=Infinity, mx=-Infinity;
    for(const s of win.samples){ const y=s[k+1]; if(y==null) continue;
      if(y<mn)mn=y; if(y>mx)mx=y; }
    if(mn===Infinity){ mn=0; mx=1; }
    if(mn===mx){ mn-=1; mx+=1; }
    const pad=(mx-mn)*0.08; return [mn-pad, mx+pad];
  });
  const panelTop = k => TOP + laneH + k*(PANEL_H+PANEL_GAP);
  const yOf = (k,val) => { const [mn,mx]=ranges[k]; const top=panelTop(k);
    return top + (1-(val-mn)/(mx-mn))*PANEL_H; };
  const panelsBottom = panelTop(nV-1) + PANEL_H;

  let parts = [];
  // alarm lane
  if(alarmTypes.length){
    alarmTypes.forEach((a,r)=>{
      const y = TOP + r*LANE_ROW + LANE_ROW/2;
      const col = DATA.alarmColors[a] || '#888';
      parts.push(`<text x="${plotL-6}" y="${y+3}" text-anchor="end" font-size="8" fill="${col}">${a}</text>`);
      for(const ev of win.alarms){ if(ev[1]!==a) continue;
        parts.push(`<rect x="${xOf(ev[0])-1.5}" y="${y-3}" width="3" height="6" fill="${col}"/>`); }
    });
  }
  // panels
  VARS.forEach((v,k)=>{
    const top=panelTop(k), [mn,mx]=ranges[k];
    parts.push(`<rect x="${plotL}" y="${top}" width="${plotR-plotL}" height="${PANEL_H}" fill="none" stroke="#e3e8ee"/>`);
    // y ticks (min/mid/max)
    [mn,(mn+mx)/2,mx].forEach(val=>{
      const y=yOf(k,val);
      parts.push(`<line x1="${plotL}" y1="${y}" x2="${plotR}" y2="${y}" stroke="#eef2f6"/>`);
      parts.push(`<text x="${plotL-5}" y="${y+3}" text-anchor="end" font-size="8" fill="#5b6b7b">${val.toFixed(0)}</text>`);
    });
    parts.push(`<text x="${plotL+4}" y="${top+11}" font-size="10" font-weight="bold" fill="#1d2733">${v} (${UNITS[v]||''})</text>`);
    // line (break on nulls)
    let d='', pen=false;
    for(const s of win.samples){ const val=s[k+1];
      if(val==null){ pen=false; continue; }
      const x=xOf(s[0]), y=yOf(k,val);
      d += (pen?'L':'M')+x.toFixed(1)+' '+y.toFixed(1)+' '; pen=true; }
    parts.push(`<path d="${d}" fill="none" stroke="#0a6ebd" stroke-width="1.4"/>`);
    // value guide + dot (hidden until hover)
    parts.push(`<line class="hg" id="hg-${win.i}-${k}" x1="${plotL}" x2="${plotR}" y1="0" y2="0" stroke="#c0392b" stroke-width="0.8" stroke-dasharray="4 3" visibility="hidden"/>`);
    parts.push(`<circle class="dot" id="dot-${win.i}-${k}" r="3" fill="#c0392b" visibility="hidden"/>`);
  });
  // x axis ticks
  const nTicks=6;
  for(let i=0;i<=nTicks;i++){ const t=win.t0+(win.t1-win.t0)*i/nTicks; const x=xOf(t);
    parts.push(`<line x1="${x}" y1="${panelsBottom}" x2="${x}" y2="${panelsBottom+4}" stroke="#5b6b7b"/>`);
    parts.push(`<text x="${x}" y="${panelsBottom+15}" text-anchor="middle" font-size="9" fill="#5b6b7b">${fmtTime(t)}</text>`); }
  // burst markers (vertical) + clickable hit areas
  for(const b of win.bursts){ const x=xOf(b[0]);
    parts.push(`<line x1="${x}" y1="${TOP}" x2="${x}" y2="${panelsBottom}" stroke="#c0392b" stroke-width="1.2" stroke-dasharray="5 3"/>`);
    parts.push(`<text x="${x}" y="${TOP-1}" text-anchor="middle" font-size="8" font-weight="bold" fill="#c0392b">${fmtTime(b[0])}</text>`);
    const cid = b[2] || '';
    parts.push(`<rect class="burst-hit" x="${x-5}" y="${TOP}" width="10" height="${panelsBottom-TOP}" fill="transparent" style="cursor:pointer" data-cid="${cid}"><title>${b[1]} photos at ${fmtTime(b[0])} — click to see in chat</title></rect>`);
  }
  // crosshair (vertical), hidden until hover
  parts.push(`<line class="cx" id="cx-${win.i}" x1="0" x2="0" y1="${TOP}" y2="${panelsBottom}" stroke="#111" stroke-width="0.8" visibility="hidden"/>`);
  svg.innerHTML = parts.join('');

  // readout table
  const ro = document.getElementById('readout-'+win.i);
  let rows = `<table><tr><td class="k">Time</td><td class="v" id="ro-${win.i}-t">—</td></tr>`;
  VARS.forEach((v,k)=>{ rows += `<tr><td class="k">${v}</td><td class="v" id="ro-${win.i}-${k}">—</td></tr>`; });
  rows += `</table><div class="hint" id="hint-${win.i}">hover to read · click to lock</div>`;
  ro.innerHTML = rows;

  CTRL[win.i] = { win, svg, xOf, yOf, panelsBottom, locked:false };

  svg.addEventListener('mousemove', e=>{ const c=CTRL[win.i]; if(c.locked) return;
    updateAt(win.i, xToTime(win.i, e)); });
  svg.addEventListener('mouseleave', ()=>{ const c=CTRL[win.i]; if(!c.locked) hideCursor(win.i); });
  svg.addEventListener('click', e=>{
    if(e.target.classList.contains('burst-hit')){ const cid=e.target.getAttribute('data-cid');
      if(cid) jumpToChat(cid); return; }
    const c=CTRL[win.i]; c.locked=!c.locked;
    document.getElementById('lock-'+win.i).hidden = !c.locked;
    document.getElementById('hint-'+win.i).textContent = c.locked ? 'locked · click to unlock' : 'hover to read · click to lock';
    if(c.locked) updateAt(win.i, xToTime(win.i, e));
  });
}

function xToTime(i, e){ const c=CTRL[i]; const r=c.svg.getBoundingClientRect();
  const vbX=(e.clientX-r.left)/r.width*VB_W;
  const frac=(vbX-ML)/((VB_W-MR)-ML);
  return c.win.t0 + Math.max(0,Math.min(1,frac))*(c.win.t1-c.win.t0); }

function updateAt(i, t){ const c=CTRL[i], win=c.win;
  const idx=nearest(win.samples, t); if(idx<0) return;
  const s=win.samples[idx]; const x=c.xOf(s[0]);
  const cx=document.getElementById('cx-'+i); cx.setAttribute('x1',x); cx.setAttribute('x2',x);
  cx.setAttribute('visibility','visible');
  document.getElementById('ro-'+i+'-t').textContent = fmtTime(s[0]);
  VARS.forEach((v,k)=>{ const val=s[k+1]; const hg=document.getElementById('hg-'+i+'-'+k);
    const dot=document.getElementById('dot-'+i+'-'+k); const cell=document.getElementById('ro-'+i+'-'+k);
    if(val==null){ hg.setAttribute('visibility','hidden'); dot.setAttribute('visibility','hidden'); cell.textContent='—'; return; }
    const y=c.yOf(k,val);
    hg.setAttribute('y1',y); hg.setAttribute('y2',y); hg.setAttribute('visibility','visible');
    dot.setAttribute('cx',x); dot.setAttribute('cy',y); dot.setAttribute('visibility','visible');
    cell.textContent = val + (UNITS[v]? ' '+UNITS[v] : '');
  });
}
function hideCursor(i){ document.getElementById('cx-'+i).setAttribute('visibility','hidden');
  VARS.forEach((v,k)=>{ document.getElementById('hg-'+i+'-'+k).setAttribute('visibility','hidden');
    document.getElementById('dot-'+i+'-'+k).setAttribute('visibility','hidden');
    document.getElementById('ro-'+i+'-'+k).textContent='—'; });
  document.getElementById('ro-'+i+'-t').textContent='—'; }

function jumpToChat(cid){ const t=document.getElementById(cid); if(!t) return;
  t.scrollIntoView({behavior:'smooth', block:'center'});
  t.classList.remove('flash'); void t.offsetWidth; t.classList.add('flash'); }

function jumpToChart(ts){ const w=DATA.windows.find(w=>ts>=w.t0 && ts<w.t1); if(!w) return;
  const card=document.getElementById('card-'+w.i);
  card.scrollIntoView({behavior:'smooth', block:'center'});
  const c=CTRL[w.i]; c.locked=true;
  document.getElementById('lock-'+w.i).hidden=false;
  document.getElementById('hint-'+w.i).textContent='locked · click to unlock';
  updateAt(w.i, ts); }

DATA.windows.forEach(buildChart);
</script>
</body></html>
"""
