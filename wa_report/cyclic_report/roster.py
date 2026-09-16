"""Split a reused device's export into a **roster** of per-patient segments.

A single device is used for many patients over time; the Log records an
``Add New Patient`` row at each handover (see
``alarms.load_patient_add_events``) while the CyclicData preamble only carries
the **current** (latest) patient's details (``patient.load_patient_info``).

``assemble_roster`` cuts the timeline ``[t_min, t_max]`` at each add-event into
segments — one per patient. The **last** segment is the current patient and gets
the preamble demographics; earlier segments have no details in the file, so they
are labelled ``b1`` / ``b2`` / … in device (chronological) order. Each segment
also carries its sample/alarm counts. ``build_roster`` is the same thing from raw
sources (cyclic + log), for callers that don't already have the parsed arrays.
"""

from __future__ import annotations

import bisect
from typing import List, Optional

import pandas as pd

from .alarms import load_alarms, load_log_events, load_patient_add_events
from .config import VARIABLE_UNITS
from .data_loader import load_cyclic
from .patient import PATIENT_FIELDS, load_patient_info, patient_title

_EPOCH = pd.Timestamp("1970-01-01")

# Distinct trend colours, assigned to patients in device order. The first is the
# default cyclic blue, so a single-patient log looks exactly as before.
PATIENT_COLORS = ["#0a6ebd", "#e6194b", "#2e8b57", "#f58231", "#6f42c1",
                  "#0aa3a3", "#9a6324", "#c0392b", "#1abc9c", "#8e44ad"]


def _ms(dt) -> int:
    return int((pd.Timestamp(dt) - _EPOCH).total_seconds() * 1000)


def _count_in(sorted_ms: List[int], a: int, b: int) -> int:
    """Number of timestamps in ``[a, b)`` (sorted_ms must be ascending)."""
    return bisect.bisect_left(sorted_ms, b) - bisect.bisect_left(sorted_ms, a)


def assemble_roster(preamble, add_ms, sample_ms, alarm_ms, t_min, t_max,
                    log_start=None) -> List[dict]:
    """Build the per-patient roster (pure computation, no I/O).

    *preamble* = the current patient's ``[(label,value)]`` (may be empty). *add_ms*
    = ``Add New Patient`` times. *sample_ms* / *alarm_ms* = ascending ms arrays,
    used only for each segment's sample/alarm counts. *log_start* is unused (kept
    for backward-compat call signatures).

    A new patient segment **begins only at an actual ``Add New Patient`` log
    row** (a real handover). The logs and the cyclic data commonly don't start
    at the same instant (e.g. alarms are recorded slightly before cyclic
    sampling begins) — that gap is **not** a patient change, so it no longer
    creates its own segment; the whole stretch from the timeline start to the
    first real handover (or to the end, if there is none) is one patient. This
    keeps a segment's displayed date range aligned with the actual Add New
    Patient log entries whenever the log and cyclic data cover the same
    session. Returns a list of segment dicts (chronological); empty when there
    is nothing to split (a single unnamed patient, one continuous start)."""
    add_ms = sorted(m for m in add_ms if t_min < m < t_max)
    # segment start points: the timeline start + every real handover
    starts = sorted({t_min} | set(add_ms))
    if len(starts) <= 1 and not add_ms and not preamble:
        return []
    edges = starts + [t_max]
    raw = [(edges[i], edges[i + 1]) for i in range(len(edges) - 1) if edges[i + 1] > edges[i]]
    if not raw:
        return []

    n = len(raw)
    out: List[dict] = []
    b = 0
    for i, (s, e) in enumerate(raw):
        info = list(preamble) if i == n - 1 else []      # last = current patient
        d = dict(info)
        if not (d.get("Patient ID") or "").strip():
            b += 1
            d["Patient ID"] = f"b{b}"
            info = [(f, d[f]) for f in PATIENT_FIELDS if f in d]
        label = patient_title(info) or f"Patient {i + 1}"
        last = i == n - 1
        end = e + 1 if last else e                       # last segment: include t_max
        out.append({
            "index": i,
            "t0": s, "t1": e,
            "info": [[k, v] for k, v in info],
            "label": label,
            "current": last,
            "color": PATIENT_COLORS[i % len(PATIENT_COLORS)],
            "n_samples": _count_in(sample_ms, s, end),
            "n_alarms": _count_in(alarm_ms, s, end),
        })
    return out


def build_roster(cyclic_source, alarms_source=None, date_order: "bool | None" = None) -> List[dict]:
    """The roster straight from a cyclic CSV (+ optional Log). Light I/O — parses
    the cyclic timestamps and the log, but never touches any chat. *date_order*:
    ``None`` auto-detects each file's day/month order; ``True``/``False`` forces
    day-first/month-first everywhere below, for a source known to be ambiguous."""
    preamble = load_patient_info(cyclic_source, date_order)
    add_ms = [_ms(t) for t in load_patient_add_events(alarms_source, date_order)]
    try:
        df, _ = load_cyclic(cyclic_source, list(VARIABLE_UNITS.keys()), date_order)
        sample_ms = sorted(_ms(t) for t in df["DateTime"])
    except Exception:
        sample_ms = []
    alarms = load_alarms(alarms_source, date_order) if alarms_source is not None else None
    alarm_ms = (sorted(_ms(t) for t in alarms["DateTime"])
                if alarms is not None and not alarms.empty else [])
    # beginning of the logs = the earliest log row of ANY kind (alarms + events,
    # where events already include the "Add New Patient" rows)
    events = load_log_events(alarms_source, date_order) if alarms_source is not None else None
    event_ms = (sorted(_ms(t) for t in events["DateTime"])
                if events is not None and not events.empty else [])
    log_ms = alarm_ms + event_ms
    log_start = min(log_ms) if log_ms else None
    universe = sample_ms + alarm_ms + add_ms + event_ms
    if not universe:
        return []
    return assemble_roster(preamble, add_ms, sample_ms, alarm_ms,
                           min(universe), max(universe), log_start=log_start)
