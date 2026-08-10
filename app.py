"""Streamlit GUI for wa_report — WhatsApp -> ventilation monitoring report.

A single general page. Upload any combination of:
  * a **WhatsApp export** (.zip) — the chat;
  * the ventilator's **cyclic log(s)** (.csv);
  * the **alarm log(s)** (.csv).

Each accepts several files (stitched together by time). You always get the
interactive cyclic pages (charts / windows / chat / patients); when a WhatsApp
export is included, the printable **Word** report is offered too.

Fully self-contained — no imports from other projects — so it can be deployed as
a single folder.

Run with:
    streamlit run "app.py"
"""

from __future__ import annotations

import io
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


def _show_unexpected(exc: Exception) -> None:
    """Report an unexpected error *with* its traceback, so the failing line is
    visible instead of just the message."""
    st.error(f"Unexpected error: {exc}")
    with st.expander("Show technical details (traceback)"):
        st.code("".join(traceback.format_exc()), language="text")

# --- Make the wa_report package importable when run from this folder ---
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from wa_report import media
from wa_report.report import build_report
from wa_report.render_docx import render_docx
from wa_report.render_html import render_html
from wa_report.cyclic_report import (
    DEFAULT_VARIABLES,
    VARIABLE_UNITS,
    build_linked_pages,
)


def _save_uploads_to_tempdir(uploads: list[tuple[str, bytes]], prefix: str) -> Path:
    """Write uploaded ZIP(s) into a fresh temp folder and return it.

    Each file gets an index prefix so two uploads that share a name still land in
    distinct extraction folders. The temp dir is left on disk for the Streamlit
    run so downloads keep working.
    """
    work_dir = Path(tempfile.mkdtemp(prefix=prefix))
    for i, (zip_name, zip_bytes) in enumerate(uploads):
        safe_name = Path(zip_name).name or "chat.zip"
        if not safe_name.lower().endswith(".zip"):
            safe_name += ".zip"
        (work_dir / f"{i:02d}_{safe_name}").write_bytes(zip_bytes)
    return work_dir


def _csv_sources(uploads):
    """A CSV uploader's value (list of UploadedFile) -> a source the loaders can
    read: a single BytesIO for one file, a **list** of BytesIO for several (they
    get stitched together by time), or ``None`` when nothing was uploaded."""
    if not uploads:
        return None
    streams = [io.BytesIO(f.getvalue()) for f in uploads]
    return streams[0] if len(streams) == 1 else streams


def build_word_report(uploads, hospital, patient, mode, gap_minutes,
                      buffer_minutes, max_dim, formats):
    """Build the chat report once and render the requested *formats* (subset of
    {"docx", "html"}). Returns {format: Path}. Used for the Word report and — when
    there is no cyclic data — the standalone interactive chat report."""
    work_dir = _save_uploads_to_tempdir(uploads, prefix="wa_report_gui_")
    report = build_report(
        [work_dir], hospital, patient,
        mode=mode, gap_minutes=gap_minutes, buffer_minutes=buffer_minutes,
    )
    cache = media.MediaCache(max_dim=max_dim)
    all_imgs = []
    for c in report.cycles:
        resolved, _ = media.resolve_images(c.photo_names)
        all_imgs.extend(p for p, _dt in resolved)
    if all_imgs:
        cache.prewarm(all_imgs)

    outputs: dict[str, Path] = {}
    if "docx" in formats:
        docx_path = work_dir / "report.docx"
        render_docx(report, docx_path, cache)
        outputs["docx"] = docx_path
    if "html" in formats:
        html_path = work_dir / "report.html"
        render_html(report, html_path, cache)
        outputs["html"] = html_path

    st.session_state["_last_report_meta"] = {
        "chat_count": report.chat_count,
        "cycles": len(report.cycles),
        "photos": report.total_photos,
        "Start Date": report.date_in_str,
        "End Date": report.date_out_str,
    }
    return outputs


# ----------------------------- UI -----------------------------

st.set_page_config(page_title="WA Ventilation Report", page_icon="🫁", layout="centered")
st.title("🫁 WhatsApp → Ventilation Monitoring Report")

st.caption(
    "Upload any combination of a **WhatsApp export** (chat), the ventilator's "
    "**cyclic log(s)**, and the **alarm log(s)** — each box accepts several files, "
    "stitched together by time (overlapping rows are de-duplicated). You get the "
    "interactive pages (cyclic charts, windowed view, chat, patients); when a "
    "WhatsApp export is included, the printable **Word** report is offered too."
)

