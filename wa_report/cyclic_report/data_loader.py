"""Load the ventilator's cyclic CSV log.

Same contract as the original plotter's ``data_loader.load_cyclic``: read the
CSV, parse ``DateTime`` (day-first), and average duplicate timestamps. Here we
keep only the variables the user chose to plot.
"""

from __future__ import annotations

import re
from typing import List, Sequence, Tuple

import pandas as pd

from .csv_io import parse_datetimes, read_ventilator_csv

_TAG = re.compile(r"<[^>]+>")


def load_modes(source) -> List[Tuple["pd.Timestamp", str]]:
    """Ventilation-mode change points from the cyclic CSV's ``ModeName`` column.

    Returns ``[(datetime, mode_name), …]`` with one entry each time the mode
    changes (so a run of the same mode collapses to its first sample). HTML tags
    in the device's mode names (e.g. ``HF O<sub>2</sub> Therapy``) are stripped.
    Empty list if the column is absent.
    """
    df = read_ventilator_csv(source, "DateTime")
    if "ModeName" not in df.columns or "DateTime" not in df.columns:
        return []
    dt = parse_datetimes(df["DateTime"], dayfirst=True)
    names = df["ModeName"].astype(str).map(lambda s: _TAG.sub("", s).strip())
    d = pd.DataFrame({"dt": dt, "m": names}).dropna(subset=["dt"])
    d = d[(d["m"] != "") & (d["m"].str.lower() != "nan")].sort_values("dt")
    out: List[Tuple["pd.Timestamp", str]] = []
    prev = None
    for t, mode in zip(d["dt"], d["m"]):
        if mode != prev:
            out.append((t.to_pydatetime(), mode))
            prev = mode
    return out


def load_cyclic(source, variables: Sequence[str]) -> Tuple[pd.DataFrame, List[str]]:
    """Read a cyclic CSV (path or file-like) and keep DateTime + *variables*.

    Duplicate timestamps are averaged (the device sometimes logs several rows per
    minute). Returns (dataframe, missing_variable_names).
    """
    df = read_ventilator_csv(source, "DateTime")
    if "DateTime" not in df.columns:
        raise ValueError(
            "This CSV has no 'DateTime' column — is it a Cyclic export? "
            f"Columns found: {', '.join(map(str, df.columns[:8]))}…"
        )
    df["DateTime"] = parse_datetimes(df["DateTime"], dayfirst=True)
    df = df.dropna(subset=["DateTime"])
    if df.empty:
        raise ValueError(
            "The 'DateTime' column couldn't be parsed as dates — check the "
            "timestamp format in this CSV."
        )

    present = [v for v in variables if v in df.columns]
    missing = [v for v in variables if v not in df.columns]
    if not present:
        raise ValueError(
            "None of the selected variables exist in this CSV. "
            f"Missing: {', '.join(missing)}."
        )

    for v in present:
        df[v] = pd.to_numeric(df[v], errors="coerce")

    df = (
        df[["DateTime", *present]]
        .groupby("DateTime", as_index=False)
        .mean(numeric_only=True)
        .sort_values("DateTime")
        .reset_index(drop=True)
    )
    return df, missing
