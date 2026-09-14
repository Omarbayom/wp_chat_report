# Building the desktop .exe (PyInstaller)

The Streamlit app (`app.py`) can be packaged into a single standalone
`WA-Ventilation-Report.exe` — no Python install needed on the machine that
runs it.

## Build

From the repo root, with the `wp` conda env's packages available
(`pip install pyinstaller` into it once, first time only):

```powershell
powershell -ExecutionPolicy Bypass -File build_exe.ps1
```

Output: `dist\WA-Ventilation-Report.exe` (~85 MB, single file). Double-click
it — it starts the app's own local server and opens your browser to it
automatically. Closing the console window it opens stops the server.

## How it works

- `run_app.py` is the actual PyInstaller entry point, not `app.py` directly —
  Streamlit's CLI takes `app.py` as a **file path** it execs at runtime, not
  something PyInstaller can discover by statically analyzing imports. Two
  consequences, both handled in `run_app.py`:
  - it carries a block of otherwise-unused imports (`pandas`, `docx`, `PIL`,
    `wa_report.*`, …) purely so PyInstaller's analysis sees them and bundles
    them — don't remove them as dead code.
  - `app.py` itself is shipped as a **data file** (`--add-data`), not code
    PyInstaller compiles in, since Streamlit needs a real path on disk to
    read it from.
- Config (upload size limits, headless mode, port) is passed as `streamlit
  run` CLI flags in `run_app.py`, not via `.streamlit/config.toml` — that
  file is read relative to the process's working directory, which for a
  onefile build's extracted temp dir isn't predictable.

## Two real build issues hit (and fixed) building this the first time

1. **Crashed on startup with `ImportError: DLL load failed... _ctypes`.**
   Root cause: conda keeps several of its own shared DLLs (`ffi-8.dll`,
   `sqlite3.dll`, `libbz2.dll`, `liblzma.dll`, `libexpat.dll`) under
   `<env>\Library\bin`, which `conda activate` normally puts on `PATH` —
   since the build invokes `python.exe` by its full path instead, that
   directory was never on `PATH`, so PyInstaller's dependency walker
   couldn't find `ffi-8.dll` to bundle it, and `_ctypes` failed to load at
   runtime. `build_exe.ps1` adds `Library\bin` to `PATH` before invoking
   PyInstaller to fix this at the source. Neither this app nor its
   dependencies actually need a GUI plotting backend, so `matplotlib` and
   `tkinter` are also explicitly excluded — that removes the specific
   runtime hook path that surfaced this crash, and cuts ~10 MB besides.
2. A test session's **first two file-drop events fired back-to-back** (no
   pause between them) produced a "Connection error" in the browser tab —
   turned out to be a test-harness artifact (a stale, reused browser tab
   accumulating console errors across two separate app launches), not a
   real bug: a clean run with files added one at a time, verified between
   each step, built the exact same `charts.html` output as the normal
   Streamlit run without issue.

## Known limitation: unsigned-binary AV warnings

This `.exe` isn't code-signed. PyInstaller onefile binaries are a common
target for antivirus heuristics (they self-extract at startup, which looks
similar to some malware droppers) — expect a SmartScreen prompt on first
run on an unfamiliar machine, and possibly a Defender/AV flag on some
networks. That's a property of *any* unsigned PyInstaller build, not
something specific to this app; getting rid of it requires a paid code-signing
certificate, out of scope here.
