"""Split the cyclic timeline into fixed clock-aligned windows.

Where the original plotter used a single hand-set ``CUTOFF`` window, this cuts
the whole log into repeating windows (default 12h: 00:00–12:00, 12:00–24:00) so
each becomes one graph.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Tuple

import pandas as pd


def split_windows(df: pd.DataFrame, hours: int = 12
                  ) -> List[Tuple[datetime, datetime, pd.DataFrame]]:
    """Cut the frame into fixed clock-aligned windows of *hours* (default 12h,
    i.e. 00:00–12:00 and 12:00–24:00). Only windows containing data are returned."""
    if df.empty:
        return []
    step = pd.Timedelta(hours=hours)
    t0 = df["DateTime"].min()
    t1 = df["DateTime"].max()
    midnight = t0.normalize()
    # First boundary at or before the earliest sample.
    cur = midnight + step * int((t0 - midnight) // step)
    out: List[Tuple[datetime, datetime, pd.DataFrame]] = []
    while cur <= t1:
        nxt = cur + step
        sub = df[(df["DateTime"] >= cur) & (df["DateTime"] < nxt)]
        if not sub.empty:
            out.append((cur.to_pydatetime(), nxt.to_pydatetime(), sub))
        cur = nxt
    return out
