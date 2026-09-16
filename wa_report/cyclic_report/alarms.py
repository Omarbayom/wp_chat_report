"""Load the ventilator's alarm log (the ``Log_*.csv`` export).

Plays the role of the original plotter's ``load_alarms`` + ``filter_alarms`` +
``parse_alarms_datetime``: read the CSV, parse the ``Date`` column, and keep only
the alarm types we colour (see ``config.ALARM_COLORS``).

Note the alarm ``Date`` is ISO (``YYYY-MM-DD HH:MM:SS``), unlike the cyclic
``DateTime`` which is day-first (``DD/MM/YYYY HH:MM``) — so this parser does *not*
force day-first.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

import pandas as pd

from .config import ALARM_COLORS
from .csv_io import parse_datetimes, read_ventilator_csv

_LIMIT_SUFFIX = re.compile(r"\s+(Min|Max)$")


def load_alarms(source, date_order: "bool | None" = None) -> pd.DataFrame:
    """Read an alarm Log CSV (path or file-like) -> DataFrame[DateTime, Alarm].

    Keeps only alarms present in ``ALARM_COLORS`` and sorts by time. Returns an
    empty (but correctly-typed) frame when *source* is falsy or has no usable
    rows, so callers can treat "no alarms" uniformly. *date_order*: ``None``
    auto-detects (the default); ``True``/``False`` forces day-first/month-first
    for an ambiguous (non-ISO) ``Date`` column — see ``csv_io.parse_datetimes``.
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

    df["DateTime"] = parse_datetimes(df["Date"], dayfirst=False, force=date_order)
    df = df.dropna(subset=["DateTime"])
    df = df[df["Alarm"].isin(ALARM_COLORS)]
    if df.empty:
        return empty
    return (
        df[["DateTime", "Alarm"]]
        .sort_values("DateTime")
        .reset_index(drop=True)
    )


def load_alarm_intervals(source, date_order: "bool | None" = None) -> pd.DataFrame:
    """Pair each alarm's **Activated → Deactivated** rows into active intervals.

    The device logs an alarm as two rows sharing the same ``Alarm`` name with a
    ``Status`` of ``Activated`` then ``Deactivated``; the alarm is "on" in between.
    Returns ``DataFrame[Start, End, Alarm]`` (only alarms in ``ALARM_COLORS``).

    Rules:
      * a ``Deactivated`` with no open ``Activated`` is ignored (orphan);
      * an alarm still open when an **"EzVent Started Successfully"** row appears
        (the device restarted after a forced shutdown) is force-closed at the
        **last logged row of the session that is ending** — i.e. when the device
        actually stopped logging, not at the restart itself (which can follow a
        long device-off gap). This keeps an alarm bar from spanning the dead
        period between a forced shutdown and the next start-up;
      * anything still open at the end of the log is closed at the last log time;
      * a re-``Activated`` while already open keeps the earlier start.
    """
    empty = pd.DataFrame({"Start": pd.to_datetime([]), "End": pd.to_datetime([]),
                          "Alarm": pd.Series([], dtype="object")})
    if source is None:
        return empty
    df = read_ventilator_csv(source, "Alarm")
    if "Alarm" not in df.columns or "Date" not in df.columns:
        return empty
    df["DateTime"] = parse_datetimes(df["Date"], dayfirst=False, force=date_order)
    # stable sort so same-second rows keep their in-file order — deterministic
    # even when several log files are stitched together (multi-file upload)
    df = df.dropna(subset=["DateTime"]).sort_values("DateTime", kind="stable")
    if df.empty:
        return empty

    status = (df["Status"].astype(str).str.strip().str.lower()
              if "Status" in df.columns else pd.Series([""] * len(df), index=df.index))
    names = df["Alarm"].astype(str).str.strip()
    is_alarm = df["Alarm"].isin(ALARM_COLORS)
    is_restart = names.str.lower() == "ezvent started successfully"
    end_time = df["DateTime"].max()

    active: dict = {}          # alarm name -> start time (still open)
    rows: List[tuple] = []
    prev_dt = None             # timestamp of the previous log row (the session's last)
    for dt, alarm, st, isa, isr in zip(df["DateTime"], df["Alarm"], status, is_alarm, is_restart):
        if isr:                # device restart -> close open alarms at the ending
            # session's LAST logged row (prev_dt), not at the restart time, so the
            # bar doesn't stretch across the device-off gap before this start-up.
            close_t = prev_dt if prev_dt is not None else dt
            for typ, t0 in active.items():
                rows.append((t0, max(t0, close_t), typ))
            active.clear()
        elif isa:
            if st == "activated":
                active.setdefault(alarm, dt)
            elif st == "deactivated":
                if alarm in active:
                    rows.append((active.pop(alarm), dt, alarm))
            else:              # alarm row with no Activated/Deactivated -> instant
                rows.append((dt, dt, alarm))
        prev_dt = dt           # remember this row as the session's last-so-far
    for typ, t0 in active.items():
        rows.append((t0, end_time, typ))

    if not rows:
        return empty
    return (
        pd.DataFrame(rows, columns=["Start", "End", "Alarm"])
        .sort_values("Start")
        .reset_index(drop=True)
    )


