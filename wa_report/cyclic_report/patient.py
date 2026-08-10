"""Patient identity from the CyclicData preamble + its HTML views.

Real device *CyclicData* exports begin with a small key/value **preamble** naming
the patient, before the time-series header row (the one that contains
``DateTime``):

    "Patient ID",6
    "Patient Name",Vent
    "Patient Age",0
    "Patient Height",170
    "Patient Weight",63.58

``load_patient_info`` reads those rows; ``banner_html`` renders a compact bar for
the top of the chart pages; ``build_patient_html`` renders a dedicated, standalone
"Patient" page that cross-links to the other pages in its own browser tab.
"""

from __future__ import annotations

import csv as _csv
import html as _html
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from .csv_io import _to_text, parse_datetimes, read_ventilator_csv

# The fields we surface, in display order.
PATIENT_FIELDS = ["Patient ID", "Patient Name", "Patient Age",
                  "Patient Height", "Patient Weight"]
_DELIMS = [",", ";", "\t", "|"]

Pairs = List[Tuple[str, str]]


def _esc(s) -> str:
    return _html.escape(str(s if s is not None else ""), quote=True)


def _latest_time(source):
    """The latest ``DateTime`` in one cyclic source, or ``None`` if unreadable."""
    try:
        d = read_ventilator_csv(source, "DateTime")
        if "DateTime" not in d.columns:
            return None
        t = parse_datetimes(d["DateTime"], dayfirst=True).max()
        return None if t is None or t != t else t   # drop NaT
    except Exception:
        return None


def load_patient_info(source) -> Pairs:
    """Read the CyclicData preamble and return the patient fields present, as
    ordered ``(label, value)`` pairs. Empty list when the source can't be read or
    carries no patient rows (so callers can treat "no patient info" uniformly).

    When *source* is a **list** of cyclic files, the preamble of the file whose
    data ends **latest** is returned — that is the current patient (matching how
    the roster picks the last time-segment)."""
    if isinstance(source, (list, tuple)):
        best, best_t = [], None
        for s in source:
            info = load_patient_info(s)
            if not info:
                continue
            t = _latest_time(s)
            if not best or (t is not None and (best_t is None or t > best_t)):
                best, best_t = info, t
        return best
    try:
        text = _to_text(source)
    except Exception:
        return []
    lines = text.splitlines()
    # The preamble is everything above the row that holds the real 'DateTime'
    # header; the same key the cyclic reader uses to locate the table.
    header_idx = len(lines)
    for i, ln in enumerate(lines):
        if "datetime" in ln.lower():
            header_idx = i
            break

    want = {f.lower(): f for f in PATIENT_FIELDS}
    found: dict[str, str] = {}
    for ln in lines[:header_idx]:
        if not ln.strip():
            continue
        delim = max(_DELIMS, key=ln.count)
        if ln.count(delim) == 0:
            delim = ","
        try:
            row = next(_csv.reader([ln], delimiter=delim))
        except Exception:
            continue
        if len(row) < 2:
            continue
        key = row[0].strip().strip('"').strip().lower()
        if key in want and want[key] not in found:
            val = row[1].strip().strip('"').strip()
            if val != "":
                found[want[key]] = val
    return [(f, found[f]) for f in PATIENT_FIELDS if f in found]


def with_fallback_id(patient: Pairs, fallback: str = "") -> Pairs:
    """If the Patient ID is blank/missing, substitute *fallback* (e.g. ``"b1"``).

    A no-op when *fallback* is empty or an ID is already present, so callers that
    don't supply a fallback keep the raw parsed value. Only fills the ID in — it
    won't invent a whole patient record from nothing (an empty *patient* with a
    fallback still yields just the one ID row, which the caller can choose to
    show or ignore)."""
    if not fallback:
        return patient
    d = dict(patient)
    if (d.get("Patient ID") or "").strip():
        return patient
    d["Patient ID"] = fallback
    return [(f, d[f]) for f in PATIENT_FIELDS if f in d]


