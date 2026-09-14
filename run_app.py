"""Desktop-launcher entry point for the packaged .exe build of the Streamlit
GUI (app.py) — built with PyInstaller, see build_exe.bat.

Streamlit's CLI takes app.py as a *file path*, not an imported module, so
PyInstaller's static import analysis (which starts from THIS file) never
sees anything app.py itself imports (wa_report.*, pandas, python-docx,
Pillow, python-dotenv) — they'd silently be left out of the frozen build.
The imports below that do nothing with their result exist ONLY to put those
packages in front of that analysis; don't remove them as "unused".
"""

from __future__ import annotations

import sys
import threading
import webbrowser
from pathlib import Path

import streamlit.web.cli as stcli

# ---- PyInstaller import-discovery only (see module docstring) — noqa: F401
import pandas  # noqa: F401
import docx  # noqa: F401
import PIL  # noqa: F401
import dotenv  # noqa: F401
import wa_report.report  # noqa: F401
import wa_report.render_docx  # noqa: F401
import wa_report.render_html  # noqa: F401
import wa_report.media  # noqa: F401
import wa_report.cyclic_report  # noqa: F401


def _resource_path(relative: str) -> str:
    """Resolve a bundled file's real on-disk path, whether running from
    source (`python run_app.py`) or from a PyInstaller onefile build (which
    extracts its bundled data files to a temp dir named in `sys._MEIPASS`
    at runtime)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base / relative)


def main() -> None:
    app_path = _resource_path("app.py")
    port = "8501"
    url = f"http://localhost:{port}"

    # Streamlit blocks in stcli.main() below, so open the browser tab from a
    # timer instead of after the call — by the time this fires the server has
    # almost always finished its ~1s startup.
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    # Config passed as flags rather than .streamlit/config.toml: that file is
    # read relative to the process's *working directory*, which for a
    # onefile build's extracted temp dir isn't where it'd land — flags avoid
    # the ambiguity entirely. Values match the repo's .streamlit/config.toml.
    sys.argv = [
        "streamlit", "run", app_path,
        "--global.developmentMode=false",
        f"--server.port={port}",
        "--server.headless=true",
        "--server.maxUploadSize=300",
        "--server.maxMessageSize=300",
        "--browser.gatherUsageStats=false",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
