"""Robust reader for the ventilator's CSV exports.

Real device exports vary: some have **preamble/metadata lines before the header**
(so pandas would lock onto the wrong header), use a **different delimiter**
(``;`` or tab, common with European Excel), carry a **BOM**, or have **ragged
rows**. This reader:

  * accepts a path or a file-like object (bytes or text),
  * finds the real header row by a key column name (e.g. ``DateTime``),
  * sniffs the delimiter from that header line,
  * skips the preamble and tolerates ragged/short rows.

Falls back gracefully to a plain read when the file is already well-formed.
"""

from __future__ import annotations

import io

import pandas as pd

_DELIMS = [",", ";", "\t", "|"]


def _to_text(source) -> str:
    """Return the whole CSV as text, from a path or a (bytes/text) file-like."""
    if hasattr(source, "read"):
        data = source.read()
        if isinstance(data, bytes):
            return data.decode("utf-8-sig", errors="replace")
        return data
    with open(source, "r", encoding="utf-8-sig", errors="replace") as fh:
        return fh.read()


def read_ventilator_csv(source, key_col: str) -> pd.DataFrame:
    """Read a device CSV, locating the header row that contains *key_col*.

    Preamble lines above the header are skipped, the delimiter is inferred from
    the header line, and bad (ragged) data rows are dropped rather than raising.
    """
    text = _to_text(source)
    lines = text.splitlines()

    # First line that mentions the key column is the real header.
    header_idx = 0
    for i, ln in enumerate(lines):
        if key_col.lower() in ln.lower():
            header_idx = i
            break

    header_line = lines[header_idx] if lines else ""
    # Delimiter = the candidate that appears most on the header line.
    delim = max(_DELIMS, key=header_line.count)
    if header_line.count(delim) == 0:
        delim = ","

    df = pd.read_csv(
        io.StringIO(text), skiprows=header_idx, sep=delim,
        engine="python", on_bad_lines="skip",
    )
    df.columns = [str(c).strip() for c in df.columns]
    return df


def parse_datetimes(s: "pd.Series", dayfirst: bool = True) -> "pd.Series":
    """Parse a timestamp column, auto-recovering the day/month order.

    Tries *dayfirst* first; if that leaves many values unparsed, tries the other
    order and keeps whichever parses more. Handles ISO, ``DD/MM/YYYY`` and
    ``MM/DD/YYYY`` exports without the caller having to know which it is.
    """
    a = pd.to_datetime(s, errors="coerce", dayfirst=dayfirst)
    if a.isna().mean() > 0.3:
        b = pd.to_datetime(s, errors="coerce", dayfirst=not dayfirst)
        if b.notna().sum() > a.notna().sum():
            return b
    return a
