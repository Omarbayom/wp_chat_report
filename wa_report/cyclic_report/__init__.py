"""Cyclic <-> photo timeline report (the "second report").

Maps WhatsApp photo-burst times onto the ventilator's cyclic CSV log and
renders interactive, self-contained HTML pages. Split across submodules:

    config          constants (Y-axis variables + units, colours)
    bursts          WhatsApp side — group photo-send times into bursts
    data_loader     read + clean the cyclic CSV
    alarms          read the alarm/event Log CSV
    roster          per-patient episode segmentation
    patient         patient preamble + patient/banner HTML
    render_combined build_payload — the shared data payload for both chart pages
    render_pages    charts.html (stock overview) + report.html/windows.html linking
    render_windows  windows.html (fixed-window view)

The public names below are re-exported so callers can keep importing them
straight from ``wa_report.cyclic_report``.
"""

from __future__ import annotations

from .alarms import load_alarm_intervals, load_alarms
from .bursts import BulkEvent, detect_bulk_events
from .config import ALARM_COLORS, DEFAULT_VARIABLES, VARIABLE_UNITS
from .data_loader import load_cyclic
from .patient import (build_patient_html, build_patients_html,
                      load_patient_info, patient_title, with_fallback_id)
from .roster import assemble_roster, build_roster
from .render_pages import build_charts_html, build_linked_pages

__all__ = [
    "VARIABLE_UNITS", "DEFAULT_VARIABLES", "ALARM_COLORS",
    "BulkEvent", "detect_bulk_events",
    "load_cyclic", "load_alarms", "load_alarm_intervals",
    "build_charts_html", "build_linked_pages",
    "load_patient_info", "patient_title", "build_patient_html", "with_fallback_id",
    "build_patients_html", "build_roster", "assemble_roster",
]