def patient_title(patient: Pairs) -> str:
    """A concise ``Name (ID n)`` label, for auto-filling a blank report title."""
    d = dict(patient)
    name = (d.get("Patient Name") or "").strip()
    pid = (d.get("Patient ID") or "").strip()
    if name and pid:
        return f"{name} (ID {pid})"
    if name:
        return name
    if pid:
        return f"Patient {pid}"
    return ""


def banner_html(patient: Pairs, link_href: Optional[str] = "patient.html",
                margin: str = "12px 20px 0", note: str = "",
                link_text: str = "Details ↗", color: str = "") -> str:
    """Compact, self-contained (inline-styled) patient bar for the top of a page.

    Returns ``""`` when there is no patient info. *note* (e.g. "1 of 3 patients")
    is shown after the fields; when *link_href* is given, a link (labelled
    *link_text*) opens the patient page in the ``wa_patient`` tab. *color* (the
    patient's trend colour) draws a small swatch before the label.
    """
    if not patient:
        return ""
    swatch = (f"<span style='display:inline-block;width:10px;height:10px;border-radius:50%;"
              f"background:{_esc(color)};margin-right:2px;vertical-align:-1px'></span>") if color else ""
    items = "".join(
        f"<span style='white-space:nowrap'>"
        f"<span style='color:#5b6b7b'>{_esc(k.replace('Patient ', ''))}</span> "
        f"<b style='color:#1d2733'>{_esc(v)}</b></span>"
        for k, v in patient
    )
    note_html = (f"<span style='color:#8a5b00;background:#fff6e5;border:1px solid #ffe2a8;"
                 f"border-radius:12px;padding:1px 9px'>{_esc(note)}</span>") if note else ""
    link = (f"<a href='{_esc(link_href)}' target='wa_patient' "
            f"style='margin-left:auto;color:#0a6ebd;text-decoration:none;font-weight:600'>"
            f"{_esc(link_text)}</a>") if link_href else ""
    return (
        f"<div style='display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center;"
        f"background:#eef6fd;border:1px solid #cfe4f7;border-radius:10px;"
        f"padding:8px 14px;margin:{margin};font-size:13px'>"
        f"<span style='font-weight:700;color:#0a6ebd;letter-spacing:.03em'>{swatch}PATIENT</span>"
        f"{items}{note_html}{link}</div>"
    )


def build_patient_html(patient: Pairs, device_label: str = "",
                       links: Optional[dict] = None,
                       out_path: Optional[Path] = None) -> str:
    """A dedicated, standalone **Patient** page (opens in the ``wa_patient`` tab).

    *links* maps a button label to an ``(href, target)`` pair for the header nav
    (e.g. ``{"Windowed view": ("windows.html", "wa_windows")}``)."""
    links = links or {}
    title = device_label or patient_title(patient) or "Patient"
    if patient:
        rows = "".join(
            f"<tr><td class='k'>{_esc(k)}</td><td class='v'>{_esc(v)}</td></tr>"
            for k, v in patient
        )
        body = f"<table class='pt'>{rows}</table>"
    else:
        body = ("<p class='muted'>No patient information was found in this cyclic "
                "CSV (the export has no patient preamble).</p>")
    nav = "".join(
        f"<a class='other' href='{_esc(h)}' target='{_esc(t)}'>{_esc(lbl)} ↗</a>"
        for lbl, (h, t) in links.items()
    )
    doc = (_PATIENT_PAGE
           .replace("__TITLE__", _esc(title))
           .replace("__DEVICE__", _esc(title))
           .replace("__NAV__", nav)
           .replace("__BODY__", body))
    if out_path is not None:
        Path(out_path).write_text(doc, encoding="utf-8")
    return doc


