"""Shared data payload for the interactive charts page (charts.html).

Loads the cyclic CSV, alarm intervals, mode changes, log events, photo bursts
and the patient roster into one JSON-able ``payload`` (embedded client-side so
the page stays fully functional offline) plus a ``meta`` dict used for the
page's stat bar / notes.
"""

from __future__ import annotations

import html
from typing import Sequence

import pandas as pd

from .. import media
from ..parser import load_and_merge
from .alarms import (load_alarm_intervals, load_alarm_limits, load_log_entries,
                     load_patient_add_events)
from .bursts import detect_bulk_events
from .config import ALARM_COLORS, DEFAULT_VARIABLES, MODE_COLOR_PALETTE, VARIABLE_UNITS
from .data_loader import load_cyclic, load_modes
from .patient import load_patient_info
from .roster import assemble_roster

_EPOCH = pd.Timestamp("1970-01-01")


def _esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def _ms(dt) -> int:
    """Milliseconds since 1970 treating the (naive) timestamp as wall-clock.

    Used only as a consistent numeric axis shared by cyclic samples, alarms,
    bursts and chat messages — never as a real UTC instant.
    """
    return int((pd.Timestamp(dt) - _EPOCH).total_seconds() * 1000)


def build_payload(folders, cyclic_source, variables: Sequence[str],
                  alarms_source=None, min_photos: int = 3,
                  window_minutes: int = 10, date_order: "bool | None" = None):
    """Shared data payload for both interactive chart pages.

    *date_order*: ``None`` (default) auto-detects each CSV's day/month order
    per-file (see ``csv_io.parse_datetimes``); ``True``/``False`` forces
    day-first/month-first everywhere below, for a source known to export
    ambiguous (non-ISO) dates that the auto-detection can't reliably call —
    e.g. a short log that never crosses a calendar day boundary.

    Loads **every** configurable variable that exists in the CSV (so the page can
    let the user toggle any of them on the Y axis client-side), plus the alarm
    log and the photo bursts. Returns ``(payload, meta)``:

    ``payload`` (embedded as JSON in the page):
      * ``vars``        — all present variables (Y-axis candidates), in config order.
      * ``defaultVars`` — the user's chosen subset (∩ present); the initial selection.
      * ``units``       — units for every present variable.
      * ``samples``     — ``[ms, <all present vars…>]`` rows, time-sorted.
      * ``alarms``      — ``[ms, type]`` (filtered to ``ALARM_COLORS``).
      * ``bursts``      — ``[ms, count, cid]`` **only where cyclic data exists**
        (photos with no cyclic sample behind them are dropped).
      * ``tMin``/``tMax`` — union of sample **and** alarm times, so alarm-only
        spans (alarms recorded with no cyclic data) are still reachable.
      * ``sampleMin``/``sampleMax`` — the cyclic sample coverage only.

    ``meta`` (for the page's stat bar / notes): counts + spans.
    """
    all_vars = list(VARIABLE_UNITS.keys())
    df, missing = load_cyclic(cyclic_source, all_vars, date_order)
    present = [v for v in all_vars if v not in missing]
    default_sel = [v for v in (list(variables) or DEFAULT_VARIABLES) if v in present]
    if not default_sel:
        default_sel = present[:3]

    alarms = load_alarm_intervals(alarms_source, date_order)   # Activated→Deactivated intervals
    cyclic_modes = load_modes(cyclic_source, date_order)       # mode changes seen in the cyclic CSV
    log_entries = load_log_entries(alarms_source, date_order)  # non-alarm Log rows: mode | event, + settings
    limits = load_alarm_limits(alarms_source, date_order)      # alarm-limit setting changes
    # The chat is optional: with no folders there are simply no photo bursts.
    img_times = []
    if folders:
        img_times = sorted(
            m.dt for m in load_and_merge(folders)[0]
            if not m.is_system and m.attachment and media.is_image(m.attachment)
        )
    events = detect_bulk_events(img_times, min_photos=min_photos,
                                window_minutes=window_minutes)

    cols = {v: df[v].tolist() for v in present}
    dts = [_ms(t) for t in df["DateTime"]]
    samples = []
    for r, t in enumerate(dts):
        row = [t]
        for v in present:
            x = cols[v][r]
            row.append(None if pd.isna(x) else round(float(x), 2))
        samples.append(row)

    # alarms are [start_ms, end_ms, type] intervals (active while the cursor is inside)
    alarms_flat = ([[_ms(s), _ms(e), a] for s, e, a in
                    zip(alarms["Start"], alarms["End"], alarms["Alarm"])]
                   if not alarms.empty else [])
    if log_entries.empty:
        event_rows = mode_rows = log_entries
    else:
        event_rows = log_entries[log_entries["Kind"] == "event"]
        mode_rows = log_entries[log_entries["Kind"] == "mode"]
    # events are [ms, text, settings] points ("settings" = that log row's full
    # set-value/limit/simultaneous-cyclic-reading snapshot, for the detail popup)
    events_flat = ([[_ms(dt), txt, settings] for dt, txt, settings in
                    zip(event_rows["DateTime"], event_rows["Text"], event_rows["Settings"])]
                   if not event_rows.empty else [])
    limits_flat = [[_ms(dt), snap] for dt, snap in limits]
    # stable variable order: first-seen order across the change points
    limit_vars: list = []
    for _, snap in limits:
        for v in snap:
            if v not in limit_vars:
                limit_vars.append(v)

    s_min, s_max = (dts[0], dts[-1]) if dts else (None, None)
    # Only bursts that land inside the cyclic sample coverage — a photo with no
    # cyclic data behind it is not shown as a marker.
    bursts_flat = []
    if s_min is not None:
        bursts_flat = [[_ms(e.start), e.count, f"img-{_ms(e.start)}"]
                       for e in events if s_min <= _ms(e.start) <= s_max]

    # Merge cyclic-CSV mode-change points with log-sourced "mode" rows (Log
    # entries whose text names a mode — see load_log_entries) into one
    # time-sorted timeline; log-sourced points carry a settings snapshot,
    # cyclic-sourced ones don't (no Log row backs them). Consecutive points
    # with the same label collapse to the first — the same rule load_modes
    # already applies to its own (cyclic-only) source — but a settings
    # snapshot from a dropped duplicate is kept on the surviving point.
    mode_points_raw = [(_ms(dt), name, None) for dt, name in cyclic_modes]
    if not mode_rows.empty:
        mode_points_raw += [[_ms(dt), txt, settings] for dt, txt, settings in
                            zip(mode_rows["DateTime"], mode_rows["Text"], mode_rows["Settings"])]
    mode_points_raw.sort(key=lambda p: p[0])
    mode_points: list = []
    for ms, label, settings in mode_points_raw:
        if mode_points and mode_points[-1][1] == label:
            if mode_points[-1][2] is None and settings is not None:
                mode_points[-1] = (mode_points[-1][0], label, settings)
        else:
            mode_points.append((ms, label, settings))

    all_ms = (list(dts) + [a[0] for a in alarms_flat] + [a[1] for a in alarms_flat]
              + [e[0] for e in events_flat] + [m[0] for m in mode_points])
    t_min = min(all_ms) if all_ms else 0
    t_max = max(all_ms) if all_ms else 0

    # modes as [start_ms, end_ms, label, settings] intervals — active from one
    # mode point to the next (or to t_max for the last) — rendered as a
    # swim-lane, the same way alarms already are.
    modes_flat = []
    for i, (ms, label, settings) in enumerate(mode_points):
        end = mode_points[i + 1][0] if i + 1 < len(mode_points) else t_max
        modes_flat.append([ms, end, label, settings])
    mode_labels: list = []
    for _, label, _ in mode_points:
        if label not in mode_labels:
            mode_labels.append(label)
    mode_colors = {label: MODE_COLOR_PALETTE[i % len(MODE_COLOR_PALETTE)]
                   for i, label in enumerate(mode_labels)}

    # Per-patient roster: split the log at each "Add New Patient" handover. The
    # last segment is the current patient (preamble); earlier ones get b1/b2/…
    patient_pairs = load_patient_info(cyclic_source, date_order)
    add_ms = [_ms(t) for t in load_patient_add_events(alarms_source, date_order)]
    patients = assemble_roster(patient_pairs, add_ms, list(dts),
                               [a[0] for a in alarms_flat], t_min, t_max)

    payload = {
        "vars": present,
        "defaultVars": default_sel,
        "units": {v: VARIABLE_UNITS.get(v, "") for v in present},
        "alarmColors": ALARM_COLORS,
        "modeColors": mode_colors,
        "samples": samples, "alarms": alarms_flat, "bursts": bursts_flat,
        "modes": modes_flat, "events": events_flat,
        "limits": limits_flat, "limitVars": limit_vars,
        "tMin": t_min, "tMax": t_max,
        "sampleMin": s_min if s_min is not None else 0,
        "sampleMax": s_max if s_max is not None else 0,
        "patients": patients,
    }
    meta = {
        "missing": missing,
        "present": present,
        "default_sel": default_sel,
        "n_samples": len(samples),
        "n_alarms": int(len(alarms)),
        "n_bursts": len(bursts_flat),
        "n_bursts_dropped": len(events) - len(bursts_flat),
        "n_modes": len(modes_flat),
        "n_events": len(events_flat),
        "n_limit_changes": len(limits_flat),
        "img_times": img_times,
        "df": df,
        "patient": patient_pairs,
        "patients": patients,
    }
    return payload, meta
