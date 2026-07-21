"""Photo bursts from the WhatsApp side.

The respiratory therapists photograph the ventilator screen and send those
"bulky images" into the chat. This module extracts every image-send time and
groups them into *bursts* (a run of photos each within a few minutes of the
last) — one burst becomes one marker on the graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Sequence

from .. import media
from ..parser import load_and_merge


@dataclass
class BulkEvent:
    """A run of photos sent close together — one marker on the graph."""
    start: datetime
    end: datetime
    count: int

    @property
    def span_label(self) -> str:
        a = self.start.strftime("%H:%M")
        b = self.end.strftime("%H:%M")
        return a if a == b else f"{a}–{b}"


def image_send_times(folders) -> List[datetime]:
    """Every image-attachment timestamp across the chat(s), sorted ascending."""
    msgs, _ = load_and_merge(folders)
    times = [
        m.dt for m in msgs
        if not m.is_system and m.attachment and media.is_image(m.attachment)
    ]
    times.sort()
    return times


def detect_bulk_events(times: Sequence[datetime], min_photos: int = 3,
                       window_minutes: int = 10) -> List[BulkEvent]:
    """Group *times* into bursts and keep those with at least *min_photos*.

    A burst continues while each photo lands within *window_minutes* of the
    previous one; a larger gap starts a new burst.
    """
    if not times:
        return []
    gap = timedelta(minutes=window_minutes)
    events: List[BulkEvent] = []
    burst: List[datetime] = [times[0]]

    def flush() -> None:
        if len(burst) >= min_photos:
            events.append(BulkEvent(burst[0], burst[-1], len(burst)))

    for t in times[1:]:
        if t - burst[-1] <= gap:
            burst.append(t)
        else:
            flush()
            burst = [t]
    flush()
    return events
