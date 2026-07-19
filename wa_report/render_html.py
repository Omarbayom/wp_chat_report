"""Render a Report to a single self-contained, interactive HTML file.

The output is one .html file (images embedded as base64 data URIs) that can be
opened in any browser with no server and no external assets. It lets the reader:

  * search the whole chat as they type,
  * filter by day, by hour, and by sender,
  * jump to any day from a sidebar,
  * click any photo to open it full-size in a lightbox.

Everything is rendered up front into the DOM; filtering is done client-side by
toggling ``hidden`` on message rows, so it stays instant even for long chats.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from . import media
from .grouping import hm, transcript
from .report import Report


def _esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


# A small, stable palette; each distinct speaker gets one colour (by index).
_AVATAR_COLORS = [
    "#0a6ebd", "#2e8b57", "#b5651d", "#8e44ad", "#c0392b",
    "#16a085", "#d35400", "#2c3e50", "#7f8c8d", "#c2185b",
]


def render_html(report: Report, out_path: Path, cache: media.MediaCache) -> Path:
    """Build the interactive report at *out_path* and return it."""
    # --- Assign a stable colour to each speaker across the whole report. ---
    speakers: list[str] = []
    for c in report.cycles:
        for it in transcript(c):
            if it.speaker and it.speaker not in speakers:
                speakers.append(it.speaker)
    speaker_color = {
        s: _AVATAR_COLORS[i % len(_AVATAR_COLORS)] for i, s in enumerate(speakers)
    }

    days: list[str] = []          # sorted "YYYY-MM-DD" keys, for the day filter/sidebar
    day_labels: dict[str, str] = {}
    hours_present: set[str] = set()
    sections: list[str] = []      # rendered HTML for each cycle section
    total_msgs = 0
    total_imgs = 0
    missing_total = 0

    for ci, c in enumerate(report.cycles):
        items = transcript(c)
        rows: list[str] = []
        missing = 0

        for it in items:
            day_key = it.dt.strftime("%Y-%m-%d")
            hour_key = it.dt.strftime("%H")
            hours_present.add(hour_key)
            if day_key not in day_labels:
                day_labels[day_key] = it.dt.strftime("%d/%m/%Y")
                days.append(day_key)

            time_str = _esc(hm(it.dt))
            speaker = it.speaker or "System"
            color = speaker_color.get(speaker, "#7f8c8d")
            # Text used for the free-text search (speaker + body, lower-cased).
            search_blob = _esc((speaker + " " + (it.text or "")).lower())

            common_attrs = (
                f'class="msg" data-day="{day_key}" data-hour="{hour_key}" '
                f'data-speaker="{_esc(speaker)}" data-search="{search_blob}"'
            )

            if it.kind == "image":
                p = media.resolve(it.name, it.source_dir)
                uri = cache.data_uri(p) if p is not None else None
                if uri is None:
                    missing += 1
                    continue
                total_imgs += 1
                body = (
                    f'<img class="photo" src="{uri}" loading="lazy" '
                    f'alt="{_esc(it.name)}" '
                    f'onclick="openLightbox(this.src)">'
                )
            elif it.kind == "media":
                body = f'<span class="media-note">{_esc(it.text)}</span>'
            else:
                body = f'<span class="text" dir="auto">{_esc(it.text)}</span>'

            total_msgs += 1
            rows.append(
                f'<div {common_attrs}>'
                f'<div class="avatar" style="background:{color}">{_esc(_initials(speaker))}</div>'
                f'<div class="bubble">'
                f'<div class="meta"><span class="speaker" style="color:{color}">{_esc(speaker)}</span>'
                f'<span class="time">{time_str}</span></div>'
                f'<div class="content">{body}</div>'
                f'</div></div>'
            )

        missing_total += missing
        if missing:
            rows.append(
                f'<div class="msg system-note" data-day="" data-hour="" '
                f'data-speaker="" data-search="">'
                f'{missing} image(s) referenced but not found in the export folder.</div>'
            )

        if not rows:
            body_html = '<div class="empty">All messages in this window were deleted.</div>'
        else:
            body_html = "\n".join(rows)

        sections.append(
            f'<section class="cycle" id="cycle-{ci}">'
            f'<h2 class="cycle-title">{_esc(c.title)}</h2>'
            f'{body_html}'
            f'</section>'
        )

    hours_sorted = sorted(hours_present)

    # --- Sidebar day links ---
    sidebar_links = "\n".join(
        f'<a href="#" class="day-link" data-day="{d}" '
        f'onclick="jumpToDay(event, \'{d}\')">{_esc(day_labels[d])}</a>'
        for d in days
    )

    # --- Filter dropdown options ---
    day_options = '<option value="">All days</option>' + "".join(
        f'<option value="{d}">{_esc(day_labels[d])}</option>' for d in days
    )
    hour_options = '<option value="">All hours</option>' + "".join(
        f'<option value="{h}">{h}:00 – {int(h) + 1:02d}:00</option>' for h in hours_sorted
    )
    speaker_options = '<option value="">All senders</option>' + "".join(
        f'<option value="{_esc(s)}">{_esc(s)}</option>' for s in speakers
    )

    profile_rows = [
        ("Device", report.patient),
        ("Date In", report.date_in_str),
        ("Date Out", report.date_out_str),
        ("Duration", f"{report.duration_days} day(s)"),
        ("Group members", ", ".join(report.members) or "-"),
    ]
    profile_html = "".join(
        f'<div class="pf-row"><span class="pf-k">{_esc(k)}</span>'
        f'<span class="pf-v">{_esc(str(v))}</span></div>'
        for k, v in profile_rows
    )

    stats_json = json.dumps({
        "days": len(days),
        "cycles": len(report.cycles),
        "messages": total_msgs,
        "photos": total_imgs,
    })

    doc = _PAGE_TEMPLATE.format(
        title=_esc(report.hospital) or "WhatsApp Report",
        hospital=_esc(report.hospital) or "—",
        profile=profile_html,
        sidebar_links=sidebar_links or '<span class="muted">No days</span>',
        day_options=day_options,
        hour_options=hour_options,
        speaker_options=speaker_options,
        stats_days=len(days),
        stats_msgs=total_msgs,
        stats_imgs=total_imgs,
        stats_json=stats_json,
        sections="\n".join(sections),
    )
    out_path.write_text(doc, encoding="utf-8")
    return out_path


_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Ventilation Report</title>
<style>
  :root {{
    --accent:#0a6ebd; --bg:#f4f6f9; --panel:#ffffff; --line:#e3e8ee;
    --text:#1d2733; --muted:#5b6b7b; --shadow:0 1px 3px rgba(20,40,70,.08);
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:"Segoe UI",system-ui,Arial,sans-serif;
    color:var(--text); background:var(--bg); font-size:14.5px; line-height:1.45; }}
  a {{ color:var(--accent); text-decoration:none; }}
  .muted {{ color:var(--muted); }}

  header.top {{ background:var(--accent); color:#fff; padding:16px 22px; }}
  header.top h1 {{ margin:0; font-size:20px; font-weight:650; }}
  header.top .sub {{ opacity:.9; font-size:13px; margin-top:2px; }}

  .layout {{ display:flex; align-items:flex-start; gap:18px;
    max-width:1180px; margin:0 auto; padding:18px; }}
  aside {{ position:sticky; top:18px; width:220px; flex:0 0 220px;
    background:var(--panel); border:1px solid var(--line); border-radius:10px;
    box-shadow:var(--shadow); padding:12px; max-height:calc(100vh - 40px);
    overflow:auto; }}
  aside h3 {{ margin:4px 4px 8px; font-size:12px; letter-spacing:.05em;
    text-transform:uppercase; color:var(--muted); }}
  .pf-row {{ display:flex; justify-content:space-between; gap:8px; padding:4px 4px;
    border-bottom:1px dashed var(--line); font-size:13px; }}
  .pf-row:last-child {{ border-bottom:0; }}
  .pf-k {{ color:var(--muted); }}
  .pf-v {{ font-weight:600; text-align:right; }}
  .day-link {{ display:block; padding:5px 8px; border-radius:6px; font-size:13px;
    color:var(--text); }}
  .day-link:hover {{ background:var(--bg); }}
  .day-link.active {{ background:var(--accent); color:#fff; }}

  main {{ flex:1 1 auto; min-width:0; }}

  .toolbar {{ position:sticky; top:0; z-index:20; background:var(--panel);
    border:1px solid var(--line); border-radius:10px; box-shadow:var(--shadow);
    padding:12px; display:flex; flex-wrap:wrap; gap:10px; align-items:center;
    margin-bottom:16px; }}
  .toolbar input, .toolbar select {{ font:inherit; padding:8px 10px;
    border:1px solid var(--line); border-radius:8px; background:#fff; color:var(--text); }}
  .toolbar input.search {{ flex:1 1 260px; min-width:180px; }}
  .toolbar button {{ font:inherit; padding:8px 12px; border:1px solid var(--line);
    background:#fff; border-radius:8px; cursor:pointer; color:var(--muted); }}
  .toolbar button:hover {{ background:var(--bg); }}
  .count {{ font-size:12.5px; color:var(--muted); margin-left:auto; white-space:nowrap; }}

  .stats {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:16px; }}
  .stat {{ background:var(--panel); border:1px solid var(--line); border-radius:10px;
    box-shadow:var(--shadow); padding:10px 16px; }}
  .stat b {{ display:block; font-size:20px; color:var(--accent); }}
  .stat span {{ font-size:12px; color:var(--muted); }}

  section.cycle {{ background:var(--panel); border:1px solid var(--line);
    border-radius:10px; box-shadow:var(--shadow); padding:6px 16px 14px;
    margin-bottom:16px; }}
  .cycle-title {{ position:sticky; top:64px; background:var(--panel); z-index:5;
    margin:0 -16px 8px; padding:10px 16px; font-size:15px; color:var(--accent);
    border-bottom:1px solid var(--line); }}

  .msg {{ display:flex; gap:10px; padding:6px 2px; align-items:flex-start; }}
  .avatar {{ flex:0 0 30px; width:30px; height:30px; border-radius:50%; color:#fff;
    display:flex; align-items:center; justify-content:center; font-size:11px;
    font-weight:700; margin-top:2px; }}
  .bubble {{ flex:1 1 auto; min-width:0; }}
  .meta {{ display:flex; gap:8px; align-items:baseline; }}
  .speaker {{ font-weight:600; font-size:13px; }}
  .time {{ font-size:11px; color:var(--muted); }}
  .content {{ margin-top:1px; }}
  .text {{ white-space:pre-wrap; word-wrap:break-word; }}
  .media-note {{ color:var(--muted); font-style:italic; font-size:13px; }}
  .photo {{ max-width:230px; max-height:230px; border-radius:8px; cursor:zoom-in;
    border:1px solid var(--line); display:block; margin-top:3px; }}
  .empty, .system-note {{ color:var(--muted); font-style:italic; font-size:13px;
    padding:6px 2px; }}
  .no-results {{ text-align:center; color:var(--muted); padding:40px; display:none; }}

  /* Lightbox */
  #lightbox {{ display:none; position:fixed; inset:0; z-index:100;
    background:rgba(10,20,35,.9); align-items:center; justify-content:center;
    overflow:hidden; touch-action:none; cursor:zoom-out; }}
  #lightbox img {{ max-width:94vw; max-height:94vh; border-radius:6px;
    box-shadow:0 8px 40px rgba(0,0,0,.5); cursor:zoom-in; user-select:none;
    -webkit-user-drag:none; transform-origin:center center; will-change:transform;
    transition:transform .12s ease-out; }}
  #lightbox img.zoomed {{ cursor:grab; }}
  #lightbox img.grabbing {{ cursor:grabbing; transition:none; }}
  #lb-controls {{ position:fixed; top:14px; right:16px; display:flex; gap:8px; z-index:101; }}
  #lb-controls button {{ width:38px; height:38px; border-radius:8px; border:0;
    background:rgba(255,255,255,.16); color:#fff; font-size:18px; cursor:pointer;
    display:flex; align-items:center; justify-content:center; line-height:1; }}
  #lb-controls button:hover {{ background:rgba(255,255,255,.3); }}
  #lb-hint {{ position:fixed; bottom:14px; left:50%; transform:translateX(-50%);
    color:rgba(255,255,255,.8); font-size:12px; z-index:101; pointer-events:none;
    background:rgba(10,20,35,.5); padding:5px 12px; border-radius:20px; white-space:nowrap; }}

  @media (max-width:820px) {{
    .layout {{ flex-direction:column; }}
    aside {{ position:static; width:100%; flex:1 1 auto; max-height:none; }}
    .cycle-title {{ top:0; }}
  }}
</style>
</head>
<body>
<header class="top">
  <h1>{hospital}</h1>
  <div class="sub">Mechanical Ventilation Monitoring Report</div>
</header>

<div class="layout">
  <aside>
    <h3>Details</h3>
    {profile}
    <h3 style="margin-top:14px">Jump to day</h3>
    {sidebar_links}
  </aside>

  <main>
    <div class="stats">
      <div class="stat"><b>{stats_days}</b><span>Days</span></div>
      <div class="stat"><b>{stats_msgs}</b><span>Messages</span></div>
      <div class="stat"><b>{stats_imgs}</b><span>Photos</span></div>
    </div>

    <div class="toolbar">
      <input class="search" id="q" type="search" placeholder="Search messages…"
        oninput="applyFilters()">
      <select id="fday" onchange="onDaySelect()">{day_options}</select>
      <select id="fhour" onchange="applyFilters()">{hour_options}</select>
      <select id="fspeaker" onchange="applyFilters()">{speaker_options}</select>
      <button type="button" onclick="clearFilters()">Clear</button>
      <span class="count" id="count"></span>
    </div>

    <div class="no-results" id="noResults">No messages match your filters.</div>

    {sections}
  </main>
</div>

<div id="lightbox">
  <div id="lb-controls">
    <button type="button" title="Zoom out (-)" onclick="lbZoom(1/1.4)">&minus;</button>
    <button type="button" title="Zoom in (+)" onclick="lbZoom(1.4)">+</button>
    <button type="button" title="Reset (0)" onclick="lbReset()">&#8635;</button>
    <button type="button" title="Close (Esc)" onclick="closeLightbox()">&times;</button>
  </div>
  <img id="lightbox-img" alt="" draggable="false">
  <div id="lb-hint">Scroll or click to zoom &middot; drag to pan &middot; Esc or click outside to close</div>
</div>

<script>
  const STATS = {stats_json};
  const msgs = Array.from(document.querySelectorAll('.msg'));
  const sections = Array.from(document.querySelectorAll('section.cycle'));

  // ---- Zoomable / pannable image lightbox ----
  const lb = document.getElementById('lightbox');
  const lbImg = document.getElementById('lightbox-img');
  const LB_MIN = 1, LB_MAX = 8;
  let lbScale = 1, lbTx = 0, lbTy = 0;

  function lbClamp(v, lo, hi) {{ return Math.min(hi, Math.max(lo, v)); }}

  function lbApply() {{
    lbImg.style.transform =
      'translate(' + lbTx + 'px,' + lbTy + 'px) scale(' + lbScale + ')';
    lbImg.classList.toggle('zoomed', lbScale > 1.001);
  }}

  function lbReset() {{ lbScale = 1; lbTx = 0; lbTy = 0; lbApply(); }}

  function openLightbox(src) {{
    lbImg.src = src;
    lbReset();
    lb.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }}

  function closeLightbox() {{
    lb.style.display = 'none';
    document.body.style.overflow = '';
  }}

  // Zoom by *factor*, keeping the point (clientX,clientY) fixed on screen.
  // With no point given, zoom about the image centre.
  function lbZoomAt(factor, clientX, clientY) {{
    const rect = lbImg.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    if (clientX === undefined) {{ clientX = cx; clientY = cy; }}
    const newScale = lbClamp(lbScale * factor, LB_MIN, LB_MAX);
    const real = newScale / lbScale;
    lbTx += (clientX - cx) * (1 - real);
    lbTy += (clientY - cy) * (1 - real);
    lbScale = newScale;
    if (lbScale <= 1.001) {{ lbScale = 1; lbTx = 0; lbTy = 0; }}
    lbApply();
  }}

  function lbZoom(factor) {{ lbZoomAt(factor); }}

  // Mouse wheel zooms toward the cursor.
  lb.addEventListener('wheel', e => {{
    e.preventDefault();
    lbZoomAt(e.deltaY < 0 ? 1.2 : 1 / 1.2, e.clientX, e.clientY);
  }}, {{passive:false}});

  // Click toggles zoom; drag pans when zoomed.
  let lbDown = false, lbMoved = false, lbSX = 0, lbSY = 0, lbOX = 0, lbOY = 0;

  lbImg.addEventListener('pointerdown', e => {{
    e.preventDefault();
    lbDown = true; lbMoved = false;
    lbSX = e.clientX; lbSY = e.clientY; lbOX = lbTx; lbOY = lbTy;
    lbImg.setPointerCapture(e.pointerId);
    lbImg.classList.add('grabbing');
  }});

  lbImg.addEventListener('pointermove', e => {{
    if (!lbDown) return;
    const dx = e.clientX - lbSX, dy = e.clientY - lbSY;
    if (Math.abs(dx) + Math.abs(dy) > 4) lbMoved = true;
    if (lbScale > 1) {{ lbTx = lbOX + dx; lbTy = lbOY + dy; lbApply(); }}
  }});

  lbImg.addEventListener('pointerup', e => {{
    lbImg.classList.remove('grabbing');
    if (!lbDown) return;
    lbDown = false;
    if (!lbMoved) {{  // a real click, not a drag
      if (lbScale > 1.001) lbReset();
      else lbZoomAt(2.5, e.clientX, e.clientY);
    }}
  }});

  // Clicking the dark area outside the image closes the viewer.
  lb.addEventListener('click', e => {{ if (e.target === lb) closeLightbox(); }});

  function onDaySelect() {{
    // Selecting a day from the dropdown also highlights the sidebar link.
    const day = document.getElementById('fday').value;
    document.querySelectorAll('.day-link').forEach(a =>
      a.classList.toggle('active', a.dataset.day === day && day !== ''));
    applyFilters();
  }}

  function jumpToDay(ev, day) {{
    ev.preventDefault();
    document.getElementById('fday').value = day;
    onDaySelect();
    // Scroll to the first visible message of that day.
    const first = msgs.find(m => m.dataset.day === day && !m.hidden);
    if (first) first.scrollIntoView({{behavior:'smooth', block:'start'}});
  }}

  function clearFilters() {{
    document.getElementById('q').value = '';
    document.getElementById('fday').value = '';
    document.getElementById('fhour').value = '';
    document.getElementById('fspeaker').value = '';
    document.querySelectorAll('.day-link').forEach(a => a.classList.remove('active'));
    applyFilters();
  }}

  function applyFilters() {{
    const q = document.getElementById('q').value.trim().toLowerCase();
    const day = document.getElementById('fday').value;
    const hour = document.getElementById('fhour').value;
    const speaker = document.getElementById('fspeaker').value;
    let shown = 0;

    for (const m of msgs) {{
      // System notes (missing-image markers) only show when unfiltered.
      const isNote = m.classList.contains('system-note');
      let ok = true;
      if (isNote) {{
        ok = !q && !day && !hour && !speaker;
      }} else {{
        if (day && m.dataset.day !== day) ok = false;
        if (ok && hour && m.dataset.hour !== hour) ok = false;
        if (ok && speaker && m.dataset.speaker !== speaker) ok = false;
        if (ok && q && !m.dataset.search.includes(q)) ok = false;
      }}
      m.hidden = !ok;
      if (ok && !isNote) shown++;
    }}

    // Hide a whole section (and its sticky title) when nothing in it shows.
    for (const sec of sections) {{
      const anyVisible = Array.from(sec.querySelectorAll('.msg'))
        .some(m => !m.hidden);
      sec.hidden = !anyVisible;
    }}

    document.getElementById('noResults').style.display = shown ? 'none' : 'block';
    const filtered = (q || day || hour || speaker);
    document.getElementById('count').textContent =
      filtered ? (shown + ' of ' + STATS.messages + ' messages')
               : (STATS.messages + ' messages · ' + STATS.photos + ' photos');
  }}

  document.addEventListener('keydown', e => {{
    if (lb.style.display !== 'flex') return;
    if (e.key === 'Escape') closeLightbox();
    else if (e.key === '+' || e.key === '=') lbZoom(1.4);
    else if (e.key === '-' || e.key === '_') lbZoom(1 / 1.4);
    else if (e.key === '0') lbReset();
  }});

  applyFilters();
</script>
</body>
</html>
"""
