"""Shared data payload for the interactive chart pages (charts.html / windows.html).

Loads the cyclic CSV, alarm intervals, mode changes, log events, photo bursts
and the patient roster into one JSON-able ``payload`` (embedded client-side so
the pages stay fully functional offline) plus a ``meta`` dict used for the
page's stat bar / notes.
"""

from __future__ import annotations

import html
from typing import Sequence

import pandas as pd

from .. import media
from ..parser import load_and_merge
from .alarms import (load_alarm_intervals, load_alarm_limits, load_log_events,
                     load_patient_add_events)
from .bursts import detect_bulk_events
from .config import ALARM_COLORS, DEFAULT_VARIABLES, VARIABLE_UNITS
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
                  window_minutes: int = 10):
    """Shared data payload for both interactive chart pages.

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
    df, missing = load_cyclic(cyclic_source, all_vars)
    present = [v for v in all_vars if v not in missing]
    default_sel = [v for v in (list(variables) or DEFAULT_VARIABLES) if v in present]
    if not default_sel:
        default_sel = present[:3]

    alarms = load_alarm_intervals(alarms_source)   # Activated→Deactivated intervals
    modes = load_modes(cyclic_source)              # ventilation-mode changes
    events_df = load_log_events(alarms_source)     # settings/data-change events
    limits = load_alarm_limits(alarms_source)      # alarm-limit setting changes
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
    modes_flat = [[_ms(dt), name] for dt, name in modes]
    events_flat = ([[_ms(dt), ev] for dt, ev in zip(events_df["DateTime"], events_df["Event"])]
                   if not events_df.empty else [])
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

    all_ms = (list(dts) + [a[0] for a in alarms_flat] + [a[1] for a in alarms_flat]
              + [e[0] for e in events_flat] + [m[0] for m in modes_flat])
    t_min = min(all_ms) if all_ms else 0
    t_max = max(all_ms) if all_ms else 0

    # Per-patient roster: split the log at each "Add New Patient" handover. The
    # last segment is the current patient (preamble); earlier ones get b1/b2/…
    patient_pairs = load_patient_info(cyclic_source)
    add_ms = [_ms(t) for t in load_patient_add_events(alarms_source)]
    # beginning of the logs = earliest log row of any kind (alarms + events)
    log_times = [a[0] for a in alarms_flat] + [e[0] for e in events_flat]
    log_start = min(log_times) if log_times else None
    patients = assemble_roster(patient_pairs, add_ms, list(dts),
                               [a[0] for a in alarms_flat], t_min, t_max,
                               log_start=log_start)

    payload = {
        "vars": present,
        "defaultVars": default_sel,
        "units": {v: VARIABLE_UNITS.get(v, "") for v in present},
        "alarmColors": ALARM_COLORS,
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
