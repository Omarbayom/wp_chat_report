"""Two linked, interactive pages (instead of one merged file).

  * ``charts.html`` — the interactive cyclic charts. The **whole** cyclic log is
    always shown (independent of the chat): a compressed *stock-style* overview
    of the entire range sits on top, with a **draggable / resizable window**
    (brush) you drag to pick any span. Below it a detail chart draws only that
    span — hover for a value table + time crosshair, click to lock. A **date/time
    search** (with seconds) sets and reflects the window exactly, and a **variable
    picker** lets you choose one or many signals (VTi/VTe/PIP/PEEP/RR/FIO2…) on
    the Y axis live. Alarms recorded with no cyclic data are still shown and can
    be stepped through (◀ / ▶). Photo-burst markers (only where cyclic data
    exists) open the chat page at the matching image.
  * ``report.html`` — the existing interactive chat report (search/filter/
    lightbox), with a 📈 button on each image that opens the charts page at that
    moment (and centres the window there).

The two open each other in **named browser tabs** (``wa_report`` / ``wa_charts``),
so they stay side by side and connected. Save both files in the *same folder*.
``build_linked_pages`` returns a dict of the three pages.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Sequence

from .. import media
from ..render_html import render_html_str
from ..report import build_report
from .config import DEFAULT_VARIABLES
from .patient import build_patients_html
from .render_combined import _esc, _ms, build_payload
from .render_windows import build_windows_html
from .roster import build_roster


def _span(a, b) -> str:
    return f"{a:%d/%m/%Y %H:%M:%S} → {b:%d/%m/%Y %H:%M:%S}"


def _var_options(present, selected) -> str:
    return "".join(
        f"<label><input type='checkbox' value='{_esc(v)}'"
        f"{' checked' if v in selected else ''} onchange='onVarToggle()'> {_esc(v)}</label>"
        for v in present
    )


def build_charts_html(folders, cyclic_source, variables: Sequence[str],
                      device_label: str = "", alarms_source=None,
                      chat_href: str = "report.html",
                      windows_href: str = "windows.html", min_photos: int = 3,
                      window_minutes: int = 10, window_hours: int = 12,
                      patient_href: str = "", out_path: Optional[Path] = None) -> str:
    """Interactive charts page. The whole cyclic log is embedded and shown; the
    user drags a window over a compressed overview (or types a start/end time, or
    steps through alarms) to zoom the detail chart, and picks any variables on the
    Y axis. Burst markers open *chat_href* at the matching image; a ``?t=<ms>``
    query on load centres the window on that moment and locks it."""
    variables = list(variables) or list(DEFAULT_VARIABLES)
    payload, meta = build_payload(folders, cyclic_source, variables,
                                  alarms_source=alarms_source,
                                  min_photos=min_photos,
                                  window_minutes=window_minutes)
    payload["initialHours"] = window_hours if window_hours > 0 else 12
    # The patient banner is rendered client-side from payload["patients"] so it
    # follows the current view (which patient's segment you're looking at).
    patients = meta.get("patients", [])
    device_label = device_label or (patients[-1]["label"] if patients else "")

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
    ov_default = meta["default_sel"][0] if meta["default_sel"] else (meta["present"][0] if meta["present"] else "")
    ov_var_opts = "".join(
        f"<option value='{_esc(v)}'{' selected' if v == ov_default else ''}>{_esc(v)}</option>"
        for v in meta["present"]
    )
    doc = (_CHARTS_PAGE
           .replace("__TITLE__", _esc(device_label) or "Cyclic charts")
           .replace("__DEVICE__", _esc(device_label) or "Cyclic charts")
           .replace("__CHATLINK__", chat_link)
           .replace("__CHATHREF__", _esc(chat_href))
           .replace("__WINDOWSHREF__", _esc(windows_href))
           .replace("__VAROPTS__", _var_options(meta["present"], meta["default_sel"]))
           .replace("__OVVAROPTS__", ov_var_opts)
           .replace("__NSAMP__", str(meta["n_samples"]))
           .replace("__NBURST__", str(meta["n_bursts"]))
           .replace("__NALARM__", str(meta["n_alarms"]))
           .replace("__NMODE__", str(meta["n_modes"]))
           .replace("__NEVENT__", str(meta["n_events"]))
           .replace("__NOTES__", notes)
           .replace("__PATIENTHREF__", _esc(patient_href))
           .replace("/*__DATA__*/", json.dumps(payload)))
    if out_path is not None:
        Path(out_path).write_text(doc, encoding="utf-8")
    return doc


def build_linked_pages(folders, cyclic_source, variables: Sequence[str],
                       hospital: str = "", device_label: str = "",
                       alarms_source=None, min_photos: int = 3,
                       window_minutes: int = 10, window_hours: int = 12,
                       max_img_dim: int = 480, mode: str = "hourly",
                       buffer_minutes: int = 0, windows_hours: int = 1):
    """Return a dict of **three** interactive pages that link to each other. Save
    them side by side in one folder:

      * ``report.html``  — the chat report (1-hour sections, 24-hour times).
      * ``windows.html`` — one graph per fixed clock window (defaults to
        *windows_hours*; the user can re-slice live to 1/2/3/6/12/24h).
      * ``charts.html``  — the stock-style overview with a draggable window +
        date/time search + variable picker (defaults to *window_hours* wide).

    The three cross-link in named browser tabs (``wa_report`` / ``wa_windows`` /
    ``wa_charts``): photo-burst markers open the chat at the matching image, and
    the chat's 📈 buttons open the stock view at that moment.

    **The chat is optional.** If *folders* is empty/None (the user uploaded only
    the cyclic data), the chat page is skipped and the result has just
    ``windows.html`` + ``charts.html`` — those show the cyclic log (and any
    alarms) with no photo markers and no chat links.
    """
    has_chat = bool(folders)
    chat_href = "report.html" if has_chat else ""

    # Per-patient roster from the cyclic CSV + log ("Add New Patient" handovers).
    # Drives the Patients page, the banners, and a blank report title. The current
    # (last) patient supplies the label; earlier patients are b1/b2/…
    roster = build_roster(cyclic_source, alarms_source)
    device_label = device_label or (roster[-1]["label"] if roster else "")

    result = {}
    if has_chat:
        report = build_report(folders, hospital or "—", device_label or "—",
                              mode=mode, buffer_minutes=buffer_minutes)
        cache = media.MediaCache(max_dim=max_img_dim)
        imgs = []
        for c in report.cycles:
            resolved, _ = media.resolve_images(c.photo_names)
            imgs.extend(p for p, _dt in resolved)
        if imgs:
            cache.prewarm(imgs)
        nav_links = (
            '<a class="nav-btn" href="windows.html" target="wa_windows">📊 Windowed view</a>'
            '<a class="nav-btn" href="charts.html" target="wa_charts">📈 Stock view</a>'
        )
        if roster:
            label = "Patients" if len(roster) > 1 else "Patient"
            nav_links += f'<a class="nav-btn" href="patient.html" target="wa_patient">👤 {label}</a>'
        result["report.html"] = render_html_str(
            report, cache, chart_href="charts.html", hour24=True,
            nav_links=nav_links)

    patient_href = "patient.html" if roster else ""
    result["windows.html"] = build_windows_html(
        folders, cyclic_source, variables, device_label=device_label,
        alarms_source=alarms_source, chat_href=chat_href,
        stock_href="charts.html", min_photos=min_photos,
        window_minutes=window_minutes, window_hours=windows_hours,
        patient_href=patient_href,
    )
    result["charts.html"] = build_charts_html(
        folders, cyclic_source, variables, device_label=device_label,
        alarms_source=alarms_source, chat_href=chat_href,
        windows_href="windows.html", min_photos=min_photos,
        window_minutes=window_minutes, window_hours=window_hours,
        patient_href=patient_href,
    )
    # Dedicated, cross-linked Patients page (one card per patient on the device).
    if roster:
        links = {}
        if has_chat:
            links["Chat"] = ("report.html", "wa_report")
        links["Windowed view"] = ("windows.html", "wa_windows")
        links["Stock view"] = ("charts.html", "wa_charts")
        result["patient.html"] = build_patients_html(
            roster, device_label=device_label, links=links, chart_href="charts.html")
    return result


_CHARTS_PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — Cyclic charts</title>
<style>
  * { box-sizing:border-box; }
  body { margin:0; font-family:"Segoe UI",system-ui,Arial,sans-serif; color:#1d2733;
    background:#f4f6f9; font-size:14px; }
  header { background:#0a6ebd; color:#fff; padding:12px 20px; display:flex; align-items:center; gap:14px; flex-wrap:wrap; }
  header h1 { margin:0; font-size:18px; }
  header .sub { opacity:.9; font-size:12.5px; }
  header .ctl { margin-left:auto; display:flex; align-items:center; gap:10px; }
  header a.other { color:#fff; background:rgba(255,255,255,.18); padding:6px 12px;
    border-radius:8px; text-decoration:none; font-size:13px; }
  header a.other:hover { background:rgba(255,255,255,.32); }
  .stats { display:flex; gap:8px; flex-wrap:wrap; padding:10px 20px 0; }
  .stat { background:#fff; border:1px solid #e3e8ee; border-radius:9px; padding:6px 12px; }
  .stat b { color:#0a6ebd; font-size:16px; } .stat span { color:#5b6b7b; font-size:11px; }
  .warn { margin:8px 20px 0; color:#8a5b00; background:#fff6e5; border:1px solid #ffe2a8;
    border-radius:8px; padding:6px 12px; font-size:13px; line-height:1.5; }
  .muted { color:#5b6b7b; font-style:italic; }
  .controls { display:flex; gap:10px; align-items:flex-end; flex-wrap:wrap;
    background:#fff; border:1px solid #e3e8ee; border-radius:10px; padding:10px 14px; margin:12px 20px 0; }
  .controls .fld, .controls label.q { display:flex; flex-direction:column; gap:3px; font-size:11px; color:#5b6b7b; }
  .controls input[type="datetime-local"] { font:inherit; font-size:13px; padding:5px 8px; border:1px solid #cfd8e3; border-radius:6px; color:#1d2733; }
  .controls input[type="number"] { font:inherit; font-size:13px; padding:5px 8px; border:1px solid #cfd8e3; border-radius:6px; color:#1d2733; width:72px; }
  .controls .wrow { display:flex; gap:4px; align-items:center; }
  .controls select, .controls button { font:inherit; font-size:13px; padding:6px 10px; border-radius:6px; border:1px solid #cfd8e3; background:#fff; cursor:pointer; }
  .controls button.primary { background:#0a6ebd; color:#fff; border-color:#0a6ebd; }
  .controls button:hover { border-color:#0a6ebd; }
  .controls .span { font-size:12px; color:#1d2733; margin-left:auto; text-align:right; line-height:1.4; }
  .controls .span b { color:#0a6ebd; }
  .varbar { display:flex; gap:6px; align-items:center; flex-wrap:wrap;
    background:#fff; border:1px solid #e3e8ee; border-radius:10px; padding:8px 14px; margin:10px 20px 0; }
  .varbar .lbl { font-size:12px; color:#5b6b7b; font-weight:600; margin-right:4px; }
  .varbar label { font-size:13px; display:inline-flex; align-items:center; gap:4px;
    background:#f4f6f9; border:1px solid #e3e8ee; border-radius:20px; padding:3px 10px; cursor:pointer; }
  .varbar label:hover { border-color:#0a6ebd; }
  .overview { background:#fff; border:1px solid #e3e8ee; border-radius:10px; padding:8px 12px 4px; margin:12px 20px 0; }
  .overview .ov-h { font-size:12px; color:#5b6b7b; margin:0 0 4px; }
  svg.ov { width:100%; height:auto; display:block; touch-action:none; }
  .charts { padding:12px 20px 24px; }
  .card { background:#fff; border:1px solid #e3e8ee; border-radius:10px; padding:8px 12px 12px; margin-bottom:14px; }
  .card-h { font-size:14px; font-weight:600; color:#0a6ebd; margin:2px 0 6px; }
  .lock-badge { font-size:11px; color:#c0392b; margin-left:8px; font-weight:600; }
  .alarm-only { font-size:11px; color:#8a5b00; margin-left:8px; font-weight:600; }
  .chart-row { display:flex; gap:10px; align-items:flex-start; }
  svg.chart { flex:1 1 auto; width:100%; height:auto; cursor:crosshair; user-select:none; }
  .readout { flex:0 0 160px; font-size:12px; }
  .readout table { border-collapse:collapse; width:100%; }
  .readout td { border-bottom:1px solid #eef2f6; padding:2px 4px; }
  .readout td.k { color:#5b6b7b; } .readout td.v { text-align:right; font-weight:600; }
  .readout td.al { text-align:left; font-weight:600; font-size:11px; line-height:1.35; }
  .readout .hint { color:#5b6b7b; font-style:italic; margin-top:6px; font-size:11px; }
  /* focus mode (double-click a panel) */
  .focus-note { font-size:12px; color:#0a6ebd; background:#eaf4fc; border:1px solid #bcdcf5;
    border-radius:20px; padding:3px 10px; margin-left:auto; }
  .focus-note button { font:inherit; font-size:11.5px; margin-left:6px; padding:1px 8px;
    border-radius:12px; border:1px solid #0a6ebd; background:#fff; color:#0a6ebd; cursor:pointer; }
  /* event / mode titles under the time axis — selectable text, clickable chips */
  .ledger { margin-top:8px; border-top:1px solid #eef2f6; padding-top:6px; }
  .ledger-h { font-size:11.5px; color:#5b6b7b; margin:0 0 4px; }
  .ledger-h b { color:#1d2733; }
  .ledger .chips { display:flex; flex-wrap:wrap; gap:5px; max-height:150px; overflow:auto;
    user-select:text; -webkit-user-select:text; }
  .chip { font-size:11.5px; border-radius:14px; padding:2px 9px; cursor:pointer;
    user-select:text; -webkit-user-select:text; background:#e9f7f7; border:1px solid #b6e4e4; color:#14555a; }
  .chip b { font-variant-numeric:tabular-nums; color:#0aa3a3; margin-right:5px; font-weight:700; }
  .chip:hover { border-color:#0aa3a3; }
  .chip.sel { background:#0aa3a3; border-color:#0aa3a3; color:#fff; } .chip.sel b { color:#fff; }
  .chip.mode { background:#f3eefc; border-color:#dccdf5; color:#452a75; }
  .chip.mode b { color:#6f42c1; }
  .chip.mode.sel { background:#6f42c1; border-color:#6f42c1; color:#fff; }
  /* per-window statistics */
  .statbox { margin-top:8px; border-top:1px solid #eef2f6; padding-top:6px; }
  .statbox summary { cursor:pointer; font-size:12px; font-weight:600; color:#0a6ebd; }
  table.st { border-collapse:collapse; margin-top:6px; font-size:11.5px; }
  table.st th, table.st td { border:1px solid #eef2f6; padding:2px 9px; text-align:right;
    font-variant-numeric:tabular-nums; }
  table.st th { background:#f7f9fc; color:#5b6b7b; font-weight:600; }
  table.st td.n, table.st th.n { text-align:left; font-weight:600; color:#1d2733; }
  table.st .u { color:#5b6b7b; font-weight:400; font-size:10.5px; }
  .stat-foot { font-size:11px; color:#5b6b7b; margin-top:5px; }
  @media (max-width:720px){ .chart-row{ flex-direction:column; } .readout{ flex-basis:auto; width:100%; } }
</style></head><body>
<header><h1>__DEVICE__</h1><div class="sub">set a range to zoom · drag the window inside · hover to read · click to lock · double-click a graph to focus it</div>
  <div class="ctl">
    <a class="other" href="__WINDOWSHREF__" target="wa_windows">Windowed view ↗</a>
    __CHATLINK__
  </div></header>
<div class="stats">
  <div class="stat"><b>__NSAMP__</b> <span>cyclic samples</span></div>
  <div class="stat"><b>__NMODE__</b> <span>mode changes</span></div>
  <div class="stat"><b>__NEVENT__</b> <span>events</span></div>
  <div class="stat"><b>__NALARM__</b> <span>alarms</span></div>
  <div class="stat"><b>__NBURST__</b> <span>photo bursts</span></div>
</div>
<div id="patient-banner"></div>
__NOTES__

<div class="varbar">
  <span class="lbl">Y axis:</span>
  __VAROPTS__
  <span class="focus-note" id="focus-note" hidden></span>
</div>

<div class="controls">
  <label class="q">Range start (zooms overview)
    <input type="datetime-local" id="q-start" step="1">
  </label>
  <label class="q">Range end (zooms overview)
    <input type="datetime-local" id="q-end" step="1">
  </label>
  <button class="primary" id="q-apply">Set range</button>
  <button id="q-reset">Full range</button>
  <label class="q">Window width
    <select id="q-width" onchange="setWidthHours(+this.value)">
      <option value="1">1 hour</option>
      <option value="2">2 hours</option>
      <option value="3">3 hours</option>
      <option value="6">6 hours</option>
      <option value="12">12 hours</option>
      <option value="24">24 hours</option>
      <option value="0">Whole range</option>
    </select>
  </label>
  <label class="q">Custom width
    <span class="wrow">
      <input type="number" id="q-width-n" min="1" step="1" placeholder="e.g. 90">
      <select id="q-width-u">
        <option value="min">min</option>
        <option value="hour" selected>hours</option>
        <option value="day">days</option>
      </select>
      <button type="button" id="q-width-apply">Set</button>
    </span>
  </label>
  <button id="al-prev" title="Move the window to the previous alarm">◀ Alarm</button>
  <button id="al-next" title="Move the window to the next alarm">Alarm ▶</button>
  <label class="q">Go to date &amp; time
    <span class="wrow">
      <input type="datetime-local" id="g-time" step="1">
      <button class="primary" type="button" id="g-go">Go</button>
    </span>
  </label>
  <div class="span" id="span-lbl">—</div>
</div>
<div style="font-size:11.5px;color:#5b6b7b;margin:4px 20px 0">Tip: use <b>←</b> / <b>→</b> to step the cursor through the data — hold to move faster.</div>

<div class="overview">
  <div class="ov-h" id="ov-h">Overview — set a range to zoom, then drag the window inside it</div>
  <div style="font-size:12px;color:#5b6b7b;margin:0 0 4px">Trend variable:
    <select id="ov-var" onchange="setOvVar(this.value)">__OVVAROPTS__</select></div>
  <div id="patient-legend" style="font-size:11.5px;color:#5b6b7b;margin:2px 0 4px"></div>
  <svg class="ov" id="overview"></svg>
</div>

<div class="charts" id="charts"></div>
<script id="data" type="application/json">/*__DATA__*/</script>
<script>
const CHAT_HREF = "__CHATHREF__";
function jumpToChat(cid){ if(!cid || !CHAT_HREF) return; window.open(CHAT_HREF + '#' + cid, 'wa_report'); }
</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const ALLVARS = DATA.vars, UNITS = DATA.units;
const COL = {}; ALLVARS.forEach((v,i)=>{ COL[v]=i+1; });
let VARS = (DATA.defaultVars && DATA.defaultVars.length ? DATA.defaultVars : ALLVARS).slice();
let OVVAR = (DATA.defaultVars && DATA.defaultVars[0]) || ALLVARS[0];   // overview trend variable
const MODE_COLOR = '#6f42c1', EVENT_COLOR = '#0aa3a3';                 // modes / events
const HOUR = 3600000;
function modeAt(t){ let m=null; for(const md of DATA.modes){ if(md[0]<=t) m=md[1]; else break; } return m; }
function setOvVar(v){ OVVAR=v; buildOverview(); }
function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
// --- patient banner: follows the view (which patient's segment you're on) ---
const PATIENT_HREF = "__PATIENTHREF__";
const PATIENTS = DATA.patients || [];
const DEFAULT_TREND = '#0a6ebd';
function segAt(t){ for(const s of PATIENTS){ if(t>=s.t0 && t<=s.t1) return s; }
  return PATIENTS.length ? PATIENTS[PATIENTS.length-1] : null; }
// trend colour at time t: the patient segment's colour (falls back to blue)
function colorAt(t){ for(const s of PATIENTS){ if(t>=s.t0 && t<=s.t1) return s.color||DEFAULT_TREND; } return DEFAULT_TREND; }
function dot(c){ return `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;`
  +`background:${c};margin-right:2px;vertical-align:-1px"></span>`; }
function patientBannerHTML(seg, note){
  const info = (seg && seg.info) ? seg.info : [];
  if(!info.length) return '';
  const items = info.map(kv=>`<span style="white-space:nowrap"><span style="color:#5b6b7b">`
    +`${esc(kv[0].replace('Patient ',''))}</span> <b style="color:#1d2733">${esc(kv[1])}</b></span>`).join('');
  const noteHtml = note ? `<span style="color:#8a5b00;background:#fff6e5;border:1px solid #ffe2a8;`
    +`border-radius:12px;padding:1px 9px">${esc(note)}</span>` : '';
  const link = PATIENT_HREF ? `<a href="${esc(PATIENT_HREF)}" target="wa_patient" `
    +`style="margin-left:auto;color:#0a6ebd;text-decoration:none;font-weight:600">All patients ↗</a>` : '';
  const swatch = (seg && seg.color && PATIENTS.length>1) ? dot(seg.color) : '';
  return `<div style="display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center;background:#eef6fd;`
    +`border:1px solid #cfe4f7;border-radius:10px;padding:8px 14px;margin:12px 20px 0;font-size:13px">`
    +`<span style="font-weight:700;color:#0a6ebd;letter-spacing:.03em">${swatch}PATIENT</span>${items}${noteHtml}${link}</div>`;
}
// patient colour legend under the overview (only when >1 patient)
function renderPatientLegend(){
  const host=document.getElementById('patient-legend'); if(!host) return;
  if(PATIENTS.length<2){ host.innerHTML=''; return; }
  host.innerHTML = 'Patients: ' + PATIENTS.map(s=>
    `<span style="margin-right:10px;white-space:nowrap">${dot(s.color)}${esc(s.label)}</span>`).join('');
}
function updatePatientBanner(){
  const host=document.getElementById('patient-banner'); if(!host) return;
  if(!PATIENTS.length){ host.innerHTML=''; return; }
  const seg = segAt((SEL.t0+SEL.t1)/2);
  const n = PATIENTS.length;
  const note = n>1 ? `patient ${(seg? seg.index : n-1)+1} of ${n}` : '';
  host.innerHTML = patientBannerHTML(seg, note);
}
// --- detail chart geometry ---
const VB_W = 1000, ML = 70, MR = 16, TOP = 8, PANEL_H = 78, PANEL_GAP = 6, XAXIS_H = 26, LANE_ROW = 14;
const ALARM_SNAP_PX = 8;   // cursor within this many px of an alarm snaps onto it
// Typical cyclic sampling gap (median of consecutive sample diffs). A cursor time
// farther than COVER_TOL from any sample is treated as "no cyclic data here" — the
// value cells show "—" instead of a stale/far reading.
const SAMPLE_GAP = (function(){ const s=DATA.samples; if(!s||s.length<3) return 60000;
  const d=[]; for(let i=1;i<s.length;i++){ const g=s[i][0]-s[i-1][0]; if(g>0) d.push(g); }
  if(!d.length) return 60000; d.sort((a,b)=>a-b); return d[d.length>>1]; })();
const COVER_TOL = Math.max(SAMPLE_GAP*4, 15000);
// focus mode: double-clicking a variable panel blows it up and shrinks the rest
const FOCUS_H = 260, MINI_H = 26;
let FOCUS = null;                                        // focused variable, or null
function panelHeights(){ return VARS.map(v => !FOCUS ? PANEL_H : (v===FOCUS ? FOCUS_H : MINI_H)); }
function gridVals(mn, mx, h){ const n = h>=150 ? 4 : (h>=44 ? 2 : 1); const out=[];
  for(let i=0;i<=n;i++) out.push(mn+(mx-mn)*i/n); return out; }
function setFocus(v){ FOCUS = (v && v!==FOCUS) ? v : null; updateFocusNote(); renderDetail(); }
function updateFocusNote(){ const n=document.getElementById('focus-note'); if(!n) return;
  n.hidden = !FOCUS;
  if(FOCUS) n.innerHTML = `focused on <b>${esc(FOCUS)}</b> — the other graphs are shrunk`
    + `<button type="button" onclick="setFocus(null)">show all</button>`; }
// --- overview geometry ---
const OV_L = 70, OV_R = VB_W - 16, OV_TOP = 10, OV_CH = 66, OV_GAP = 6, OV_LANE = 9;

const TMIN = DATA.tMin, TMAX = DATA.tMax;                // full data bounds
const MINW = 60000;                                     // smallest window = 1 minute
// Two levels: REGION = the zoomed extent of the overview (set by the start/end
// fields / Quick width / Full range / Alarm). WINDOW (SEL) = the draggable brush
// inside REGION; the detail chart shows the window.
let REGION = { r0: TMIN, r1: TMAX };
let SEL = { t0: TMIN, t1: TMIN };
const CTRL = { locked:false };
function regSpan(){ return Math.max(1, REGION.r1 - REGION.r0); }

function pad(n){ return String(n).padStart(2,'0'); }
function fmtTime(ms){ const d=new Date(ms); return pad(d.getUTCHours())+':'+pad(d.getUTCMinutes())+':'+pad(d.getUTCSeconds()); }
function fmtHM(ms){ const d=new Date(ms); return pad(d.getUTCHours())+':'+pad(d.getUTCMinutes()); }
function fmtDate(ms){ const d=new Date(ms); return pad(d.getUTCDate())+'/'+pad(d.getUTCMonth()+1)+'/'+d.getUTCFullYear(); }
function fmtDateTime(ms){ return fmtDate(ms)+' '+fmtTime(ms); }
function fmtDur(ms){ const s=Math.round(ms/1000); const h=Math.floor(s/3600), m=Math.floor((s%3600)/60), ss=s%60;
  return (h?h+'h ':'')+(m?m+'m ':'')+(h?'':ss+'s'); }
function msToInput(ms){ const d=new Date(ms);
  return d.getUTCFullYear()+'-'+pad(d.getUTCMonth()+1)+'-'+pad(d.getUTCDate())+'T'+pad(d.getUTCHours())+':'+pad(d.getUTCMinutes())+':'+pad(d.getUTCSeconds()); }
function inputToMs(v){ if(!v) return null; const m=v.match(/(\d+)-(\d+)-(\d+)T(\d+):(\d+)(?::(\d+))?/);
  if(!m) return null; return Date.UTC(+m[1],+m[2]-1,+m[3],+m[4],+m[5],+(m[6]||0)); }
function nearest(samples, t){ let lo=0, hi=samples.length-1; if(hi<0) return -1;
  while(lo<hi){ const m=(lo+hi)>>1; if(samples[m][0]<t) lo=m+1; else hi=m; }
  if(lo>0 && (t-samples[lo-1][0])<(samples[lo][0]-t)) return lo-1; return lo; }
function lowerBound(t){ let lo=0, hi=DATA.samples.length; while(lo<hi){ const m=(lo+hi)>>1;
  if(DATA.samples[m][0] < t) lo=m+1; else hi=m; } return lo; }

// ============================ variable picker ============================
function onVarToggle(){
  const boxes=[...document.querySelectorAll('.varbar input[type=checkbox]')];
  const sel=boxes.filter(b=>b.checked).map(b=>b.value);
  if(!sel.length){ return; }                        // keep at least one variable
  VARS = ALLVARS.filter(v=>sel.includes(v));         // stable config order
  if(FOCUS && !VARS.includes(FOCUS)){ FOCUS=null; updateFocusNote(); }
  buildOverview(); renderDetail();
}

// ============================ OVERVIEW (stock) ============================
// The overview is zoomed to REGION; a draggable window (brush) inside it picks
// the detail sub-range. Axis ticks span REGION, so the bottom dates match it.
function ovX(t){ return OV_L + (t-REGION.r0)/regSpan()*(OV_R-OV_L); }
function ovT(x){ return REGION.r0 + (x-OV_L)/(OV_R-OV_L)*regSpan(); }
function inRegion(t){ return t>=REGION.r0 && t<=REGION.r1; }

function buildOverview(){
  const svg = document.getElementById('overview');
  const laneAl = DATA.alarms.length ? OV_LANE : 0;
  const laneMo = DATA.modes.length ? OV_LANE : 0;
  const laneEv = DATA.events.length ? OV_LANE : 0;
  const laneBu = DATA.bursts.length ? OV_LANE : 0;
  const H = OV_TOP + OV_CH + OV_GAP + laneAl + laneMo + laneEv + laneBu + 22;
  svg.setAttribute('viewBox', `0 0 ${VB_W} ${H}`);
  const pv = COL[OVVAR] ? OVVAR : (VARS[0] || ALLVARS[0]); const pc = COL[pv];
  let gmn=Infinity, gmx=-Infinity;
  for(const s of DATA.samples){ if(!inRegion(s[0])) continue; const y=s[pc]; if(y==null) continue; if(y<gmn)gmn=y; if(y>gmx)gmx=y; }
  if(gmn===Infinity){ gmn=0; gmx=1; } if(gmn===gmx){ gmn-=1; gmx+=1; }
  const yTop=OV_TOP, yBot=OV_TOP+OV_CH;
  const yOf = v => yBot - (v-gmn)/(gmx-gmn)*(yBot-yTop);
  let p=[];
  p.push(`<rect x="${OV_L}" y="${yTop}" width="${OV_R-OV_L}" height="${OV_CH}" fill="#fbfdff" stroke="#e3e8ee"/>`);
  // the trend line ("diagram") of the chosen variable over the region, drawn in
  // each patient's own colour (a break at every "Add New Patient" handover)
  let d='', pen=false, col=null;
  const flush=()=>{ if(d) p.push(`<path d="${d}" fill="none" stroke="${col||'#0a6ebd'}" stroke-width="1.2"/>`); d=''; pen=false; };
  for(let i=lowerBound(REGION.r0);i<DATA.samples.length && DATA.samples[i][0]<=REGION.r1;i++){
    const s=DATA.samples[i]; const y=s[pc];
    if(y==null){ flush(); continue; }
    const c=colorAt(s[0]); if(c!==col){ flush(); col=c; }
    const x=ovX(s[0]), yy=yOf(y); d += (pen?'L':'M')+x.toFixed(1)+' '+yy.toFixed(1)+' '; pen=true;
  }
  flush();
  p.push(`<text x="${OV_L+4}" y="${yTop+11}" font-size="10" font-weight="bold" fill="#1d2733">${pv} (${UNITS[pv]||''}) — trend</text>`);
  p.push(`<text x="${OV_L-5}" y="${yTop+9}" text-anchor="end" font-size="8" fill="#5b6b7b">${gmx.toFixed(0)}</text>`);
  p.push(`<text x="${OV_L-5}" y="${yBot}" text-anchor="end" font-size="8" fill="#5b6b7b">${gmn.toFixed(0)}</text>`);
  let ly = yBot + OV_GAP;
  const lane = (items, key, color, label) => {
    const yy=ly+OV_LANE/2;
    p.push(`<text x="${OV_L-5}" y="${yy+3}" text-anchor="end" font-size="8" fill="#5b6b7b">${label}</text>`);
    for(const it of items){ if(!inRegion(it[0])) continue; const col = color || (DATA.alarmColors[it[1]]||'#888');
      p.push(`<rect x="${(ovX(it[0])-0.6).toFixed(1)}" y="${ly}" width="1.3" height="${OV_LANE}" fill="${col}"/>`); }
    ly+=OV_LANE;
  };
  if(laneAl){   // alarms as bars (Activated→Deactivated), coloured by type
    const yy=ly+OV_LANE/2;
    p.push(`<text x="${OV_L-5}" y="${yy+3}" text-anchor="end" font-size="8" fill="#5b6b7b">alarms</text>`);
    for(const a of DATA.alarms){ if(a[1]<REGION.r0 || a[0]>REGION.r1) continue;
      const x0=ovX(Math.max(a[0],REGION.r0)), x1=ovX(Math.min(a[1],REGION.r1));
      const col=DATA.alarmColors[a[2]]||'#888';
      p.push(`<rect x="${x0.toFixed(1)}" y="${ly}" width="${Math.max(1.3,x1-x0).toFixed(1)}" height="${OV_LANE}" fill="${col}"/>`); }
    ly+=OV_LANE; }
  if(laneMo) lane(DATA.modes, 'mode', MODE_COLOR, 'modes');
  if(laneEv) lane(DATA.events, 'event', EVENT_COLOR, 'events');
  if(laneBu) lane(DATA.bursts, 'burst', '#c0392b', 'photos');
  const axisY = ly + 14;
  for(let i=0;i<=6;i++){ const t=REGION.r0+regSpan()*i/6, x=ovX(t);
    p.push(`<line x1="${x.toFixed(1)}" y1="${ly+2}" x2="${x.toFixed(1)}" y2="${ly+6}" stroke="#5b6b7b"/>`);
    p.push(`<text x="${x.toFixed(1)}" y="${axisY}" text-anchor="middle" font-size="8" fill="#5b6b7b">${fmtDate(t)} ${fmtHM(t)}</text>`); }
  // draggable window (brush) inside the zoomed region
  const x0=ovX(SEL.t0), x1=ovX(SEL.t1);
  p.push(`<rect id="ov-dim-l" x="${OV_L}" y="${yTop}" width="${Math.max(0,x0-OV_L).toFixed(1)}" height="${OV_CH}" fill="rgba(120,135,150,.18)"/>`);
  p.push(`<rect id="ov-dim-r" x="${x1.toFixed(1)}" y="${yTop}" width="${Math.max(0,OV_R-x1).toFixed(1)}" height="${OV_CH}" fill="rgba(120,135,150,.18)"/>`);
  p.push(`<rect id="ov-brush" x="${x0.toFixed(1)}" y="${yTop}" width="${Math.max(3,x1-x0).toFixed(1)}" height="${OV_CH}" fill="rgba(10,110,189,.10)" stroke="#0a6ebd" stroke-width="1"/>`);
  p.push(`<rect id="ov-hl" x="${(x0-3).toFixed(1)}" y="${yTop}" width="6" height="${OV_CH}" fill="#0a6ebd" fill-opacity="0.55" style="cursor:ew-resize"/>`);
  p.push(`<rect id="ov-hr" x="${(x1-3).toFixed(1)}" y="${yTop}" width="6" height="${OV_CH}" fill="#0a6ebd" fill-opacity="0.55" style="cursor:ew-resize"/>`);
  svg.innerHTML = p.join('');
}
function updateBrushRects(){
  const x0=ovX(SEL.t0), x1=ovX(SEL.t1);
  const set=(id,a,v)=>{ const el=document.getElementById(id); if(el) el.setAttribute(a,v); };
  set('ov-dim-l','width',Math.max(0,x0-OV_L).toFixed(1));
  set('ov-dim-r','x',x1.toFixed(1)); set('ov-dim-r','width',Math.max(0,OV_R-x1).toFixed(1));
  set('ov-brush','x',x0.toFixed(1)); set('ov-brush','width',Math.max(3,x1-x0).toFixed(1));
  set('ov-hl','x',(x0-3).toFixed(1)); set('ov-hr','x',(x1-3).toFixed(1));
}
(function(){
  const svg=document.getElementById('overview');
  let mode=null, anchor=0, grabOff=0;
  function evT(e){ const r=svg.getBoundingClientRect(); const vbX=(e.clientX-r.left)/r.width*VB_W; return ovT(vbX); }
  function evX(e){ const r=svg.getBoundingClientRect(); return (e.clientX-r.left)/r.width*VB_W; }
  svg.addEventListener('pointerdown', e=>{
    const x=evX(e), x0=ovX(SEL.t0), x1=ovX(SEL.t1), w=x1-x0;
    if(w>=16 && Math.abs(x-x0)<=5) mode='l';
    else if(w>=16 && Math.abs(x-x1)<=5) mode='r';
    else if(x>=x0-6 && x<=x1+6){ mode='move'; grabOff=evT(e)-SEL.t0; }
    else { mode='new'; anchor=evT(e); setSel(anchor, anchor+MINW); }
    svg.setPointerCapture(e.pointerId); e.preventDefault();
  });
  svg.addEventListener('pointermove', e=>{
    if(!mode) return; const t=evT(e);
    if(mode==='l') setSel(Math.min(t, SEL.t1-MINW), SEL.t1);
    else if(mode==='r') setSel(SEL.t0, Math.max(t, SEL.t0+MINW));
    else if(mode==='move'){ const w=SEL.t1-SEL.t0; let a=t-grabOff; a=Math.max(REGION.r0, Math.min(a, REGION.r1-w)); setSel(a, a+w); }
    else if(mode==='new'){ if(t>=anchor) setSel(anchor, Math.max(t, anchor+MINW)); else setSel(Math.min(t, anchor-MINW), anchor); }
  });
  const end=e=>{ if(mode){ mode=null; renderDetail(); } };
  svg.addEventListener('pointerup', end);
  svg.addEventListener('pointercancel', end);
})();

// ============================ window (brush) state ============================
// The window is the draggable brush inside REGION; the detail chart shows it.
// setSel only moves the brush (updates its rects) — it does NOT re-zoom the
// overview or touch the region fields.
function setSel(t0, t1, skipDetail){
  t0=Math.max(REGION.r0, Math.min(t0, REGION.r1));
  t1=Math.max(REGION.r0, Math.min(t1, REGION.r1));
  if(t1-t0 < MINW){ t1=Math.min(REGION.r1, t0+MINW); t0=Math.max(REGION.r0, t1-MINW); }
  SEL.t0=t0; SEL.t1=t1;
  updateBrushRects();
  const lbl=document.getElementById('span-lbl');
  lbl.innerHTML = `window <b>${fmtDateTime(t0)}</b> → <b>${fmtDateTime(t1)}</b> · ${fmtDur(t1-t0)}`;
  updatePatientBanner();
  if(!skipDetail) renderDetail();
}
function unitMs(u){ return u==='min' ? 60000 : (u==='day' ? 86400000 : HOUR); }
function setWidthMs(w){                        // centre a window of width w on the current centre
  w=Math.min(Math.max(MINW, w), regSpan()); const c=(SEL.t0+SEL.t1)/2;
  let a=Math.max(REGION.r0, c-w/2); let b=a+w; if(b>REGION.r1){ b=REGION.r1; a=Math.max(REGION.r0, b-w); }
  setSel(a, b);
}
function setWidthHours(h){
  if(h===0){ setSel(REGION.r0, REGION.r1); return; }
  setWidthMs(h*HOUR);
}
function applyCustomWidth(){                    // any window size the user types (min / hours / days)
  const n=parseFloat(document.getElementById('q-width-n').value);
  if(!isFinite(n) || n<=0){ alert('Enter a positive window width.'); return; }
  setWidthMs(n*unitMs(document.getElementById('q-width-u').value));
}
function gotoAlarm(dir){
  if(!DATA.alarms.length) return;
  const c=(SEL.t0+SEL.t1)/2; let target=null;
  if(dir>0){ for(const a of DATA.alarms){ if(a[0] > c+1 && inRegion(a[0])){ target=a[0]; break; } } }
  else { for(let i=DATA.alarms.length-1;i>=0;i--){ if(DATA.alarms[i][0] < c-1 && inRegion(DATA.alarms[i][0])){ target=DATA.alarms[i][0]; break; } } }
  if(target==null) return;
  const w=SEL.t1-SEL.t0; let a=Math.max(REGION.r0, target-w/2), b=a+w;
  if(b>REGION.r1){ b=REGION.r1; a=Math.max(REGION.r0, b-w); }
  setSel(a, b); setTimeout(()=>lockAt(target), 40);
}
// ============================ region (zoom) state ============================
function updateRegionLbl(){
  const h=document.getElementById('ov-h');
  if(h) h.innerHTML = `Overview zoomed to <b>${fmtDateTime(REGION.r0)}</b> → <b>${fmtDateTime(REGION.r1)}</b> — drag the window inside (edges resize)`;
}
function applyRegion(a, b){
  a=Math.max(TMIN, Math.min(a, TMAX)); b=Math.max(TMIN, Math.min(b, TMAX));
  if(b<a){ const t=a; a=b; b=t; }
  if(b-a < MINW){ b=Math.min(TMAX, a+MINW); a=Math.max(TMIN, b-MINW); }
  REGION.r0=a; REGION.r1=b;
  document.getElementById('q-start').value = msToInput(a);
  document.getElementById('q-end').value = msToInput(b);
  updateRegionLbl(); buildOverview();
  setSel(a, b);                 // window starts as the whole region; drag to narrow
}
function resetRegion(){
  REGION.r0=TMIN; REGION.r1=TMAX;
  document.getElementById('q-start').value = msToInput(TMIN);
  document.getElementById('q-end').value = msToInput(TMAX);
  document.getElementById('q-width').value = String(DATA.initialHours);
  updateRegionLbl(); buildOverview();
  setSel(TMIN, Math.min(TMAX, TMIN + DATA.initialHours*HOUR));
}
document.getElementById('q-apply').addEventListener('click', ()=>{
  const a=inputToMs(document.getElementById('q-start').value);
  const b=inputToMs(document.getElementById('q-end').value);
  if(a==null||b==null){ alert('Enter both a start and end date/time.'); return; }
  applyRegion(a, b);
});
document.getElementById('q-reset').addEventListener('click', resetRegion);
document.getElementById('q-width-apply').addEventListener('click', applyCustomWidth);
document.getElementById('q-width-n').addEventListener('keydown', e=>{ if(e.key==='Enter'){ e.preventDefault(); applyCustomWidth(); } });
document.getElementById('al-prev').addEventListener('click', ()=>gotoAlarm(-1));
document.getElementById('al-next').addEventListener('click', ()=>gotoAlarm(1));

// ---- jump the cursor to an exact date & time ----
function gotoTime(t){
  if(t==null || isNaN(t)) return;
  t=Math.max(TMIN, Math.min(t, TMAX));
  // widen the region to the full log if the searched time is outside the zoom
  if(t < REGION.r0 || t > REGION.r1){
    REGION.r0=TMIN; REGION.r1=TMAX;
    document.getElementById('q-start').value=msToInput(TMIN);
    document.getElementById('q-end').value=msToInput(TMAX);
    updateRegionLbl(); buildOverview();
  }
  // move the window (keep its width) to contain t, then lock the cursor there
  const w=Math.min(SEL.t1-SEL.t0, regSpan()); let a=Math.max(REGION.r0, t-w/2), b=a+w;
  if(b>REGION.r1){ b=REGION.r1; a=Math.max(REGION.r0, b-w); }
  setSel(a, b);
  lockAt(t, false, true);          // exact: land on the searched moment, no alarm magnet
}
document.getElementById('g-go').addEventListener('click', ()=>{
  const t=inputToMs(document.getElementById('g-time').value);
  if(t==null){ alert('Enter a date & time to go to.'); return; }
  gotoTime(t);
  // drop focus off the field so the ← / → arrows drive the cursor, not the input
  document.getElementById('g-time').blur(); document.getElementById('g-go').blur();
});
document.getElementById('g-time').addEventListener('keydown', e=>{ if(e.key==='Enter'){ e.preventDefault(); document.getElementById('g-go').click(); } });

// ---- ← / → step the cursor through the samples (slow, faster while held) ----
const ARROW = { hold:0, dir:0 };
function arrowStep(dir){
  if(!DATA.samples.length) return;
  const baseT = (CTRL.cursorT!=null) ? CTRL.cursorT : (SEL.t0+SEL.t1)/2;
  let idx = nearest(DATA.samples, baseT);
  const step = ARROW.hold<4 ? 1 : ARROW.hold<12 ? 4 : ARROW.hold<24 ? 12 : 40;
  idx = Math.max(0, Math.min(DATA.samples.length-1, idx + dir*step));
  let nt = Math.max(REGION.r0, Math.min(DATA.samples[idx][0], REGION.r1));
  if(nt < SEL.t0 || nt > SEL.t1){            // pan the window to keep the cursor in view
    const w=SEL.t1-SEL.t0; let a=Math.max(REGION.r0, nt-w/2), b=a+w;
    if(b>REGION.r1){ b=REGION.r1; a=Math.max(REGION.r0, b-w); }
    setSel(a, b);
  }
  lockAt(nt, true, true);          // exact: step sample-by-sample, no alarm magnet
}
document.addEventListener('keydown', e=>{
  const tag=(e.target.tagName||''); if(tag==='INPUT'||tag==='SELECT'||tag==='TEXTAREA') return;
  if(e.key==='ArrowRight' || e.key==='ArrowLeft'){
    e.preventDefault();
    const dir = e.key==='ArrowRight' ? 1 : -1;
    if(e.repeat && dir===ARROW.dir) ARROW.hold++; else { ARROW.hold=0; ARROW.dir=dir; }
    arrowStep(dir);
  }
});
document.addEventListener('keyup', e=>{ if(e.key==='ArrowRight'||e.key==='ArrowLeft') ARROW.hold=0; });

// ============================ DETAIL chart ============================
function sliceWindow(t0, t1){
  const lo=lowerBound(t0); const out=[];
  for(let i=lo;i<DATA.samples.length && DATA.samples[i][0]<=t1;i++) out.push(DATA.samples[i]);
  const al=DATA.alarms.filter(a=>a[1]>=t0 && a[0]<=t1);   // interval overlaps window
  const bu=DATA.bursts.filter(b=>b[0]>=t0 && b[0]<=t1);
  const mo=DATA.modes.filter(m=>m[0]>=t0 && m[0]<=t1);
  const ev=DATA.events.filter(e=>e[0]>=t0 && e[0]<=t1);
  return { t0, t1, samples:out, alarms:al, bursts:bu, modes:mo, events:ev };
}
function renderDetail(){
  const win = sliceWindow(SEL.t0, SEL.t1);
  const host = document.getElementById('charts');
  const title = `${fmtDateTime(win.t0)} – ${fmtDateTime(win.t1)}`;
  if(!win.samples.length && !win.alarms.length && !win.modes.length && !win.events.length){
    host.innerHTML = `<div class="card"><div class="card-h">${title}</div>`
      +`<p class="muted">No cyclic data or alarms in this window — drag a wider window on the overview above.</p></div>`;
    CTRL.win=win; return;
  }
  const badge = win.samples.length
    ? `<span class="lock-badge" id="lock-d" hidden>🔒 locked</span>`
    : `<span class="alarm-only">alarms only — no cyclic data</span>`;
  host.innerHTML = `<div class="card" id="card-d"><div class="card-h">${title}${badge}</div>`
    + `<div class="chart-row"><svg class="chart" id="chart-d"></svg>`
    + `<div class="readout" id="readout-d"></div></div>`
    + `<div class="ledger" id="ledger-d"></div>`
    + `<details class="statbox" id="stats-d" open></details></div>`;
  CTRL.locked=false;
  buildChart(win);
  buildLedger(win);
  buildStats(win);
}
function buildChart(win){
  const svg = document.getElementById('chart-d');
  const alarmTypes = [...new Set(win.alarms.map(a=>a[2]))]
        .sort((a,b)=>Object.keys(DATA.alarmColors).indexOf(a)-Object.keys(DATA.alarmColors).indexOf(b));
  const laneH = alarmTypes.length ? alarmTypes.length*LANE_ROW + 8 : 0;
  const nV = VARS.length;
  const PH = panelHeights();                    // focused panel tall, the rest shrunk
  const H = TOP + laneH + PH.reduce((a,h)=>a+h+PANEL_GAP, 0) + XAXIS_H;
  svg.setAttribute('viewBox', `0 0 ${VB_W} ${H}`);
  const plotL = ML, plotR = VB_W - MR;
  const dur = Math.max(1, win.t1-win.t0);
  const xOf = t => plotL + (t-win.t0)/dur*(plotR-plotL);
  const ranges = VARS.map(v=>{ const c=COL[v]; let mn=Infinity, mx=-Infinity;
    for(const s of win.samples){ const y=s[c]; if(y==null) continue; if(y<mn)mn=y; if(y>mx)mx=y; }
    if(mn===Infinity){ mn=0; mx=1; } if(mn===mx){ mn-=1; mx+=1; }
    const pad=(mx-mn)*0.08; return [mn-pad, mx+pad]; });
  const tops = []; { let y = TOP + laneH;
    for(let k=0;k<nV;k++){ tops.push(y); y += PH[k] + PANEL_GAP; } }
  const panelTop = k => tops[k];
  const yOf = (k,val) => { const [mn,mx]=ranges[k]; return panelTop(k) + (1-(val-mn)/(mx-mn))*PH[k]; };
  const panelsBottom = panelTop(nV-1) + PH[nV-1];
  let parts = [];
  if(alarmTypes.length){ alarmTypes.forEach((typ,r)=>{ const y = TOP + r*LANE_ROW + LANE_ROW/2;
    const col = DATA.alarmColors[typ] || '#888';
    parts.push(`<text x="${plotL-6}" y="${y+3}" text-anchor="end" font-size="8" fill="${col}">${esc(typ)}</text>`);
    // one bar per active interval (Activated→Deactivated) of this alarm type
    for(const ev of win.alarms){ if(ev[2]!==typ) continue;
      const bx0=Math.max(plotL,xOf(ev[0])), bx1=Math.min(plotR,xOf(ev[1]));
      parts.push(`<rect x="${bx0.toFixed(1)}" y="${y-3}" width="${Math.max(2,bx1-bx0).toFixed(1)}" height="6" fill="${col}" fill-opacity="0.8"><title>${esc(typ)} · ${fmtTime(ev[0])}–${fmtTime(ev[1])} (${fmtDur(ev[1]-ev[0])})</title></rect>`); } }); }
  VARS.forEach((v,k)=>{ const c=COL[v], top=panelTop(k), [mn,mx]=ranges[k];
    parts.push(`<rect x="${plotL}" y="${top}" width="${plotR-plotL}" height="${PH[k]}" fill="${FOCUS===v?'#f7fbff':'none'}" stroke="${FOCUS===v?'#bcdcf5':'#e3e8ee'}"/>`);
    gridVals(mn, mx, PH[k]).forEach(val=>{ const y=yOf(k,val);
      parts.push(`<line x1="${plotL}" y1="${y}" x2="${plotR}" y2="${y}" stroke="#eef2f6"/>`);
      parts.push(`<text x="${plotL-5}" y="${y+3}" text-anchor="end" font-size="8" fill="#5b6b7b">${val.toFixed(PH[k]>=150?1:0)}</text>`); });
    parts.push(`<text x="${plotL+4}" y="${top+11}" font-size="10" font-weight="bold" fill="#1d2733">${v} (${UNITS[v]||''})</text>`);
    // double-click target: focuses this panel (and shrinks the others)
    parts.push(`<rect class="panel-hit" data-v="${esc(v)}" x="${plotL}" y="${top}" width="${plotR-plotL}"`
      + ` height="${PH[k]}" fill="transparent" style="cursor:${FOCUS===v?'zoom-out':'zoom-in'}">`
      + `<title>${esc(v)} — double-click to ${FOCUS===v?'show all graphs again':'focus this graph'}</title></rect>`);
    let d='', pen=false, col=null; const sw=(FOCUS===v?1.8:1.4);
    const flush=()=>{ if(d) parts.push(`<path d="${d}" fill="none" stroke="${col||'#0a6ebd'}" stroke-width="${sw}"/>`); d=''; pen=false; };
    for(const s of win.samples){ const val=s[c]; if(val==null){ flush(); continue; }
      const cc=colorAt(s[0]); if(cc!==col){ flush(); col=cc; }
      const x=xOf(s[0]), y=yOf(k,val); d += (pen?'L':'M')+x.toFixed(1)+' '+y.toFixed(1)+' '; pen=true; }
    flush();
    parts.push(`<line class="hg" id="hg-d-${k}" x1="${plotL}" x2="${plotR}" y1="0" y2="0" stroke="#c0392b" stroke-width="0.8" stroke-dasharray="4 3" visibility="hidden"/>`);
    parts.push(`<circle class="dot" id="dot-d-${k}" r="3" fill="#c0392b" visibility="hidden"/>`); });
  const nTicks=6;
  for(let i=0;i<=nTicks;i++){ const t=win.t0+dur*i/nTicks; const x=xOf(t);
    parts.push(`<line x1="${x}" y1="${panelsBottom}" x2="${x}" y2="${panelsBottom+4}" stroke="#5b6b7b"/>`);
    parts.push(`<text x="${x}" y="${panelsBottom+15}" text-anchor="middle" font-size="8.5" fill="#5b6b7b">${fmtTime(t)}</text>`); }
  for(const b of win.bursts){ const x=xOf(b[0]);
    parts.push(`<line x1="${x}" y1="${TOP}" x2="${x}" y2="${panelsBottom}" stroke="#c0392b" stroke-width="1.2" stroke-dasharray="5 3"/>`);
    parts.push(`<text x="${x}" y="${TOP-1}" text-anchor="middle" font-size="8" font-weight="bold" fill="#c0392b">${fmtHM(b[0])}</text>`);
    parts.push(`<rect class="burst-hit" x="${x-5}" y="${TOP}" width="10" height="${panelsBottom-TOP}" fill="transparent" style="cursor:pointer" data-cid="${b[2]||''}"><title>${b[1]} photos at ${fmtTime(b[0])} — click to see in chat</title></rect>`); }
  // mode changes: purple dashed line at each change; label only where there's room
  let lastMX=-1e9;
  for(const m of win.modes){ const x=xOf(m[0]);
    parts.push(`<line x1="${x}" y1="${TOP}" x2="${x}" y2="${panelsBottom}" stroke="${MODE_COLOR}" stroke-width="1" stroke-dasharray="2 2"><title>${esc(m[1])} at ${fmtTime(m[0])}</title></line>`);
    if(x-lastMX>46){ parts.push(`<text x="${x+2}" y="${panelsBottom-2}" font-size="8" fill="${MODE_COLOR}" font-weight="bold">${esc(m[1])}</text>`); lastMX=x; } }
  // settings/data-change events: teal ticks along the top, plus a tick just under
  // the time axis that lines up with the titles listed below the chart
  for(const e of win.events){ const x=xOf(e[0]);
    parts.push(`<line x1="${x}" y1="${TOP}" x2="${x}" y2="${TOP+6}" stroke="${EVENT_COLOR}" stroke-width="1.2"><title>${esc(e[1])} at ${fmtTime(e[0])}</title></line>`);
    parts.push(`<line x1="${x}" y1="${panelsBottom+18}" x2="${x}" y2="${panelsBottom+25}" stroke="${EVENT_COLOR}" stroke-width="1.2"><title>${esc(e[1])} at ${fmtTime(e[0])}</title></line>`); }
  parts.push(`<line id="ev-pick-d" x1="0" x2="0" y1="${TOP}" y2="${panelsBottom+25}" stroke="${EVENT_COLOR}" stroke-width="1.4" stroke-dasharray="3 2" visibility="hidden"/>`);
  parts.push(`<line class="cx" id="cx-d" x1="0" x2="0" y1="${TOP}" y2="${panelsBottom}" stroke="#111" stroke-width="0.8" visibility="hidden"/>`);
  svg.innerHTML = parts.join('');
  const ro = document.getElementById('readout-d');
  // Readout lists EVERY present variable — deselecting one in the Y-axis picker
  // only hides its diagram, the value is still read here (marked "graph off").
  let rows = `<table><tr><td class="k">Time</td><td class="v" id="ro-d-t">—</td></tr>`;
  ALLVARS.forEach((v,i)=>{ const plotted = VARS.includes(v);
    rows += `<tr><td class="k"${plotted?'':" style='opacity:.55'"}`
      + `${plotted?'':" title='graph hidden — value still shown'"}>${v}${plotted?'':" ·"}</td>`
      + `<td class="v" id="ro-d-v${i}">—</td></tr>`; });
  rows += `<tr><td class="k">Mode</td><td class="v" id="ro-d-mode">—</td></tr>`;
  rows += `<tr><td class="k">Alarms</td><td class="v al" id="ro-d-al">—</td></tr>`;
  rows += `<tr><td class="k">Events</td><td class="v al" id="ro-d-ev">—</td></tr>`;
  rows += `</table><div class="hint" id="hint-d">hover to read · click to lock · double-click a graph to focus</div>`;
  ro.innerHTML = rows;
  CTRL.win=win; CTRL.svg=svg; CTRL.xOf=xOf; CTRL.yOf=yOf; CTRL.H=H;
  CTRL.bands=VARS.map((v,k)=>[panelTop(k), panelTop(k)+PH[k], v]);
  CTRL.alarmT=win.alarms.map(a=>a[0]);   // alarm times, for magnetic cursor snap
  svg.addEventListener('mousemove', e=>{ if(CTRL.locked) return; updateAt(xToTime(e)); });
  svg.addEventListener('mouseleave', ()=>{ if(!CTRL.locked) hideCursor(); });
  svg.addEventListener('click', e=>{
    if(e.target.classList.contains('burst-hit')){ const cid=e.target.getAttribute('data-cid'); if(cid) jumpToChat(cid); return; }
    CTRL.locked=!CTRL.locked;
    const lb=document.getElementById('lock-d'); if(lb) lb.hidden = !CTRL.locked;
    document.getElementById('hint-d').textContent = CTRL.locked ? 'locked · click to unlock' : 'hover to read · click to lock · double-click a graph to focus';
    if(CTRL.locked) updateAt(xToTime(e)); });
  svg.addEventListener('dblclick', e=>{ const v=varAtEvent(e); if(v) setFocus(v); });
}
// which variable panel is under the pointer: normally the panel's own hit rect
// is the target; when the double-click lands on something drawn over it (the
// trace, a marker line, a burst hit-box) fall back to the Y band it sits in.
function varAtEvent(e){
  const hit = e.target && e.target.closest ? e.target.closest('.panel-hit') : null;
  if(hit) return hit.getAttribute('data-v');
  if(!CTRL.svg || !CTRL.bands) return null;
  const r=CTRL.svg.getBoundingClientRect(); if(!r.height) return null;
  const y=(e.clientY-r.top)/r.height*CTRL.H;
  for(const b of CTRL.bands){ if(y>=b[0]-PANEL_GAP/2 && y<=b[1]+PANEL_GAP/2) return b[2]; }
  return null; }

// ============ event / mode titles under the time axis (selectable + clickable) ============
function chipHTML(t, txt, cls){   // date shown beside the time
  return `<span class="chip ${cls}" data-t="${t}" onclick="pickEvent(this)"`
    + ` title="${esc(txt)} at ${fmtDateTime(t)} — click to put the cursor here">`
    + `<b>${fmtDate(t)} ${fmtTime(t)}</b>${esc(txt)}</span>`;
}
function alarmChipHTML(a){       // a = [start, end, type]; shows the full active period
  const col=DATA.alarmColors[a[2]]||'#888';
  const sameDay = fmtDate(a[0])===fmtDate(a[1]);
  const endStr = sameDay ? fmtTime(a[1]) : (fmtDate(a[1])+' '+fmtTime(a[1]));
  return `<span class="chip" data-t="${a[0]}" onclick="pickEvent(this)"`
    + ` style="border-color:${col};color:${col}"`
    + ` title="${esc(a[2])} · activated ${fmtDateTime(a[0])} → deactivated ${fmtDateTime(a[1])} (${fmtDur(a[1]-a[0])}) — click to jump">`
    + `<b style="color:${col}">${fmtDate(a[0])} ${fmtTime(a[0])} → ${endStr}</b>`
    + ` <span style="color:#5b6b7b">${fmtDur(a[1]-a[0])}</span> ${esc(a[2])}</span>`;
}
function buildLedger(win){
  const host=document.getElementById('ledger-d'); if(!host) return;
  let h = `<div class="ledger-h">Alarms in this window — <b>${win.alarms.length}</b>`
    + ` · click one to jump to it</div>`;
  h += `<div class="chips">` + (win.alarms.length
      ? win.alarms.map(a=>alarmChipHTML(a)).join('')
      : `<span class="muted">no alarms in this window</span>`) + `</div>`;
  h += `<div class="ledger-h" style="margin-top:7px">Events — <b>${win.events.length}</b>`
    + ` · click a title to put the cursor at that moment · the text is selectable</div>`;
  h += `<div class="chips">` + (win.events.length
      ? win.events.map(e=>chipHTML(e[0], e[1], 'ev')).join('')
      : `<span class="muted">no logged events in this window</span>`) + `</div>`;
  if(win.modes.length){
    h += `<div class="ledger-h" style="margin-top:7px">Mode changes — <b>${win.modes.length}</b></div>`
      + `<div class="chips">` + win.modes.map(m=>chipHTML(m[0], m[1], 'mode')).join('') + `</div>`;
  }
  host.innerHTML = h;
}
function pickEvent(el){
  document.querySelectorAll('#ledger-d .chip.sel').forEach(c=>c.classList.remove('sel'));
  el.classList.add('sel');
  const t=+el.dataset.t;
  const pk=document.getElementById('ev-pick-d');
  if(pk && CTRL.xOf){ const x=CTRL.xOf(t);
    pk.setAttribute('x1',x); pk.setAttribute('x2',x); pk.setAttribute('visibility','visible'); }
  lockAt(t, true);
}

// ============================ window statistics ============================
function fmtNum(x){ if(x==null || !isFinite(x)) return '—';
  const s = Math.abs(x)>=10 ? x.toFixed(1) : x.toFixed(2);
  return s.replace(/\.0+$/,'').replace(/(\.\d*[1-9])0+$/,'$1'); }
function statsFor(win){
  return VARS.map(v=>{ const c=COL[v]; let mn=Infinity, mx=-Infinity, sum=0, n=0;
    for(const s of win.samples){ const y=s[c]; if(y==null) continue;
      if(y<mn)mn=y; if(y>mx)mx=y; sum+=y; n++; }
    return n ? {v,n,mn,mx,avg:sum/n} : {v,n:0,mn:null,mx:null,avg:null}; });
}
function statsTableHTML(win){
  let h = `<table class="st"><tr><th class="n">Variable</th><th>Min</th><th>Max</th>`
    + `<th>Average</th><th>Samples</th></tr>`;
  for(const r of statsFor(win)){
    h += `<tr><td class="n">${esc(r.v)} <span class="u">${esc(UNITS[r.v]||'')}</span></td>`
      + `<td>${fmtNum(r.mn)}</td><td>${fmtNum(r.mx)}</td><td>${fmtNum(r.avg)}</td>`
      + `<td>${r.n}</td></tr>`;
  }
  h += `</table><div class="stat-foot">${fmtDateTime(win.t0)} → ${fmtDateTime(win.t1)}`
    + ` · ${fmtDur(win.t1-win.t0).trim()} · ${win.samples.length} samples · ${win.alarms.length} alarms`
    + ` · ${win.events.length} events · ${win.modes.length} mode changes`
    + ` · ${win.bursts.length} photo bursts</div>`;
  return h;
}
function buildStats(win){
  const host=document.getElementById('stats-d'); if(!host) return;
  host.innerHTML = `<summary>Statistics for this window — min / max / average per variable</summary>`
    + statsTableHTML(win);
}
function xToTime(e){ const r=CTRL.svg.getBoundingClientRect();
  const vbX=(e.clientX-r.left)/r.width*VB_W; const frac=(vbX-ML)/((VB_W-MR)-ML);
  return CTRL.win.t0 + Math.max(0,Math.min(1,frac))*(CTRL.win.t1-CTRL.win.t0); }
// nearest index in a plain sorted ms array
function nearestMs(arr, t){ let lo=0, hi=arr.length-1; if(hi<0) return -1;
  while(lo<hi){ const m=(lo+hi)>>1; if(arr[m]<t) lo=m+1; else hi=m; }
  if(lo>0 && (t-arr[lo-1])<(arr[lo]-t)) return lo-1; return lo; }
function updateAt(t, exact){ const win=CTRL.win; if(!win) return;
  const hasSamples = win.samples && win.samples.length;
  let anchor, lo, hi;
  if(hasSamples){
    // magnetic alarm snap: if the cursor is within ALARM_SNAP_PX of an alarm,
    // anchor to that alarm so alarms stay reachable even amid dense samples.
    // *exact* (from the time-search / arrow keys) disables the magnet.
    const PW=(VB_W-MR)-ML, TOL=ALARM_SNAP_PX*(win.t1-win.t0)/PW;
    const at=CTRL.alarmT; let snap=false, ai=-1;
    if(!exact && at && at.length){ ai=nearestMs(at,t); if(Math.abs(at[ai]-t)<=TOL){ anchor=at[ai]; snap=true; } }
    const si=nearest(win.samples, snap?anchor:t); if(si<0) return;
    const s=win.samples[si]; if(!snap) anchor=s[0];
    const sx=CTRL.xOf(s[0]);
    // is there actually cyclic data at the anchor? (else values read "—")
    const covered = Math.abs(s[0]-anchor) <= COVER_TOL;
    // values for ALL present variables (readings kept even when the graph is off)
    ALLVARS.forEach((v,i)=>{ const cell=document.getElementById('ro-d-v'+i); if(!cell) return;
      const val=covered? s[COL[v]] : null; cell.textContent = (val==null)? '—' : (val + (UNITS[v]? ' '+UNITS[v] : '')); });
    // crosshair line + dot only for the plotted (diagram) variables (dot on the trace)
    VARS.forEach((v,k)=>{ const val=covered? s[COL[v]] : null; const hg=document.getElementById('hg-d-'+k);
      const dot=document.getElementById('dot-d-'+k);
      if(val==null){ if(hg) hg.setAttribute('visibility','hidden'); if(dot) dot.setAttribute('visibility','hidden'); return; }
      const y=CTRL.yOf(k,val);
      if(hg){ hg.setAttribute('y1',y); hg.setAttribute('y2',y); hg.setAttribute('visibility','visible'); }
      if(dot){ dot.setAttribute('cx',sx); dot.setAttribute('cy',y); dot.setAttribute('visibility','visible'); } });
    if(snap){   // snapped onto an alarm → show just that alarm (its cell among alarms)
      lo = ai>0 ? (at[ai-1]+anchor)/2 : -Infinity;
      hi = ai<at.length-1 ? (anchor+at[ai+1])/2 : Infinity;
    } else {    // on cyclic data → alarms/events attributed to this sample's cell
      lo = si>0 ? (win.samples[si-1][0]+s[0])/2 : -Infinity;
      hi = si<win.samples.length-1 ? (s[0]+win.samples[si+1][0])/2 : Infinity;
    }
  } else {
    // no cyclic data behind the cursor — snap to the nearest ALARM (then event /
    // mode / burst) so alarms recorded with no cyclic log can still be read
    const src = win.alarms.length ? win.alarms : win.events.length ? win.events
              : win.modes.length ? win.modes : win.bursts;
    if(!src || !src.length) return;
    const times = src.map(a=>a[0]);
    const ai=nearestMs(times, t); anchor=times[ai];
    ALLVARS.forEach((v,i)=>{ const cell=document.getElementById('ro-d-v'+i); if(cell) cell.textContent='—'; });
    VARS.forEach((v,k)=>{ const hg=document.getElementById('hg-d-'+k), dot=document.getElementById('dot-d-'+k);
      if(hg) hg.setAttribute('visibility','hidden'); if(dot) dot.setAttribute('visibility','hidden'); });
    lo = ai>0 ? (times[ai-1]+anchor)/2 : -Infinity;
    hi = ai<times.length-1 ? (anchor+times[ai+1])/2 : Infinity;
  }
  const x=CTRL.xOf(anchor);
  const cx=document.getElementById('cx-d'); cx.setAttribute('x1',x); cx.setAttribute('x2',x); cx.setAttribute('visibility','visible');
  document.getElementById('ro-d-t').textContent = fmtTime(anchor);
  CTRL.cursorT = anchor;   // remembered so ← / → arrows can step from here
  const alc=document.getElementById('ro-d-al');
  if(alc){ const active=[];   // alarms ACTIVE at the cursor (interval contains anchor)
    for(const a of win.alarms){ if(a[0]<=anchor && anchor<=a[1] && !active.includes(a[2])) active.push(a[2]); }
    alc.innerHTML = active.length
      ? active.map(t=>`<span style="color:${DATA.alarmColors[t]||'#555'}">${esc(t)}</span>`).join('<br>')
      : '—'; }
  const mc=document.getElementById('ro-d-mode'); if(mc){ mc.textContent = modeAt(anchor) || '—'; }
  const evc=document.getElementById('ro-d-ev');
  if(evc){ const list=[]; for(const e of win.events){ if(e[0]>lo && e[0]<=hi) list.push(e[1]); }
    evc.innerHTML = list.length
      ? list.map(x=>`<span style="color:${EVENT_COLOR}">${esc(x)}</span>`).join('<br>') : '—'; } }
function hideCursor(){ const cx=document.getElementById('cx-d'); if(cx) cx.setAttribute('visibility','hidden');
  VARS.forEach((v,k)=>{ const hg=document.getElementById('hg-d-'+k), dot=document.getElementById('dot-d-'+k);
    if(hg) hg.setAttribute('visibility','hidden'); if(dot) dot.setAttribute('visibility','hidden'); });
  ALLVARS.forEach((v,i)=>{ const cell=document.getElementById('ro-d-v'+i); if(cell) cell.textContent='—'; });
  const t=document.getElementById('ro-d-t'); if(t) t.textContent='—';
  const alc=document.getElementById('ro-d-al'); if(alc) alc.textContent='—';
  const mc=document.getElementById('ro-d-mode'); if(mc) mc.textContent='—';
  const evc=document.getElementById('ro-d-ev'); if(evc) evc.textContent='—'; }
function lockAt(ts, noScroll, exact){ if(!CTRL.win) return; CTRL.locked=true;
  const lb=document.getElementById('lock-d'); if(lb) lb.hidden=false;
  const hint=document.getElementById('hint-d'); if(hint) hint.textContent='locked · click to unlock';
  updateAt(Math.max(CTRL.win.t0, Math.min(ts, CTRL.win.t1)), exact);
  if(noScroll) return;
  const card=document.getElementById('card-d'); if(card) card.scrollIntoView({behavior:'smooth', block:'center'}); }

// ============================ init ============================
// Region defaults to the full log; the window (brush) defaults to the first
// `initialHours`. A ?t=<ms> deep-link centres the window on that moment.
document.getElementById('q-start').value = msToInput(TMIN);
document.getElementById('q-end').value = msToInput(TMAX);
document.getElementById('q-width').value = String(DATA.initialHours);
updateRegionLbl();
renderPatientLegend();
buildOverview();
(function(){
  const p=new URLSearchParams(location.search);
  const t=p.get('t'), from=p.get('from'), to=p.get('to');
  if(from!=null && to!=null && !isNaN(+from) && !isNaN(+to)){
    // a patient segment: zoom the overview to [from,to] and show the whole span
    applyRegion(+from, +to);
  } else if(t!=null && !isNaN(+t)){
    const w=DATA.initialHours*HOUR; let a=Math.max(TMIN,(+t)-w/2), b=a+w;
    if(b>TMAX){ b=TMAX; a=Math.max(TMIN,b-w); }
    setSel(a,b); setTimeout(()=>lockAt(+t), 60);
  } else {
    setSel(TMIN, Math.min(TMAX, TMIN + DATA.initialHours*HOUR));
  }
  updatePatientBanner();
})();
</script>
</body></html>
"""
