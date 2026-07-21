"""Render a CyclicReport to a single self-contained HTML file.

PNGs are embedded as base64 data URIs, so the output is one portable .html file
with no external assets — mirroring how ``wa_report.render_html`` treats the main
report.
"""

from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Optional

from .report import CyclicReport


def _esc(s: str) -> str:
    return html.escape(str(s or ""), quote=True)


def render_cyclic_html(report: CyclicReport, out_path: Optional[Path] = None) -> str:
    """Build a self-contained HTML report (PNGs embedded as data URIs).

    Returns the HTML string; also writes it to *out_path* when given.
    """
    sections = []
    for w in report.windows:
        uri = "data:image/png;base64," + base64.b64encode(w.png).decode("ascii")
        if w.events:
            rows = "".join(
                f"<tr><td>{_esc(e.span_label)}</td><td>{e.count}</td></tr>"
                for e in w.events
            )
            table = (
                "<table class='ev'><thead><tr><th>Time</th>"
                "<th>Photos</th></tr></thead><tbody>" + rows + "</tbody></table>"
            )
        else:
            table = "<p class='muted'>No photo bursts logged in this window.</p>"
        if w.alarm_counts:
            chips = "".join(
                f"<span class='chip'>{_esc(a)} <b>{n}</b></span>"
                for a, n in sorted(w.alarm_counts.items(), key=lambda kv: -kv[1])
            )
            alarm_html = f"<div class='alarms'><span class='muted'>Alarms:</span> {chips}</div>"
        else:
            alarm_html = ""
        sections.append(
            f"<section><h2>{_esc(w.title)}</h2>"
            f"<img src='{uri}' alt='{_esc(w.title)}'>{table}{alarm_html}</section>"
        )

    missing_note = (
        f"<p class='warn'>Variables not found in this CSV and skipped: "
        f"{_esc(', '.join(report.missing_vars))}.</p>"
        if report.missing_vars else ""
    )
    overlap_note = ""
    if report.total_bursts == 0 and report.total_images > 0:
        overlap_note = (
            "<p class='warn'>None of the chat's photo bursts fall inside this "
            "log's time range — the chat and this cyclic CSV don't overlap in "
            "time. Pair the chat with a CSV exported from the same device and "
            "dates to see markers.</p>"
        )

    doc = _CYCLIC_TEMPLATE.format(
        device=_esc(report.device_label),
        vars=_esc(", ".join(report.variables)),
        span=f"{report.data_start.strftime('%d/%m/%Y %H:%M')} → "
             f"{report.data_end.strftime('%d/%m/%Y %H:%M')}",
        n_windows=len(report.windows),
        n_bursts=report.total_bursts,
        n_burst_imgs=report.burst_images,
        n_images=report.total_images,
        n_alarms=report.total_alarms,
        missing_note=missing_note,
        overlap_note=overlap_note,
        sections="\n".join(sections)
        or "<p class='muted'>No cyclic data rows to plot.</p>",
    )
    if out_path is not None:
        Path(out_path).write_text(doc, encoding="utf-8")
    return doc


_CYCLIC_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{device} — Cyclic / Photo Timeline</title>
<style>
  body {{ margin:0; font-family:"Segoe UI",system-ui,Arial,sans-serif;
    color:#1d2733; background:#f4f6f9; font-size:14.5px; }}
  header {{ background:#0a6ebd; color:#fff; padding:16px 22px; }}
  header h1 {{ margin:0; font-size:20px; }}
  header .sub {{ opacity:.9; font-size:13px; margin-top:2px; }}
  main {{ max-width:1100px; margin:0 auto; padding:18px; }}
  .stats {{ display:flex; gap:10px; flex-wrap:wrap; margin:6px 0 16px; }}
  .stat {{ background:#fff; border:1px solid #e3e8ee; border-radius:10px;
    padding:10px 16px; box-shadow:0 1px 3px rgba(20,40,70,.08); }}
  .stat b {{ display:block; font-size:20px; color:#0a6ebd; }}
  .stat span {{ font-size:12px; color:#5b6b7b; }}
  section {{ background:#fff; border:1px solid #e3e8ee; border-radius:10px;
    box-shadow:0 1px 3px rgba(20,40,70,.08); padding:10px 16px 16px;
    margin-bottom:16px; }}
  section h2 {{ font-size:15px; color:#0a6ebd; margin:6px 0 10px; }}
  section img {{ max-width:100%; height:auto; border:1px solid #e3e8ee;
    border-radius:6px; }}
  table.ev {{ border-collapse:collapse; margin-top:10px; font-size:13px; }}
  table.ev th, table.ev td {{ border:1px solid #e3e8ee; padding:3px 12px;
    text-align:left; }}
  table.ev th {{ background:#f4f6f9; color:#5b6b7b; }}
  .muted {{ color:#5b6b7b; font-style:italic; }}
  .alarms {{ margin-top:10px; display:flex; flex-wrap:wrap; gap:6px;
    align-items:center; }}
  .chip {{ font-size:12px; background:#f4f6f9; border:1px solid #e3e8ee;
    border-radius:14px; padding:2px 10px; }}
  .chip b {{ color:#c0392b; }}
  .warn {{ color:#8a5b00; background:#fff6e5; border:1px solid #ffe2a8;
    border-radius:8px; padding:8px 12px; }}
</style></head><body>
<header>
  <h1>{device}</h1>
  <div class="sub">Cyclic ventilator log ⟷ WhatsApp photo timeline · Y-axis: {vars}</div>
</header>
<main>
  <div class="stats">
    <div class="stat"><b>{n_windows}</b><span>12-hour graphs</span></div>
    <div class="stat"><b>{n_bursts}</b><span>Photo bursts mapped</span></div>
    <div class="stat"><b>{n_burst_imgs}</b><span>Images in bursts</span></div>
    <div class="stat"><b>{n_images}</b><span>Images in chat</span></div>
    <div class="stat"><b>{n_alarms}</b><span>Alarms in log</span></div>
  </div>
  <p class="muted">Log span: {span}</p>
  {missing_note}
  {overlap_note}
  {sections}
</main>
</body></html>
"""