def load_log_events(source, date_order: "bool | None" = None) -> pd.DataFrame:
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
    df["DateTime"] = parse_datetimes(df["Date"], dayfirst=False, force=date_order)
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


_MODE_RE = re.compile(r"mode", re.I)
_LOG_META_COLS = {"id", "date", "alarm", "status"}


def _native(v):
    """A numpy scalar (int64/float64/bool_/...) -> the equivalent plain
    Python value, so it's JSON-serialisable; anything else is passed through
    unchanged."""
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            pass
    return v


def _row_settings(row: "pd.Series") -> dict:
    """One Log row (minus the identity columns) -> a dict of its non-blank
    values, in column order."""
    out: dict = {}
    for k, v in row.items():
        if v is None:
            continue
        if isinstance(v, float) and pd.isna(v):
            continue
        if isinstance(v, str):
            v = v.strip()
            if not v:
                continue
        out[k] = _native(v)
    return out


def load_log_entries(source, date_order: "bool | None" = None) -> pd.DataFrame:
    """Every **non-alarm** Log row, classified as a *mode* or a plain
    *event*, each carrying a settings snapshot.

    A row is a **mode** entry when its text mentions "mode" (case-insensitive)
    — e.g. ``"Change A/C-VC Mode Setting"``, ``"Start NIV A/C-PC Mode"``,
    ``"Standby Mode Activated"``, ``"Diagnostic mode active"`` — anything
    else non-alarm is an **event** (``"Maintenance Settings Updated"``,
    ``"Add New Patient"``, …).

    Every Log row carries the device's full state alongside its own text: the
    active ``Mode``, every "set" parameter (``PIP``, ``RR``, ``PEEP``,
    ``FIO2``, ``VT``, …), the alarm-limit columns, and the simultaneous
    cyclic readings (``Cyc. *``) — whichever of those a given export has.
    ``Settings`` is a dict of every column **other than** the identity
    columns (``Id``/``Date``/``Alarm``/``Status``) that's non-blank on that
    row — not a hard-coded column list, so a different device/firmware's
    column set still works.

    **The ``Cyc. *`` columns are blank on most rows — this is the device's
    own behaviour, not a gap in this reader.** Checked against a real export
    (`test/LogData 28-07-2026 114304.csv`): of 709 non-alarm rows across 48
    distinct event types, only ``"Standby Mode Activated"`` ever carries a
    non-blank ``Cyc. *`` snapshot (43 of its 117 occurrences do; every other
    type — mode changes/confirmations, battery events, screen lock/unlock,
    "View Logs", circuit checks, …  — is 0 for 0). Reasonable to read as
    deliberate: Standby is the moment active ventilation stops, so recording
    the last live reading right at that transition is a meaningful
    checkpoint in a way most other logged actions aren't.

    Returns ``DataFrame[DateTime, Text, Kind, Settings]`` sorted by time
    (``Kind`` is ``"mode"``/``"event"``); an empty (but correctly-typed)
    frame when *source* is falsy or unreadable.
    """
    empty = pd.DataFrame({
        "DateTime": pd.to_datetime([]), "Text": pd.Series([], dtype="object"),
        "Kind": pd.Series([], dtype="object"), "Settings": pd.Series([], dtype="object"),
    })
    if source is None:
        return empty
    df = read_ventilator_csv(source, "Alarm")
    if "Alarm" not in df.columns or "Date" not in df.columns:
        return empty
    df["DateTime"] = parse_datetimes(df["Date"], dayfirst=False, force=date_order)
    df = df.dropna(subset=["DateTime"])
    df = df[~df["Alarm"].isin(ALARM_COLORS)]
    text = df["Alarm"].astype(str).str.strip()
    df = df[text != ""]
    if df.empty:
        return empty
    text = df["Alarm"].astype(str).str.strip()
    kind = text.str.contains(_MODE_RE).map({True: "mode", False: "event"})
    cols = [c for c in df.columns if c.strip().lower() not in _LOG_META_COLS and c != "DateTime"]
    settings = df[cols].apply(_row_settings, axis=1) if cols else pd.Series([{}] * len(df), index=df.index)
    out = pd.DataFrame({"DateTime": df["DateTime"], "Text": text, "Kind": kind, "Settings": settings})
    return out.sort_values("DateTime", kind="stable").reset_index(drop=True)


