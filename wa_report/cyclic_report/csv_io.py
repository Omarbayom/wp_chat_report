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
import re
import warnings

import pandas as pd

_DELIMS = [",", ";", "\t", "|"]


def _to_text(source) -> str:
    """Return the whole CSV as text, from a path or a (bytes/text) file-like.

    Seekable file-likes are rewound first, so the same upload (e.g. a
    ``BytesIO``) can be read more than once — several pages share one source.
    """
    if hasattr(source, "read"):
        if hasattr(source, "seek"):
            try:
                source.seek(0)
            except (OSError, ValueError):
                pass
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

    *source* may also be a **list/tuple of sources** (several uploaded files) —
    each is read independently (each keeps its own preamble/delimiter) and the
    rows are concatenated; callers sort by time afterwards, so file order and
    small column differences don't matter.
    """
    if isinstance(source, (list, tuple)):
        frames = [read_ventilator_csv(s, key_col) for s in source]
        frames = [f for f in frames if f is not None and not f.empty]
        if not frames:
            return pd.DataFrame()
        merged = pd.concat(frames, ignore_index=True, sort=False)
        # De-overlap: separate exports from one device can share rows where their
        # time ranges overlap. The device's per-row **Id** is unique, so identical
        # Ids across files are the SAME row re-exported (not a genuine
        # repeated-timestamp sample, which carries a different Id) — collapse them,
        # the **later file winning** (keep="last") so a re-export overrides.
        if "Id" in merged.columns:
            merged = merged.drop_duplicates(subset="Id", keep="last")
        else:
            merged = merged.drop_duplicates(keep="last")
        return merged.reset_index(drop=True)
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


_ISO_RE = re.compile(r"^\s*\d{4}-\d{1,2}-\d{1,2}")


def parse_datetimes(s: "pd.Series", dayfirst: bool = True) -> "pd.Series":
    """Parse a timestamp column, auto-recovering the day/month order.

    ISO timestamps (``YYYY-MM-DD HH:MM:SS``) have an unambiguous day/month order,
    so they are parsed without ``dayfirst`` — passing it would make pandas warn
    that it's being ignored. For slash-style dates we try *dayfirst* first and, if
    that leaves many values unparsed, the other order, keeping whichever parses
    more. Handles ISO, ``DD/MM/YYYY`` and ``MM/DD/YYYY`` exports transparently.
    """
    sample = s.dropna().astype(str).head(20)
    looks_iso = len(sample) > 0 and sample.str.match(_ISO_RE).mean() > 0.5
    if looks_iso:
        return pd.to_datetime(s, errors="coerce")

    # We deliberately probe both day/month orders and keep the better one, so
    # pandas' "dayfirst was specified" advisory is expected noise — silence it.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        a = pd.to_datetime(s, errors="coerce", dayfirst=dayfirst)
        if a.isna().mean() > 0.3:
            b = pd.to_datetime(s, errors="coerce", dayfirst=not dayfirst)
            if b.notna().sum() > a.notna().sum():
                return b
        return a
