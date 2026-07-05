"""Streamlit GUI for wa_report — WhatsApp -> ventilation monitoring report.

Upload a WhatsApp export .zip, optionally enter the hospital and patient names
(all optional), generate a Word (.docx) report, and download it. Fully
self-contained — no imports from other projects — so it can be deployed as a
single folder.

Run with:
    streamlit run "app.py"
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import streamlit as st

# --- Make the wa_report package importable when run from this folder ---
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from wa_report import media
from wa_report.report import build_report
from wa_report.render_docx import render_docx


def generate_docx(
    uploads: list[tuple[str, bytes]],
    hospital: str,
    patient: str,
    mode: str,
    gap_minutes: int,
    buffer_minutes: int,
    max_dim: int,
) -> Path:
    """Extract the upload(s), build the report, render a single .docx, return its path.

    Multiple ZIPs are dropped into one folder; build_report extracts each into its
    own subfolder and merges every chat into a single timeline sorted by time
    (identical transcripts are de-duplicated). The temp dir is intentionally left
    on disk for the duration of the Streamlit run so the file can be downloaded.
    """
    work_dir = Path(tempfile.mkdtemp(prefix="wa_report_gui_"))
    # build_report auto-extracts WhatsApp .zip exports found in the folder.
    for i, (zip_name, zip_bytes) in enumerate(uploads):
        safe_name = Path(zip_name).name or "chat.zip"
        if not safe_name.lower().endswith(".zip"):
            safe_name += ".zip"
        # Prefix keeps each upload's extraction folder distinct even if two
        # uploads share the same filename.
        (work_dir / f"{i:02d}_{safe_name}").write_bytes(zip_bytes)

    report = build_report(
        [work_dir],
        hospital,
        patient,
        mode=mode,
        gap_minutes=gap_minutes,
        buffer_minutes=buffer_minutes,
    )

    # Pre-process every image once; the renderer reuses the cache.
    cache = media.MediaCache(max_dim=max_dim)
    all_imgs = []
    for c in report.cycles:
        resolved, _ = media.resolve_images(c.photo_names)
        all_imgs.extend(p for p, _dt in resolved)
    if all_imgs:
        cache.prewarm(all_imgs)

    docx_path = work_dir / "report.docx"
    render_docx(report, docx_path, cache)

    st.session_state["_last_report_meta"] = {
        "chat_count": report.chat_count,
        "cycles": len(report.cycles),
        "photos": report.total_photos,
        "Start Date": report.date_in_str,
        "End Date": report.date_out_str,
    }
    return docx_path


# ----------------------------- UI -----------------------------

st.set_page_config(page_title="WA Ventilation Report", page_icon="🫁", layout="centered")
st.title("🫁 WhatsApp → Ventilation Monitoring Report")
st.caption(
    "Upload one or more WhatsApp export ZIPs — multiple chats are merged into a "
    "single timeline. Hospital and patient names are optional. Generate a Word "
    "(.docx) report and download it."
)

with st.form("report_form"):
    uploaded = st.file_uploader(
        "WhatsApp export(s) (.zip)", type=["zip"], accept_multiple_files=True
    )

    col1, col2 = st.columns(2)
    with col1:
        hospital = st.text_input("Hospital name (optional)", value="")
    with col2:
        patient = st.text_input("Device name / ID (optional)", value="")

    with st.expander("Advanced options"):
        mode = st.selectbox(
            "Grouping mode",
            options=["daily", "hourly", "gap"],
            index=0,
            help="daily = one section per date, hourly = clock windows, gap = by inactivity.",
        )
        gap_minutes = st.number_input(
            "Gap minutes (gap mode)", min_value=1, max_value=240, value=15
        )
        buffer_minutes = st.number_input(
            "Boundary buffer minutes (daily/hourly)", min_value=0, max_value=60, value=3
        )
        max_dim = st.number_input(
            "Max image dimension (px)", min_value=200, max_value=4000, value=1000, step=100
        )

    submitted = st.form_submit_button("Generate report", type="primary")

if submitted:
    if not uploaded:
        st.error("Please upload at least one WhatsApp export ZIP file first.")
    else:
        hospital_val = hospital.strip() or "—"
        patient_val = patient.strip() or "—"
        docx_path: Path | None = None
        with st.spinner("Generating report…"):
            try:
                docx_path = generate_docx(
                    uploads=[(f.name, f.getvalue()) for f in uploaded],
                    hospital=hospital_val,
                    patient=patient_val,
                    mode=mode,
                    gap_minutes=int(gap_minutes),
                    buffer_minutes=int(buffer_minutes),
                    max_dim=int(max_dim),
                )
            except ValueError as exc:
                st.error(f"Could not build the report: {exc}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Unexpected error: {exc}")

        if docx_path and docx_path.exists():
            meta = st.session_state.get("_last_report_meta", {})
            if meta:
                st.success(
                    f"Done — {meta['chat_count']} chat(s), {meta['cycles']} cycle(s), "
                    f"{meta['photos']} photo(s), {meta['Start Date']} → {meta['End Date']}."
                )

            st.subheader("Download")
            st.download_button(
                label="Download Word report (.docx)",
                data=docx_path.read_bytes(),
                file_name="report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
