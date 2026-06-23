"""Group a merged, time-sorted message stream into reporting cycles, and build
the rendered content (photos + classified comments) for each cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

from . import extract, media
from .parser import Message, SUPERVISOR_HINTS


@dataclass
class PhotoRef:
    name: str
    path: Path          # resolved absolute path (may not exist -> see `exists`)
    exists: bool


@dataclass
class Cycle:
    index: int
    start: datetime
    end: datetime
    messages: List[Message]
    # filled by build_content():
    # (name, source_dir, message_timestamp)
    photo_names: List[Tuple[str, Path, datetime]] = field(default_factory=list)
    comments: Dict[str, List[str]] = field(default_factory=dict)       # bucket -> lines
    general: List[str] = field(default_factory=list)                   # "Speaker: line"
    window_label: str = ""   # set for fixed hourly windows ("10:00 to 11:00")

    @property
    def title(self) -> str:
        if self.window_label:
            return self.window_label
        if self.start.date() == self.end.date():
            return f"{self.start.strftime('%d/%m/%Y')}  {_t(self.start)} – {_t(self.end)}"
        return f"{self.start.strftime('%d/%m/%Y %H:%M')} – {self.end.strftime('%d/%m/%Y %H:%M')}"


def _t(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def _is_supervisor(sender) -> bool:
    return bool(sender) and any(h in sender.lower() for h in SUPERVISOR_HINTS)


def group_into_cycles(messages: List[Message], gap_minutes: int = 15) -> List[Cycle]:
    """Split the timeline wherever the gap between consecutive messages exceeds
    *gap_minutes*."""
    cycles: List[Cycle] = []
    bucket: List[Message] = []
    gap = timedelta(minutes=gap_minutes)

    def flush():
        if bucket:
            cycles.append(
                Cycle(
                    index=len(cycles) + 1,
                    start=bucket[0].dt,
                    end=bucket[-1].dt,
                    messages=list(bucket),
                )
            )

    prev: Message | None = None
    for m in messages:
        if m.is_system:
            continue
        if prev is not None and (m.dt - prev.dt) > gap:
            flush()
            bucket = []
        bucket.append(m)
        prev = m
    flush()
    return cycles


def _assigned_hour(dt: datetime, buffer: timedelta) -> datetime:
    """The clock hour a message belongs to. A message within *buffer* of the
    upcoming hour boundary snaps forward to it (a slightly-late/early report);
    otherwise it floors to its own hour."""
    top = dt.replace(minute=0, second=0, microsecond=0)
    next_top = top + timedelta(hours=1)
    if (next_top - dt) <= buffer:
        return next_top
    return top


def group_into_hours(messages: List[Message], buffer_minutes: int = 3) -> List[Cycle]:
    """Group messages into fixed clock-hour windows labelled '10:00 to 11:00'.

    A *buffer* (default 3 min) pulls a batch that lands just past the hour into
    the hour it belongs to, so a report sent at 11:02 still joins the 11:00 window.
    """
    buffer = timedelta(minutes=buffer_minutes)
    cycles: List[Cycle] = []
    cur_hour: datetime | None = None
    bucket: List[Message] = []

    def flush():
        if bucket and cur_hour is not None:
            end = cur_hour + timedelta(hours=1)
            label = (f"{cur_hour.strftime('%d/%m/%Y')}  "
                     f"{cur_hour.strftime('%H:%M')} to {end.strftime('%H:%M')}")
            cycles.append(
                Cycle(
                    index=len(cycles) + 1,
                    start=cur_hour,
                    end=end,
                    messages=list(bucket),
                    window_label=label,
                )
            )

    for m in messages:
        if m.is_system:
            continue
        h = _assigned_hour(m.dt, buffer)
        if cur_hour is None or h != cur_hour:
            flush()
            bucket = []
            cur_hour = h
        bucket.append(m)
    flush()
    return cycles


def _assigned_day(dt: datetime, buffer: timedelta):
    """The calendar day a message belongs to. A message within *buffer* of
    midnight snaps to the next day (e.g. 11:58 pm on 12/11 -> 13/11)."""
    day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    next_midnight = day_start + timedelta(days=1)
    if (next_midnight - dt) <= buffer:
        return next_midnight.date()
    return dt.date()


def group_into_days(messages: List[Message], buffer_minutes: int = 3) -> List[Cycle]:
    """Group messages into per-calendar-day sections labelled '15/11/2025'.

    A *buffer* (default 3 min) pulls a message sent just before midnight into the
    next day's section.
    """
    buffer = timedelta(minutes=buffer_minutes)
    cycles: List[Cycle] = []
    cur = None
    bucket: List[Message] = []

    def flush():
        if bucket and cur is not None:
            start = datetime(cur.year, cur.month, cur.day)
            cycles.append(
                Cycle(
                    index=len(cycles) + 1,
                    start=start,
                    end=start + timedelta(days=1),
                    messages=list(bucket),
                    window_label=cur.strftime("%d/%m/%Y"),
                )
            )

    for m in messages:
        if m.is_system:
            continue
        d = _assigned_day(m.dt, buffer)
        if cur is None or d != cur:
            flush()
            bucket = []
            cur = d
        bucket.append(m)
    flush()
    return cycles


# ---- Chronological chat transcript (time-only) ---------------------------------

@dataclass
class ChatItem:
    kind: str                       # 'text' | 'image' | 'media'
    dt: datetime
    speaker: str
    text: str = ""                  # text body, or a label like '[voice note]'
    name: str = ""                  # attachment filename (image/media)
    source_dir: Path = None


def _media_label(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext in (".opus", ".mp3", ".m4a", ".ogg", ".aac", ".wav"):
        return "[voice note]"
    if ext in (".mp4", ".3gp", ".mov", ".avi", ".mkv", ".webm"):
        return "[video]"
    return "[file]"


def transcript(cycle: Cycle) -> List[ChatItem]:
    """Flatten a day's messages into a chronological list of chat items
    (text lines, inline images, and small markers for skipped media)."""
    items: List[ChatItem] = []
    for m in cycle.messages:
        if m.is_system or m.is_deleted:
            continue
        speaker = m.sender or "System"
        if m.attachment:
            if media.is_image(m.attachment):
                items.append(ChatItem("image", m.dt, speaker,
                                       name=m.attachment, source_dir=m.source_dir))
            else:
                items.append(ChatItem("media", m.dt, speaker,
                                       text=_media_label(m.attachment)))
            for c in m.continuations:
                if c.strip() and not extract.is_clock_note(c):
                    items.append(ChatItem("text", m.dt, speaker, text=c.strip()))
        elif m.is_media_omitted:
            items.append(ChatItem("media", m.dt, speaker, text="[media omitted]"))
        else:
            for line in m.text_lines():
                if extract.is_clock_note(line):
                    continue
                items.append(ChatItem("text", m.dt, speaker, text=line.strip()))
    return items


def hm(dt: datetime) -> str:
    """Time only, e.g. '11:58 pm'."""
    return dt.strftime("%I:%M %p").lstrip("0").lower()


def build_content(cycle: Cycle) -> None:
    """Resolve photo names and classify comment lines for a cycle (in place)."""
    comments: Dict[str, List[str]] = {
        extract.COMFORT: [],
        extract.HUMIDIFIER: [],
        extract.WATER_TRAP: [],
    }
    general: List[str] = []
    photos: List[Tuple[str, Path, datetime]] = []

    for m in cycle.messages:
        if m.attachment:
            photos.append((m.attachment, m.source_dir, m.dt))

        speaker = m.sender or "System"
        is_rt = bool(m.sender) and not _is_supervisor(m.sender)

        for line in m.text_lines():
            if extract.is_clock_note(line):
                continue
            hits = extract.match_buckets(line)
            placed = False
            if is_rt and hits:
                for cat in hits:
                    comments[cat].append(line.strip())
                placed = True
            if not placed and extract.is_substantive(line):
                general.append(f"{speaker}: {line.strip()}")

    # Drop empty buckets.
    cycle.comments = {k: v for k, v in comments.items() if v}
    cycle.general = general
    cycle.photo_names = photos


def collect_untimed(messages: List[Message]) -> List[Tuple[datetime, str, str]]:
    """The 'chats with no timestamp': every continuation/caption line, with a
    pointer to its parent message (datetime + speaker)."""
    out: List[Tuple[datetime, str, str]] = []
    for m in messages:
        if m.is_system:
            continue
        speaker = m.sender or "System"
        for c in m.continuations:
            if c.strip() and not extract.is_clock_note(c):
                out.append((m.dt, speaker, c.strip()))
    return out