with st.form("main_form"):
    zip_up = st.file_uploader(
        "WhatsApp export(s) (.zip) — optional; adds the chat page, photo-burst "
        "markers, and enables the Word report",
        type=["zip"], accept_multiple_files=True, key="m_zip",
    )
    cyclic_up = st.file_uploader(
        "Cyclic device log(s) (.csv) — optional; needs a 'DateTime' column "
        "(one or more, stitched by time)",
        type=["csv"], accept_multiple_files=True, key="m_cyc",
    )
    alarm_up = st.file_uploader(
        "Alarm log(s) (.csv) — optional; 'Date' + 'Alarm' columns "
        "(the Log_*.csv; one or more, stitched by time)",
        type=["csv"], accept_multiple_files=True, key="m_alarm",
    )

    c1, c2 = st.columns(2)
    with c1:
        hospital = st.text_input("Hospital name (optional)", value="")
    with c2:
        label = st.text_input("Device name / label (optional)", value="")

    variables = st.multiselect(
        "Variables on the Y axis (cyclic charts)",
        options=list(VARIABLE_UNITS.keys()),
        default=list(DEFAULT_VARIABLES),
        help="Each becomes a stacked panel on the cyclic charts. Units: "
        + ", ".join(f"{k} ({v})" for k, v in VARIABLE_UNITS.items()),
    )

    want_docx = st.checkbox(
        "Also produce the Word (.docx) chat report (only used when a WhatsApp "
        "export is uploaded)",
        value=True,
    )

    with st.expander("Advanced options"):
        a1, a2, a3, a4 = st.columns(4)
        with a1:
            min_photos = st.number_input("Min photos/burst", 1, 50, 3)
        with a2:
            burst_gap = st.number_input("Burst gap (min)", 1, 120, 10)
        with a3:
            window_hours = st.number_input("Window (hours)", 1, 48, 1)
        with a4:
            max_dim = st.number_input("Max image px", 200, 4000, 480, step=40)
        b1, b2 = st.columns(2)
        with b1:
            mode = st.selectbox(
                "Chat grouping mode (Word report)",
                options=["daily", "hourly", "gap"], index=1,
                help="daily = one section per date, hourly = clock windows, "
                "gap = by inactivity.",
            )
        with b2:
            buffer_minutes = st.number_input(
                "Boundary buffer minutes (daily/hourly)", 0, 60, 5)

    submitted = st.form_submit_button("Generate", type="primary")

if submitted:
    has_zip = bool(zip_up)
    has_cyclic = bool(cyclic_up)
    if not has_zip and not has_cyclic:
        st.error("Upload a WhatsApp export (.zip) and/or a cyclic device log (.csv) "
                 "to begin.")
    elif has_cyclic and not variables:
        st.error("Pick at least one variable for the cyclic charts' Y axis.")
    else:
        pages = None
        report_outputs: dict[str, Path] = {}
        spin = ("Building the interactive pages"
                + (" + Word report" if has_zip and want_docx else "")
                + "…") if has_cyclic else "Building the chat report…"
        with st.spinner(spin):
            try:
                folders = []
                if has_zip:
                    zip_dir = _save_uploads_to_tempdir(
                        [(f.name, f.getvalue()) for f in zip_up], prefix="wa_gui_")
                    folders = [zip_dir]

                # 1) interactive cyclic pages — the chat report.html is included
                #    automatically when a WhatsApp export is present.
                if has_cyclic:
                    pages = build_linked_pages(
                        folders, _csv_sources(cyclic_up), variables,
                        hospital=hospital.strip(), device_label=label.strip(),
                        alarms_source=_csv_sources(alarm_up),
                        min_photos=int(min_photos), window_minutes=int(burst_gap),
                        window_hours=int(window_hours), windows_hours=int(window_hours),
                        max_img_dim=int(max_dim), mode=mode,
                        buffer_minutes=int(buffer_minutes),
                    )

                # 2) Word report (and, only when there's no cyclic data, a
                #    standalone interactive chat report — otherwise the chat is
                #    already report.html inside the ZIP above).
                if has_zip:
                    formats = []
                    if want_docx:
                        formats.append("docx")
                    if not has_cyclic:
                        formats.append("html")
                    if formats:
                        report_outputs = build_word_report(
                            uploads=[(f.name, f.getvalue()) for f in zip_up],
                            hospital=hospital.strip() or "—",
                            patient=label.strip() or "—",
                            mode=mode, gap_minutes=int(burst_gap),
                            buffer_minutes=int(buffer_minutes), max_dim=int(max_dim),
                            formats=formats,
                        )
            except ValueError as exc:
                st.error(f"Could not build: {exc}")
            except Exception as exc:  # noqa: BLE001
                _show_unexpected(exc)

        produced = False

        # --- interactive linked pages ---
        if pages:
            produced = True
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for name, html_str in pages.items():
                    zf.writestr(name, html_str)
            sizes = " + ".join(f"{name} ({len(h) // 1024} KB)"
                               for name, h in pages.items())
            n = len(pages)
            st.success(f"Interactive page{'s' if n != 1 else ''} — {n}: {sizes}.")
            st.download_button(
                label="Download the interactive pages (.zip)",
                data=buf.getvalue(), file_name="linked_report.zip",
                mime="application/zip",
            )
            st.caption(
                "Preview of the stock overview (charts.html). Its cross-links to the "
                "windowed / chat / patient pages work once the ZIP is extracted into "
                "one folder."
            )
            components.html(pages["charts.html"], height=760, scrolling=True)

        # --- Word report ---
        if "docx" in report_outputs:
            produced = True
            meta = st.session_state.get("_last_report_meta", {})
            if meta:
                st.success(
                    f"Word report — {meta['chat_count']} chat(s), {meta['cycles']} "
                    f"cycle(s), {meta['photos']} photo(s), {meta['Start Date']} → "
                    f"{meta['End Date']}."
                )
            st.download_button(
                label="Download Word report (.docx)",
                data=report_outputs["docx"].read_bytes(), file_name="report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        # --- standalone interactive chat report (only when there's no cyclic) ---
        if "html" in report_outputs:
            produced = True
            html_bytes = report_outputs["html"].read_bytes()
            st.download_button(
                label="Download interactive chat report (.html)",
                data=html_bytes, file_name="report.html", mime="text/html",
            )
            with st.expander("Preview interactive chat report", expanded=True):
                components.html(html_bytes.decode("utf-8"), height=720, scrolling=True)

        if not produced:
            st.warning(
                "Nothing was produced. Add a cyclic CSV for the interactive charts, "
                "or a WhatsApp export for the chat/Word report."
            )
