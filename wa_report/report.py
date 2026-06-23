"""Assemble the report data model from a folder of chats."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from . import media
from .grouping import (Cycle, build_content, collect_untimed,
                       group_into_cycles, group_into_days, group_into_hours)
from .parser import load_and_merge, rt_names


@dataclass
class Report:
    hospital: str
    patient: str
    date_in: datetime
    date_out: datetime
    rts: List[str]
    chat_count: int
    cycles: List[Cycle]
    untimed: List[Tuple[datetime, str, str]]
    total_photos: int = 0
    folder: Path = field(default=Path("."))

    @property
    def duration_days(self) -> int:
        return (self.date_out.date() - self.date_in.date()).days + 1

    @property
    def date_in_str(self) -> str:
        return self.date_in.strftime("%d/%m/%Y %H:%M")

    @property
    def date_out_str(self) -> str:
        return self.date_out.strftime("%d/%m/%Y %H:%M")


def build_report(folders, hospital: str, patient: str,
                 mode: str = "daily", gap_minutes: int = 15,
                 buffer_minutes: int = 3) -> Report:
    messages, chat_files = load_and_merge(folders)
    real = [m for m in messages if not m.is_system]
    if not real:
        raise ValueError(f"No WhatsApp messages found under: {folders}")

    if mode == "gap":
        cycles = group_into_cycles(messages, gap_minutes=gap_minutes)
    elif mode == "hourly":
        cycles = group_into_hours(messages, buffer_minutes=buffer_minutes)
    else:  # daily
        cycles = group_into_days(messages, buffer_minutes=buffer_minutes)
    total_photos = 0
    for c in cycles:
        build_content(c)
        # Count resolvable images for the summary.
        resolved, _ = media.resolve_images(c.photo_names)
        total_photos += len(resolved)

    return Report(
        hospital=hospital,
        patient=patient,
        date_in=real[0].dt,
        date_out=real[-1].dt,
        rts=rt_names(messages),
        chat_count=len(chat_files),
        cycles=cycles,
        untimed=collect_untimed(messages),
        total_photos=total_photos,
        folder=chat_files[0].parent if chat_files else Path("."),
    )
