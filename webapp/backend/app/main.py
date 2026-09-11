"""FastAPI app: upload cyclic/log CSVs, get back the same JSON payload the
static ``charts.html`` report embeds — reusing ``wa_report.cyclic_report``'s
parsing/data-prep code untouched, so this app can't drift from what the
Streamlit app + static report already do with the same files.

Run (from the repo root, with the ``wp`` conda env active):
    uvicorn webapp.backend.app.main:app --reload --port 8000

(Repo root is added to ``sys.path`` below so ``import wa_report`` works
regardless of the current working directory uvicorn was launched from.)
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import List, Optional

# ---- make the existing wa_report package importable ----
# webapp/backend/app/main.py -> parents[3] is the repo root (contains wa_report/).
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from wa_report.cyclic_report.config import (ALARM_COLORS, DEFAULT_VARIABLES,
                                             MODE_COLOR_PALETTE, VARIABLE_UNITS)
from wa_report.cyclic_report.render_combined import build_payload

app = FastAPI(title="Cyclic Report API", version="0.1.0")

# Vite's default dev server ports (5173) on both localhost and 127.0.0.1.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",  # `vite preview`
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def config():
    """Static lookup data the frontend needs before/without an upload: the
    full candidate Y-axis variable list (+ units + the app's default
    selection) and the colour tables for alarm types / mode swim-lanes."""
    return {
        "allVariables": list(VARIABLE_UNITS.keys()),
        "units": VARIABLE_UNITS,
        "defaultVariables": DEFAULT_VARIABLES,
        "alarmColors": ALARM_COLORS,
        "modeColorPalette": MODE_COLOR_PALETTE,
    }


async def _read_uploads(files: Optional[List[UploadFile]]) -> Optional[list]:
    """UploadFile list -> list of named BytesIO buffers ``read_ventilator_csv``
    (and friends) already know how to consume — same "path or file-like, or a
    list of them" contract the Streamlit app relies on. None/empty -> None,
    so downstream code takes its own "no log file given" path."""
    if not files:
        return None
    out = []
    for f in files:
        data = await f.read()
        if not data:
            continue
        buf = io.BytesIO(data)
        buf.name = f.filename  # some pandas error messages reference .name
        out.append(buf)
    return out or None


@app.post("/api/report")
async def build_report(
    cyclic_files: List[UploadFile] = File(..., description="One or more CyclicData CSV exports"),
    log_files: Optional[List[UploadFile]] = File(None, description="One or more LogData CSV exports (optional)"),
    variables: Optional[str] = Form(None, description="Comma-separated Y-axis variable names; default = app default"),
):
    """Parse the uploaded CSV(s) and return the same ``{payload, meta}`` shape
    the static report's embedded JSON carries — everything the timeline view
    needs to render, in one response, no server-side session state kept
    between requests (mirrors the existing app's stateless per-run model)."""
    cyclic_sources = await _read_uploads(cyclic_files)
    if not cyclic_sources:
        raise HTTPException(400, "At least one Cyclic CSV file is required.")
    log_sources = await _read_uploads(log_files)
    var_list = [v.strip() for v in variables.split(",") if v.strip()] if variables else []

    try:
        payload, meta = build_payload(
            folders=[],  # WhatsApp chat merge is out of scope for this app for now
            cyclic_source=cyclic_sources,
            variables=var_list,
            alarms_source=log_sources,
        )
    except ValueError as e:
        # load_cyclic/read_ventilator_csv raise ValueError for things like a
        # missing DateTime column or no matching variables — those are the
        # user's file, not a server bug, so 400 + the message as-is.
        raise HTTPException(400, str(e)) from e

    # `meta` carries a couple of fields that aren't JSON-safe (a pandas
    # DataFrame, raw Timestamps) and aren't needed client-side — pick only
    # the plain-JSON subset the payload itself doesn't already carry.
    meta_out = {
        "missing": meta["missing"],
        "present": meta["present"],
        "defaultSel": meta["default_sel"],
        "nSamples": meta["n_samples"],
        "nAlarms": meta["n_alarms"],
        "nBursts": meta["n_bursts"],
        "nBurstsDropped": meta["n_bursts_dropped"],
        "nModes": meta["n_modes"],
        "nEvents": meta["n_events"],
        "nLimitChanges": meta["n_limit_changes"],
        "patient": meta["patient"],  # [(label, value), …] preamble pairs
    }
    return {"payload": payload, "meta": meta_out}