def _fmt_ms(ms) -> str:
    """ms-since-1970 (wall-clock) → ``dd/mm/YYYY HH:MM``."""
    d = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=int(ms))
    return d.strftime("%d/%m/%Y %H:%M")


def build_patients_html(roster: List[dict], device_label: str = "",
                        links: Optional[dict] = None, chart_href: str = "charts.html",
                        out_path: Optional[Path] = None) -> str:
    """The **Patients** page for a reused device: one card per patient segment.

    *roster* is the list from ``roster.assemble_roster`` (each item has ``info``,
    ``label``, ``t0``/``t1``, ``current``, ``n_samples``, ``n_alarms``). Every card
    links into *chart_href* zoomed to that patient's time range
    (``?from=<ms>&to=<ms>``). *links* maps a label to ``(href, target)`` for the
    header nav."""
    links = links or {}
    title = device_label or "Patients"
    nav = "".join(
        f"<a class='other' href='{_esc(h)}' target='{_esc(t)}'>{_esc(lbl)} ↗</a>"
        for lbl, (h, t) in links.items()
    )
    if not roster:
        cards = ("<p class='muted'>No patient information was found in this cyclic "
                 "CSV.</p>")
    else:
        cards = "".join(_patient_card(seg, chart_href) for seg in roster)
    intro = (f"<p class='intro'>{len(roster)} patient(s) on this device"
             " — split at each <b>Add New Patient</b> handover. Open a patient to"
             " see the charts zoomed to their time on the device.</p>"
             if len(roster) > 1 else "")
    doc = (_PATIENTS_PAGE
           .replace("__TITLE__", _esc(title))
           .replace("__DEVICE__", _esc(title))
           .replace("__NAV__", nav)
           .replace("__INTRO__", intro)
           .replace("__CARDS__", cards))
    if out_path is not None:
        Path(out_path).write_text(doc, encoding="utf-8")
    return doc


def _patient_card(seg: dict, chart_href: str) -> str:
    info = seg.get("info") or []
    rows = "".join(
        f"<tr><td class='k'>{_esc(k)}</td><td class='v'>{_esc(v)}</td></tr>"
        for k, v in info
    ) or "<tr><td class='k muted' colspan='2'>no details recorded</td></tr>"
    cur = ("<span class='cur'>current</span>" if seg.get("current") else "")
    period = f"{_fmt_ms(seg['t0'])} → {_fmt_ms(seg['t1'])}"
    href = f"{chart_href}?from={int(seg['t0'])}&to={int(seg['t1'])}"
    color = seg.get("color") or "#0a6ebd"
    dot = (f"<span style='display:inline-block;width:11px;height:11px;border-radius:50%;"
           f"background:{_esc(color)}'></span>")
    return (
        f"<div class='pcard{' pcur' if seg.get('current') else ''}' "
        f"style='border-top:4px solid {_esc(color)}'>"
        f"<div class='pc-h'>{dot}{_esc(seg.get('label') or 'Patient')}{cur}</div>"
        f"<table class='pt'>{rows}</table>"
        f"<div class='pc-meta'><span>🕒 {_esc(period)}</span>"
        f"<span>📈 {seg.get('n_samples', 0)} samples</span>"
        f"<span>🔔 {seg.get('n_alarms', 0)} alarms</span></div>"
        f"<a class='pc-open' href='{_esc(href)}' target='wa_charts'>Open charts for this patient ↗</a>"
        f"</div>"
    )


