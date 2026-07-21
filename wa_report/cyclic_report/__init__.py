"""Cyclic <-> photo timeline report (the "second report").

Maps WhatsApp photo-burst times onto the ventilator's cyclic CSV log, one graph
per 12-hour window. Split across submodules that mirror the original plotter's
layout:

    config         constants (Y-axis variables + units, colours)
    bursts         WhatsApp side — detect photo bursts
    data_loader    read + clean the cyclic CSV
    windowing      cut the timeline into 12-hour windows
    plotting       render one window to a PNG
    report         orchestration + data model (build_cyclic_report)
    render_html    self-contained HTML report

The public names below are re-exported so callers can keep importing them
straight from ``wa_report.cyclic_report``.
"""

from __future__ import annotations

from .alarms import alarm_types_in, load_alarms
from .bursts import BulkEvent, detect_bulk_events, image_send_times
from .config import ALARM_COLORS, DEFAULT_VARIABLES, VARIABLE_UNITS
from .data_loader import load_cyclic
from .plotting import plot_window, window_title
from .render_combined import build_combined_html
from .render_html import render_cyclic_html
from .render_pages import build_charts_html, build_linked_pages
from .report import CyclicReport, WindowResult, build_cyclic_report
from .windowing import split_windows

__all__ = [
    "VARIABLE_UNITS", "DEFAULT_VARIABLES", "ALARM_COLORS",
    "BulkEvent", "image_send_times", "detect_bulk_events",
    "load_cyclic", "load_alarms", "alarm_types_in", "split_windows",
    "plot_window", "window_title",
    "WindowResult", "CyclicReport", "build_cyclic_report",
    "render_cyclic_html", "build_combined_html",
    "build_charts_html", "build_linked_pages",
]
