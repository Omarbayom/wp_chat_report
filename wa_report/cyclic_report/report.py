"""Orchestration: chat photo bursts + cyclic CSV -> per-window graphs.

Plays the role of the original plotter's ``main.py``, but returns a data model
(``CyclicReport``) instead of writing PNGs to a fixed folder, so the Streamlit
tab and the HTML renderer can consume it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Sequence

from .alarms import load_alarms
from .bursts import BulkEvent, detect_bulk_events, image_send_times
from .config import DEFAULT_VARIABLES
from .data_loader import load_cyclic
from .plotting import plot_window, window_title
from .windowing import split_windows


@dataclass
class WindowResult:
    start: datetime
    end: datetime
    title: str
    png: bytes
    events: List[BulkEvent]
    alarm_counts: Dict[str, int] = field(default_factory=dict)  # alarm type -> count


@dataclass
class CyclicReport:
    device_label: str
    variables: List[str]
    missing_vars: List[str]
    data_start: datetime
    data_end: datetime
    total_images: int
    windows: List[WindowResult]
    total_alarms: int = 0

    @property
    def total_bursts(self) -> int:
        return sum(len(w.events) for w in self.windows)

    @property
    def burst_images(self) -> int:
        return sum(e.count for w in self.windows for e in w.events)


def build_cyclic_report(folders, cyclic_source, variables: Sequence[str],
                        device_label: str = "", alarms_source=None,
                        min_photos: int = 3, window_minutes: int = 10,
                        window_hours: int = 12) -> CyclicReport:
    """Full pipeline: chat photo bursts + cyclic CSV (+ optional alarm log) ->
    per-window graphs."""
    variables = list(variables) or list(DEFAULT_VARIABLES)
    times = image_send_times(folders)
    events = detect_bulk_events(times, min_photos=min_photos,
                                window_minutes=window_minutes)
    df, missing = load_cyclic(cyclic_source, variables)
    alarms = load_alarms(alarms_source)

    windows: List[WindowResult] = []
    for start, end, sub in split_windows(df, hours=window_hours):
        png = plot_window(start, end, sub, variables, events, alarms=alarms)
        win_events = [e for e in events if start <= e.start < end]
        win_alarms = alarms[(alarms["DateTime"] >= start) & (alarms["DateTime"] < end)]
        counts = win_alarms["Alarm"].value_counts().to_dict() if not win_alarms.empty else {}
        windows.append(WindowResult(start, end, window_title(start, end),
                                     png, win_events, counts))

    return CyclicReport(
        device_label=device_label or "Cyclic device log",
        variables=[v for v in variables if v not in missing],
        missing_vars=missing,
        data_start=df["DateTime"].min().to_pydatetime(),
        data_end=df["DateTime"].max().to_pydatetime(),
        total_images=len(times),
        windows=windows,
        total_alarms=int(len(alarms)),
    )
