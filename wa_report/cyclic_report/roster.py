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

from .alarms import load_alarms, load_patient_add_events
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


def assemble_roster(preamble, add_ms, sample_ms, alarm_ms, t_min, t_max) -> List[dict]:
    """Build the per-patient roster (pure computation, no I/O).

    *preamble* = the current patient's ``[(label,value)]`` (may be empty). *add_ms*
    = ``Add New Patient`` times. *sample_ms* / *alarm_ms* = ascending ms arrays.
    Returns a list of segment dicts (chronological); empty when there is nothing
    to show (a single unnamed patient with no handovers)."""
    add_ms = sorted(m for m in add_ms if t_min < m < t_max)
    if not add_ms and not preamble:
        return []
    edges = [t_min] + add_ms + [t_max]
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


def build_roster(cyclic_source, alarms_source=None) -> List[dict]:
    """The roster straight from a cyclic CSV (+ optional Log). Light I/O — parses
    the cyclic timestamps and the log, but never touches any chat."""
    preamble = load_patient_info(cyclic_source)
    add_ms = [_ms(t) for t in load_patient_add_events(alarms_source)]
    try:
        df, _ = load_cyclic(cyclic_source, list(VARIABLE_UNITS.keys()))
        sample_ms = sorted(_ms(t) for t in df["DateTime"])
    except Exception:
        sample_ms = []
    alarms = load_alarms(alarms_source) if alarms_source is not None else None
    alarm_ms = (sorted(_ms(t) for t in alarms["DateTime"])
                if alarms is not None and not alarms.empty else [])
    universe = sample_ms + alarm_ms + add_ms
    if not universe:
        return []
    return assemble_roster(preamble, add_ms, sample_ms, alarm_ms,
                           min(universe), max(universe))
