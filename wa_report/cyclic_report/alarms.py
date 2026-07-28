"""Load the ventilator's alarm log (the ``Log_*.csv`` export).

Plays the role of the original plotter's ``load_alarms`` + ``filter_alarms`` +
``parse_alarms_datetime``: read the CSV, parse the ``Date`` column, and keep only
the alarm types we colour (see ``config.ALARM_COLORS``).

Note the alarm ``Date`` is ISO (``YYYY-MM-DD HH:MM:SS``), unlike the cyclic
``DateTime`` which is day-first (``DD/MM/YYYY HH:MM``) — so this parser does *not*
force day-first.
"""

from __future__ import annotations

from typing import List

import pandas as pd

from .config import ALARM_COLORS
from .csv_io import parse_datetimes, read_ventilator_csv


def load_alarms(source) -> pd.DataFrame:
    """Read an alarm Log CSV (path or file-like) -> DataFrame[DateTime, Alarm].

    Keeps only alarms present in ``ALARM_COLORS`` and sorts by time. Returns an
    empty (but correctly-typed) frame when *source* is falsy or has no usable
    rows, so callers can treat "no alarms" uniformly.
    """
    empty = pd.DataFrame({"DateTime": pd.to_datetime([]), "Alarm": pd.Series([], dtype="object")})
    if source is None:
        return empty

    df = read_ventilator_csv(source, "Alarm")
    if "Alarm" not in df.columns or "Date" not in df.columns:
        raise ValueError(
            "This CSV has no 'Date'/'Alarm' columns — is it a Log export? "
            f"Columns found: {', '.join(map(str, df.columns[:8]))}…"
        )

    df["DateTime"] = parse_datetimes(df["Date"], dayfirst=False)
    df = df.dropna(subset=["DateTime"])
    df = df[df["Alarm"].isin(ALARM_COLORS)]
    if df.empty:
        return empty
    return (
        df[["DateTime", "Alarm"]]
        .sort_values("DateTime")
        .reset_index(drop=True)
    )


def load_log_events(source) -> pd.DataFrame:
    """Read the Log CSV and keep the **non-alarm** rows as events.

    The device logs mode/settings/service actions in the same ``Alarm`` column
    (e.g. "Change A/C-VC Mode Setting", "Maintenance Settings Updated", "Alarm
    Limits Change", "Standby Mode Activated"). Anything **not** in
    ``ALARM_COLORS`` is treated as an *event*. Returns DataFrame[DateTime, Event].
    """
    empty = pd.DataFrame({"DateTime": pd.to_datetime([]), "Event": pd.Series([], dtype="object")})
    if source is None:
        return empty
    df = read_ventilator_csv(source, "Alarm")
    if "Alarm" not in df.columns or "Date" not in df.columns:
        return empty
    df["DateTime"] = parse_datetimes(df["Date"], dayfirst=False)
    df = df.dropna(subset=["DateTime"])
    df = df[~df["Alarm"].isin(ALARM_COLORS)]
    df = df[df["Alarm"].astype(str).str.strip() != ""]
    if df.empty:
        return empty
    return (
        df.rename(columns={"Alarm": "Event"})[["DateTime", "Event"]]
        .sort_values("DateTime")
        .reset_index(drop=True)
    )


def load_patient_add_events(source) -> List["pd.Timestamp"]:
    """Times of the device's **"Add New Patient"** log rows — each marks a patient
    handover, so they split a reused device's log into per-patient segments.

    Returns a sorted list of timestamps (empty when the source is falsy or has no
    such rows). Matched case-insensitively on the trimmed ``Alarm`` text.
    """
    if source is None:
        return []
    df = read_ventilator_csv(source, "Alarm")
    if "Alarm" not in df.columns or "Date" not in df.columns:
        return []
    df["DateTime"] = parse_datetimes(df["Date"], dayfirst=False)
    df = df.dropna(subset=["DateTime"])
    mask = df["Alarm"].astype(str).str.strip().str.lower() == "add new patient"
    return sorted(df.loc[mask, "DateTime"].tolist())


def alarm_types_in(df: pd.DataFrame, start, end) -> List[str]:
    """Alarm types occurring in [start, end), ordered by ALARM_COLORS."""
    if df is None or df.empty:
        return []
    win = df[(df["DateTime"] >= start) & (df["DateTime"] < end)]
    present = set(win["Alarm"].astype(str).str.strip().str.lower())
    return [a for a in ALARM_COLORS if str(a).lower() in present]
