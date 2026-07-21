"""Streamlit GUI for wa_report — WhatsApp -> ventilation monitoring report.

Two tabs:
  1. **Ventilation report** — upload a WhatsApp export .zip, optionally enter the
     hospital and device names, generate a Word (.docx) / interactive HTML report.
  2. **Cyclic ↔ photo timeline** — upload the same chat plus the ventilator's
     cyclic CSV log; the app cuts the log into 12-hour windows, plots the chosen
     variables, and marks where bursts of "bulky images" were sent in the chat.

Fully self-contained — no imports from other projects — so it can be deployed as
a single folder.

Run with:
    streamlit run "app.py"
"""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

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
    build_cyclic_report,
    build_linked_pages,
    render_cyclic_html,
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


def generate_reports(
    uploads: list[tuple[str, bytes]],
    hospital: str,
    patient: str,
    mode: str,
    gap_minutes: int,
    buffer_minutes: int,
    max_dim: int,
    formats: list[str],
) -> dict[str, Path]:
    """Extract the upload(s), build the report once, render the requested formats.

    *formats* is any subset of {"docx", "html"}. Returns a mapping of format ->
    output file path.

    Multiple ZIPs are dropped into one folder; build_report extracts each into its
    own subfolder and merges every chat into a single timeline sorted by time
    (identical transcripts are de-duplicated). The temp dir is intentionally left
    on disk for the duration of the Streamlit run so the files can be downloaded.
    """
    work_dir = _save_uploads_to_tempdir(uploads, prefix="wa_report_gui_")

    report = build_report(
        [work_dir],
        hospital,
        patient,
        mode=mode,
        gap_minutes=gap_minutes,
        buffer_minutes=buffer_minutes,
    )

    # Pre-process every image once; both renderers reuse the cache.
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

_FORMAT_KEYS = {"Word (.docx)": "docx", "Interactive HTML": "html"}

tab_report, tab_cyclic, tab_combined = st.tabs(
    ["📄 Ventilation report", "📈 Cyclic ↔ photo timeline",
     "🔗 Linked interactive pages"]
)