_PATIENT_PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — Patient</title>
<style>
  * { box-sizing:border-box; }
  body { margin:0; font-family:"Segoe UI",system-ui,Arial,sans-serif; color:#1d2733;
    background:#f4f6f9; font-size:14px; }
  header { background:#0a6ebd; color:#fff; padding:12px 20px; display:flex; align-items:center; gap:14px; flex-wrap:wrap; }
  header h1 { margin:0; font-size:18px; }
  header .sub { opacity:.9; font-size:12.5px; }
  header .ctl { margin-left:auto; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
  header a.other { color:#fff; background:rgba(255,255,255,.18); padding:6px 12px;
    border-radius:8px; text-decoration:none; font-size:13px; }
  header a.other:hover { background:rgba(255,255,255,.32); }
  main { max-width:640px; margin:18px auto; padding:0 20px; }
  .card { background:#fff; border:1px solid #e3e8ee; border-radius:12px;
    box-shadow:0 1px 3px rgba(20,40,70,.08); padding:18px 22px; }
  .card h2 { margin:0 0 12px; font-size:15px; color:#0a6ebd; }
  table.pt { border-collapse:collapse; width:100%; font-size:15px; }
  table.pt td { border-bottom:1px solid #eef2f6; padding:10px 8px; }
  table.pt td.k { color:#5b6b7b; width:45%; }
  table.pt td.v { font-weight:700; font-size:16px; }
  table.pt tr:last-child td { border-bottom:0; }
  .muted { color:#5b6b7b; font-style:italic; }
</style></head><body>
<header><h1>__DEVICE__</h1><div class="sub">patient information</div>
  <div class="ctl">__NAV__</div></header>
<main><div class="card"><h2>Patient information</h2>__BODY__</div></main>
</body></html>
"""


_PATIENTS_PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — Patients</title>
<style>
  * { box-sizing:border-box; }
  body { margin:0; font-family:"Segoe UI",system-ui,Arial,sans-serif; color:#1d2733;
    background:#f4f6f9; font-size:14px; }
  header { background:#0a6ebd; color:#fff; padding:12px 20px; display:flex; align-items:center; gap:14px; flex-wrap:wrap; }
  header h1 { margin:0; font-size:18px; }
  header .sub { opacity:.9; font-size:12.5px; }
  header .ctl { margin-left:auto; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
  header a.other { color:#fff; background:rgba(255,255,255,.18); padding:6px 12px;
    border-radius:8px; text-decoration:none; font-size:13px; }
  header a.other:hover { background:rgba(255,255,255,.32); }
  main { max-width:920px; margin:18px auto; padding:0 20px; }
  .intro { color:#5b6b7b; font-size:13px; margin:0 0 14px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:14px; }
  .pcard { background:#fff; border:1px solid #e3e8ee; border-radius:12px;
    box-shadow:0 1px 3px rgba(20,40,70,.08); padding:14px 16px; display:flex; flex-direction:column; }
  .pcard.pcur { border-color:#0a6ebd; box-shadow:0 0 0 2px rgba(10,110,189,.15); }
  .pc-h { font-size:16px; font-weight:700; color:#0a6ebd; margin-bottom:8px; display:flex; align-items:center; gap:8px; }
  .pc-h .cur { font-size:11px; font-weight:600; color:#fff; background:#0a6ebd; border-radius:10px; padding:1px 8px; }
  table.pt { border-collapse:collapse; width:100%; font-size:13.5px; }
  table.pt td { border-bottom:1px solid #eef2f6; padding:5px 6px; }
  table.pt td.k { color:#5b6b7b; width:48%; }
  table.pt td.v { font-weight:700; }
  table.pt tr:last-child td { border-bottom:0; }
  .pc-meta { display:flex; flex-wrap:wrap; gap:6px 14px; color:#5b6b7b; font-size:12px; margin:10px 0; }
  .pc-open { margin-top:auto; display:inline-block; text-align:center; background:#0a6ebd; color:#fff;
    text-decoration:none; font-weight:600; font-size:13px; border-radius:8px; padding:8px 12px; }
  .pc-open:hover { background:#094e8c; }
  .muted { color:#5b6b7b; font-style:italic; }
</style></head><body>
<header><h1>__DEVICE__</h1><div class="sub">patients on this device</div>
  <div class="ctl">__NAV__</div></header>
<main>__INTRO__<div class="grid">__CARDS__</div></main>
</body></html>
"""
