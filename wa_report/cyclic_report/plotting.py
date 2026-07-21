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
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
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

    A dashed red line + 'HH:MM' time label marks each photo burst whose start
    falls in the window (overlapping labels are staggered onto stacked levels).
    When *alarms* is given, a top lane shows each alarm type as a coloured row.
    """
    present = [v for v in variables if v in sub.columns]
    n = len(present)
    in_win = [e for e in events if start <= e.start < end]

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
            alarm_ax.scatter(ev["DateTime"], [i] * len(ev), c=ALARM_COLORS[a],
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

    # ---- Variable subplots ----
    for ax, v in zip(var_axes, present):
        ax.plot(sub["DateTime"], sub[v], color=LINE_COLOR, linewidth=1.7,
                drawstyle="steps-mid")
        unit = VARIABLE_UNITS.get(v, "")
        ax.set_ylabel(f"{v}\n({unit})" if unit else v, fontsize=11,
                      fontweight="bold")
        ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.5)
        ax.margins(x=0)

    # ---- Photo-burst vertical lines across every row ----
    for ax in col:
        for e in in_win:
            ax.axvline(e.start, color=MARK_COLOR, linestyle="--",
                       linewidth=1.2, alpha=0.85)

    # X-axis limits/format first, so the label packing below sees final pixels.
    col[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    col[-1].set_xlabel("Time (HH:MM)", fontsize=11, fontweight="bold")
    col[-1].set_xlim(start, end)

    # ---- Burst time labels above the topmost row, staggered so they never
    #      overlap: greedy assignment to stacked levels by pixel position. ----
    top = col[0]
    fig.canvas.draw()                       # realise the transforms (Agg)
    fs = 8
    pad_px = 34                             # ~ width of an 'HH:MM' label + gap
    step_px = 12                            # vertical gap between stack levels
    level_right: list[float] = []           # rightmost label centre (px) per level
    for e in sorted(in_win, key=lambda ev: ev.start):
        xpx = top.transData.transform((mdates.date2num(e.start), 0))[0]
        lvl = 0
        while lvl < len(level_right) and xpx - level_right[lvl] < pad_px:
            lvl += 1
        if lvl == len(level_right):
            level_right.append(xpx)
        else:
            level_right[lvl] = xpx
        top.annotate(
            e.start.strftime("%H:%M"),
            xy=(e.start, 1.0), xycoords=("data", "axes fraction"),
            xytext=(0, 4 + lvl * step_px), textcoords="offset points",
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
