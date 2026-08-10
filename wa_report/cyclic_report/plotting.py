"""Render one 12-hour window to a PNG.

Analogous to the original plotter's ``plotting.plot_variable``, but produces one
figure *per window* with every chosen variable stacked as a shared-x subplot.
On top it overlays:

  * **photo bursts** — a red dashed vertical line (with a staggered ``HH:MM``
    time label) wherever a burst of images was sent in the chat;
  * **alarms** — an optional top "swim-lane" raster: one row per alarm type,
    coloured dots at each alarm time (scales to hundreds of alarms without
    burying the traces).
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta
from typing import Optional, Sequence

import matplotlib
matplotlib.use("Agg")           # headless: no GUI, safe inside Streamlit
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .alarms import alarm_types_in
from .bursts import BulkEvent
from .config import ALARM_COLORS, LINE_COLOR, MARK_COLOR, VARIABLE_UNITS


def window_title(start: datetime, end: datetime) -> str:
    if start.date() == (end - timedelta(seconds=1)).date():
        return f"{start.strftime('%d/%m/%Y')}  {start.strftime('%H:%M')}–{end.strftime('%H:%M')}"
    return f"{start.strftime('%d/%m/%Y %H:%M')} – {end.strftime('%d/%m/%Y %H:%M')}"


def plot_window(start: datetime, end: datetime, sub: pd.DataFrame,
                variables: Sequence[str], events: Sequence[BulkEvent],
                alarms: Optional[pd.DataFrame] = None, dpi: int = 110) -> bytes:
    """Render one window (stacked subplot per variable, optional alarm lane) to PNG.

    The X axis is the **cyclic sample index** (evenly spaced), so repeated
    timestamps stay distinct and irregular time gaps don't squash the trace. Two
    X axes are drawn: the **sample index** on top (the reference for the cyclic
    data) and the wall-clock **time** on the bottom (the reference for alarms and
    photo bursts, which are mapped onto the index by their timestamp — landing in
    time between the cyclic points that bracket them). A dashed red line + 'HH:MM'
    time label marks each photo burst whose start falls in the window (overlapping
    labels are staggered). When *alarms* is given, a top lane shows each alarm
    type as a coloured row.
    """
    present = [v for v in variables if v in sub.columns]
    n = len(present)
    in_win = [e for e in events if start <= e.start < end]

    # index axis: sample k at position k; a time maps to a fractional index by
    # interpolating within the bracketing samples (== the interactive pages).
    N = len(sub)
    x_idx = np.arange(N)
    _dts_ns = sub["DateTime"].to_numpy().astype("datetime64[ns]").astype("int64")

    def idx_of_time(ts) -> float:
        if N <= 1:
            return 0.0
        t = np.datetime64(pd.Timestamp(ts)).astype("datetime64[ns]").astype("int64")
        if t <= _dts_ns[0]:
            return 0.0
        if t >= _dts_ns[-1]:
            return float(N - 1)
        i = int(np.searchsorted(_dts_ns, t, side="right") - 1)
        i = min(max(i, 0), N - 2)
        span = _dts_ns[i + 1] - _dts_ns[i]
        return i + (t - _dts_ns[i]) / span if span > 0 else float(i)

    # Alarm types occurring in this window (ordered by the palette).
    alarm_rows = alarm_types_in(alarms, start, end)
    has_alarms = bool(alarm_rows)

    # Layout: optional alarm lane on top, then one row per variable.
    lane_h = max(0.6, 0.26 * len(alarm_rows))          # taller with more types
    height_ratios = ([lane_h] if has_alarms else []) + [1.0] * n
    fig_h = (lane_h if has_alarms else 0.0) + 2.3 * n + 0.9

    fig, axes = plt.subplots(
        n + (1 if has_alarms else 0), 1, figsize=(12, fig_h), sharex=True,
        squeeze=False, dpi=dpi, gridspec_kw={"height_ratios": height_ratios},
    )
    col = axes[:, 0]
    alarm_ax = col[0] if has_alarms else None
    var_axes = col[1:] if has_alarms else col

    # ---- Alarm lane (swim-lane raster) ----
    if has_alarms:
        win = alarms[(alarms["DateTime"] >= start) & (alarms["DateTime"] < end)]
        for i, a in enumerate(alarm_rows):
            ev = win[win["Alarm"] == a]
            xs = [idx_of_time(t) for t in ev["DateTime"]]
            alarm_ax.scatter(xs, [i] * len(ev), c=ALARM_COLORS[a],
                             s=18, marker="s", alpha=0.85, edgecolors="none")
        alarm_ax.set_ylim(-0.6, len(alarm_rows) - 0.4)
        alarm_ax.set_yticks(range(len(alarm_rows)))
        alarm_ax.set_yticklabels(alarm_rows, fontsize=7)
        for tick, a in zip(alarm_ax.get_yticklabels(), alarm_rows):
            tick.set_color(ALARM_COLORS[a])
        alarm_ax.tick_params(axis="y", length=0)
        alarm_ax.grid(True, axis="x", linestyle="--", linewidth=0.5, alpha=0.4)
        alarm_ax.set_ylabel("Alarms", fontsize=10, fontweight="bold")
        alarm_ax.margins(x=0)

    # ---- Variable subplots (X = sample index) ----
    for ax, v in zip(var_axes, present):
        ax.plot(x_idx, sub[v].to_numpy(), color=LINE_COLOR, linewidth=1.7,
                drawstyle="steps-mid")
        unit = VARIABLE_UNITS.get(v, "")
        ax.set_ylabel(f"{v}\n({unit})" if unit else v, fontsize=11,
                      fontweight="bold")
        ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.5)
        ax.margins(x=0)

    # ---- Photo-burst vertical lines across every row (at the mapped index) ----
    for ax in col:
        for e in in_win:
            ax.axvline(idx_of_time(e.start), color=MARK_COLOR, linestyle="--",
                       linewidth=1.2, alpha=0.85)

    # ---- X axes: bottom = TIME (labels at chosen index ticks), top = INDEX ----
    x_lo, x_hi = (-0.5, max(0.5, N - 0.5))
    for ax in col:
        ax.set_xlim(x_lo, x_hi)
    n_ticks = min(N, 7) if N > 1 else 1
    tick_idx = [int(round(i * (N - 1) / (n_ticks - 1))) for i in range(n_ticks)] if N > 1 else [0]
    tick_times = pd.to_datetime(sub["DateTime"].to_numpy()[tick_idx])
    # date shown on the first tick and whenever the calendar day rolls over
    labels, prev_day = [], None
    for k, ts in zip(tick_idx, tick_times):
        ts = pd.Timestamp(ts)
        day = ts.date()
        labels.append(ts.strftime("%H:%M:%S") + (f"\n{ts:%d/%m/%Y}" if day != prev_day else ""))
        prev_day = day
    col[-1].set_xticks(tick_idx)
    col[-1].set_xticklabels(labels, fontsize=8)
    col[-1].set_xlabel("Time (HH:MM:SS)", fontsize=11, fontweight="bold")
    # top index axis on the topmost subplot (identity map: position == index)
    secax = col[0].secondary_xaxis("top")
    secax.set_xticks(tick_idx)
    secax.set_xticklabels([str(k) for k in tick_idx], fontsize=8, color="#0a6ebd")
    secax.set_xlabel("Sample index", fontsize=10, fontweight="bold", color="#0a6ebd")

    # ---- Burst time labels above the topmost row, staggered so they never
    #      overlap: greedy assignment to stacked levels by pixel position. ----
    top = col[0]
    fig.canvas.draw()                       # realise the transforms (Agg)
    fs = 8
    pad_px = 34                             # ~ width of an 'HH:MM' label + gap
    step_px = 12                            # vertical gap between stack levels
    level_right: list[float] = []           # rightmost label centre (px) per level
    for e in sorted(in_win, key=lambda ev: ev.start):
        ex = idx_of_time(e.start)
        xpx = top.transData.transform((ex, 0))[0]
        lvl = 0
        while lvl < len(level_right) and xpx - level_right[lvl] < pad_px:
            lvl += 1
        if lvl == len(level_right):
            level_right.append(xpx)
        else:
            level_right[lvl] = xpx
        top.annotate(
            e.start.strftime("%H:%M"),
            xy=(ex, 1.0), xycoords=("data", "axes fraction"),
            xytext=(0, 16 + lvl * step_px), textcoords="offset points",
            ha="center", va="bottom", fontsize=fs, color=MARK_COLOR,
            fontweight="bold", clip_on=False,
        )

    # ---- Title ----
    n_ph = sum(e.count for e in in_win)
    parts = []
    if in_win:
        parts.append(f"{len(in_win)} photo burst(s), {n_ph} image(s)")
    else:
        parts.append("no photo bursts in this window")
    if has_alarms:
        n_al = len(alarms[(alarms["DateTime"] >= start) & (alarms["DateTime"] < end)])
        parts.append(f"{n_al} alarm(s)")
    fig.suptitle(window_title(start, end) + "   ·   " + " · ".join(parts),
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.97))

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()