# ========================= Tab 1: ventilation report =========================
with tab_report:
    st.caption(
        "Upload one or more WhatsApp export ZIPs — multiple chats are merged into "
        "a single timeline. Hospital and device names are optional. Generate a Word "
        "(.docx) report and/or an interactive HTML report and download it."
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

        output_formats = st.multiselect(
            "Output format",
            options=["Word (.docx)", "Interactive HTML"],
            default=["Interactive HTML"],
            help="Interactive HTML opens in any browser — search the chat and filter "
            "by day, hour, and sender. Word (.docx) is the printable document.",
        )

        with st.expander("Advanced options"):
            mode = st.selectbox(
                "Grouping mode",
                options=["daily", "hourly", "gap"],
                index=1,
                help="daily = one section per date, hourly = clock windows, gap = by inactivity.",
            )
            gap_minutes = st.number_input(
                "Gap minutes (gap mode)", min_value=1, max_value=240, value=15
            )
            buffer_minutes = st.number_input(
                "Boundary buffer minutes (daily/hourly)", min_value=0, max_value=60, value=5
            )
            max_dim = st.number_input(
                "Max image dimension (px)", min_value=200, max_value=4000, value=1000, step=100
            )

        submitted = st.form_submit_button("Generate report", type="primary")

    if submitted:
        if not uploaded:
            st.error("Please upload at least one WhatsApp export ZIP file first.")
        elif not output_formats:
            st.error("Please pick at least one output format.")
        else:
            hospital_val = hospital.strip() or "—"
            patient_val = patient.strip() or "—"
            formats = [_FORMAT_KEYS[f] for f in output_formats]
            outputs: dict[str, Path] = {}
            with st.spinner("Generating report…"):
                try:
                    outputs = generate_reports(
                        uploads=[(f.name, f.getvalue()) for f in uploaded],
                        hospital=hospital_val,
                        patient=patient_val,
                        mode=mode,
                        gap_minutes=int(gap_minutes),
                        buffer_minutes=int(buffer_minutes),
                        max_dim=int(max_dim),
                        formats=formats,
                    )
                except ValueError as exc:
                    st.error(f"Could not build the report: {exc}")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Unexpected error: {exc}")

            if outputs:
                meta = st.session_state.get("_last_report_meta", {})
                if meta:
                    st.success(
                        f"Done — {meta['chat_count']} chat(s), {meta['cycles']} cycle(s), "
                        f"{meta['photos']} photo(s), {meta['Start Date']} → {meta['End Date']}."
                    )

                st.subheader("Download")
                if "docx" in outputs:
                    st.download_button(
                        label="Download Word report (.docx)",
                        data=outputs["docx"].read_bytes(),
                        file_name="report.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                if "html" in outputs:
                    html_bytes = outputs["html"].read_bytes()
                    st.download_button(
                        label="Download interactive report (.html)",
                        data=html_bytes,
                        file_name="report.html",
                        mime="text/html",
                    )
                    with st.expander("Preview interactive report", expanded=True):
                        components.html(
                            html_bytes.decode("utf-8"), height=720, scrolling=True
                        )


# ===================== Tab 2: cyclic ↔ photo timeline ========================
with tab_cyclic:
    st.caption(
        "Overlay the times **bursts of photos** were sent in the chat onto the "
        "ventilator's own **cyclic log**. The log is split into 12-hour windows — "
        "one graph each — and a red marker is drawn wherever a photo burst falls "
        "inside the window. Pair a chat with the CSV exported from the **same "
        "device and dates** so the two line up in time."
    )

    with st.form("cyclic_form"):
        cyc_uploaded = st.file_uploader(
            "WhatsApp export(s) (.zip) — for the photo-send times",
            type=["zip"],
            accept_multiple_files=True,
            key="cyc_zip",
        )
        cyclic_csv = st.file_uploader(
            "Cyclic device log (.csv) — must have a 'DateTime' column",
            type=["csv"],
            accept_multiple_files=False,
            key="cyc_csv",
        )
        alarm_csv = st.file_uploader(
            "Alarm log (.csv) — optional; 'Date' + 'Alarm' columns (the Log_*.csv)",
            type=["csv"],
            accept_multiple_files=False,
            key="cyc_alarm",
            help="If provided, an alarm lane is drawn above the graphs — one "
            "coloured row per alarm type, marked at each alarm time.",
        )

        variables = st.multiselect(
            "Variables on the Y axis",
            options=list(VARIABLE_UNITS.keys()),
            default=list(DEFAULT_VARIABLES),
            help="Each selected variable becomes a stacked sub-plot sharing the "
            "same time axis. Units: "
            + ", ".join(f"{k} ({v})" for k, v in VARIABLE_UNITS.items()),
        )

        device_label = st.text_input("Report title / device label (optional)", value="")

        with st.expander("Advanced options"):
            c1, c2, c3 = st.columns(3)
            with c1:
                min_photos = st.number_input(
                    "Min photos per burst", min_value=1, max_value=50, value=3,
                    help="A burst must contain at least this many images to be marked.",
                )
            with c2:
                burst_gap = st.number_input(
                    "Burst gap (minutes)", min_value=1, max_value=120, value=10,
                    help="Photos more than this far apart start a new burst.",
                )
            with c3:
                window_hours = st.number_input(
                    "Window size (hours)", min_value=1, max_value=48, value=12,
                    help="Each graph covers this many clock-hours (default 12).",
                )

        cyc_submitted = st.form_submit_button("Generate timeline", type="primary")

    if cyc_submitted:
        if not cyc_uploaded:
            st.error("Please upload at least one WhatsApp export ZIP.")
        elif cyclic_csv is None:
            st.error("Please upload the cyclic device log CSV.")
        elif not variables:
            st.error("Please pick at least one variable for the Y axis.")
        else:
            with st.spinner("Building cyclic timeline…"):
                try:
                    work_dir = _save_uploads_to_tempdir(
                        [(f.name, f.getvalue()) for f in cyc_uploaded],
                        prefix="wa_cyclic_gui_",
                    )
                    report = build_cyclic_report(
                        [work_dir],
                        io.BytesIO(cyclic_csv.getvalue()),
                        variables,
                        device_label=device_label.strip(),
                        alarms_source=(io.BytesIO(alarm_csv.getvalue())
                                       if alarm_csv is not None else None),
                        min_photos=int(min_photos),
                        window_minutes=int(burst_gap),
                        window_hours=int(window_hours),
                    )
                    cyc_report = report
                except ValueError as exc:
                    cyc_report = None
                    st.error(f"Could not build the timeline: {exc}")
                except Exception as exc:  # noqa: BLE001
                    cyc_report = None
                    st.error(f"Unexpected error: {exc}")

            if cyc_report is not None:
                st.success(
                    f"Done — {len(cyc_report.windows)} window(s), "
                    f"{cyc_report.total_bursts} photo burst(s) mapped, "
                    f"{cyc_report.total_images} image(s) in the chat, "
                    f"{cyc_report.total_alarms} alarm(s) in the log."
                )

                if cyc_report.missing_vars:
                    st.warning(
                        "These variables were not in the CSV and were skipped: "
                        + ", ".join(cyc_report.missing_vars)
                    )
                if cyc_report.total_images and cyc_report.total_bursts == 0:
                    st.warning(
                        "No photo bursts fall inside this log's time range — the "
                        "chat and this cyclic CSV don't overlap in time. Pair the "
                        "chat with a CSV from the same device and dates to see markers. "
                        f"(Log span: {cyc_report.data_start:%d/%m/%Y %H:%M} → "
                        f"{cyc_report.data_end:%d/%m/%Y %H:%M}.)"
                    )

                html_doc = render_cyclic_html(cyc_report)
                st.download_button(
                    label="Download timeline report (.html)",
                    data=html_doc.encode("utf-8"),
                    file_name="cyclic_timeline.html",
                    mime="text/html",
                )

                st.subheader("12-hour windows")
                if not cyc_report.windows:
                    st.info("No cyclic data rows to plot.")
                for w in cyc_report.windows:
                    cap = w.title
                    if w.events:
                        cap += f"  ·  {len(w.events)} burst(s), " \
                               f"{sum(e.count for e in w.events)} image(s)"
                    st.image(w.png, caption=cap, use_container_width=True)


# ================== Tab 3: two linked interactive pages ======================
with tab_combined:
    st.caption(
        "Builds **two interactive pages that link to each other**: `report.html` "
        "(the chat) and `charts.html` (the cyclic charts). On a chart, hover for a "
        "value table + time crosshair and **click to lock**; click a **photo-burst "
        "marker** to open the chat at those images. On the chat, the **📈** button "
        "on any image opens the charts page at that moment (crosshair locked). The "
        "pages open each other in separate browser tabs — keep both files in the "
        "**same folder**. Downloaded together as a ZIP."
    )

    with st.form("combined_form"):
        cmb_zip = st.file_uploader(
            "WhatsApp export(s) (.zip)", type=["zip"],
            accept_multiple_files=True, key="cmb_zip",
        )
        cmb_csv = st.file_uploader(
            "Cyclic device log (.csv) — needs a 'DateTime' column",
            type=["csv"], accept_multiple_files=False, key="cmb_csv",
        )
        cmb_alarm = st.file_uploader(
            "Alarm log (.csv) — optional; 'Date' + 'Alarm' columns",
            type=["csv"], accept_multiple_files=False, key="cmb_alarm",
        )
        cmb_vars = st.multiselect(
            "Variables on the Y axis",
            options=list(VARIABLE_UNITS.keys()),
            default=list(DEFAULT_VARIABLES),
            key="cmb_vars",
        )
        c_a, c_b = st.columns(2)
        with c_a:
            cmb_hosp = st.text_input("Hospital name (optional)", value="", key="cmb_hosp")
        with c_b:
            cmb_label = st.text_input("Device name / ID (optional)", value="",
                                      key="cmb_label")
        with st.expander("Advanced options"):
            d1, d2, d3, d4 = st.columns(4)
            with d1:
                cmb_min = st.number_input("Min photos/burst", 1, 50, 3, key="cmb_min")
            with d2:
                cmb_gap = st.number_input("Burst gap (min)", 1, 120, 10, key="cmb_gap")
            with d3:
                cmb_hours = st.number_input("Window (hours)", 1, 48, 12, key="cmb_hours")
            with d4:
                cmb_dim = st.number_input("Max image px", 200, 1600, 480, step=40,
                                          key="cmb_dim")
        cmb_submitted = st.form_submit_button("Build linked pages", type="primary")

    if cmb_submitted:
        if not cmb_zip:
            st.error("Please upload at least one WhatsApp export ZIP.")
        elif cmb_csv is None:
            st.error("Please upload the cyclic device log CSV.")
        elif not cmb_vars:
            st.error("Please pick at least one variable.")
        else:
            pages = None
            with st.spinner("Building the two linked pages…"):
                try:
                    work_dir = _save_uploads_to_tempdir(
                        [(f.name, f.getvalue()) for f in cmb_zip],
                        prefix="wa_linked_gui_",
                    )
                    chat_html, charts_html = build_linked_pages(
                        [work_dir],
                        io.BytesIO(cmb_csv.getvalue()),
                        cmb_vars,
                        hospital=cmb_hosp.strip(),
                        device_label=cmb_label.strip(),
                        alarms_source=(io.BytesIO(cmb_alarm.getvalue())
                                       if cmb_alarm is not None else None),
                        min_photos=int(cmb_min),
                        window_minutes=int(cmb_gap),
                        window_hours=int(cmb_hours),
                        max_img_dim=int(cmb_dim),
                    )
                    pages = (chat_html, charts_html)
                except ValueError as exc:
                    st.error(f"Could not build the pages: {exc}")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Unexpected error: {exc}")

            if pages:
                chat_html, charts_html = pages
                import zipfile
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr("report.html", chat_html)
                    zf.writestr("charts.html", charts_html)
                st.success(
                    f"Done — report.html ({len(chat_html)//1024} KB) + "
                    f"charts.html ({len(charts_html)//1024} KB)."
                )
                st.download_button(
                    label="Download both pages (.zip)",
                    data=buf.getvalue(),
                    file_name="linked_report.zip",
                    mime="application/zip",
                )
                st.caption(
                    "Preview of the charts page (its cross-links open the chat page, "
                    "which only works once both files are extracted together):"
                )
                components.html(charts_html, height=760, scrolling=True)