def load_alarm_limits(
    source, date_order: "bool | None" = None
) -> List[Tuple["pd.Timestamp", Dict[str, list]]]:
    """Alarm-limit snapshots from the Log CSV's ``"<Var> Min"``/``"<Var> Max"``
    columns (e.g. ``"PIP Max"``, ``"PEEP Min"``, ``"PEEP Max"``, ``"RR Min"``,
    ``"RR Max"``, ``"MVe Min"``, ``"MVe Max"``, ``"ApneaTime Max"`` — whichever
    the export carries; detected by column name, not hard-coded, so a different
    export's limit columns still work).

    Only the device's own **"Alarm Limits Change"** rows are used. Every Log row
    echoes *some* copy of these columns, but it is not a meaningful time series —
    two rows logged the same second for different alarm types (e.g. a battery
    alarm vs. a power alarm) can carry two different limit sets even though
    nothing was actually reconfigured. "Alarm Limits Change" is the row the
    device itself writes when a limit is genuinely (re)set, so only those are
    collapsed to one entry per **change** (like ``load_modes``):
    ``[(datetime, {var: [min_or_None, max_or_None], ...}), …]``. Empty when the
    Log CSV has none of these columns or no such rows.
    """
    if source is None:
        return []
    df = read_ventilator_csv(source, "Alarm")
    limit_cols = [c for c in df.columns if _LIMIT_SUFFIX.search(str(c))]
    if "Date" not in df.columns or "Alarm" not in df.columns or not limit_cols:
        return []
    by_var: Dict[str, Dict[str, str]] = {}
    for c in limit_cols:
        m = _LIMIT_SUFFIX.search(c)
        base, kind = c[:m.start()].strip(), m.group(1).lower()
        by_var.setdefault(base, {})[kind] = c

    mask = df["Alarm"].astype(str).str.strip().str.lower() == "alarm limits change"
    df = df[mask]
    if df.empty:
        return []
    df["DateTime"] = parse_datetimes(df["Date"], dayfirst=False, force=date_order)
    df = df.dropna(subset=["DateTime"]).sort_values("DateTime", kind="stable")
    if df.empty:
        return []
    for c in limit_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    out: List[Tuple["pd.Timestamp", Dict[str, list]]] = []
    prev = None
    for _, row in df.iterrows():
        snap: Dict[str, list] = {}
        for base, kinds in by_var.items():
            mn = row[kinds["min"]] if "min" in kinds else None
            mx = row[kinds["max"]] if "max" in kinds else None
            mn = None if mn is None or pd.isna(mn) else float(mn)
            mx = None if mx is None or pd.isna(mx) else float(mx)
            if mn is not None or mx is not None:
                snap[base] = [mn, mx]
        if snap and snap != prev:
            out.append((row["DateTime"].to_pydatetime(), snap))
            prev = snap
    return out


def load_patient_add_events(source, date_order: "bool | None" = None) -> List["pd.Timestamp"]:
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
    df["DateTime"] = parse_datetimes(df["Date"], dayfirst=False, force=date_order)
    df = df.dropna(subset=["DateTime"])
    mask = df["Alarm"].astype(str).str.strip().str.lower() == "add new patient"
    return sorted(df.loc[mask, "DateTime"].tolist())
