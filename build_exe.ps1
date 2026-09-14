# Builds the desktop .exe for the Streamlit GUI (app.py) via PyInstaller.
# Run from anywhere: powershell -ExecutionPolicy Bypass -File build_exe.ps1
# Output: dist\WA-Ventilation-Report.exe (a single, double-click-able file).
$ErrorActionPreference = 'Stop'
$Python = "C:\Users\Owner\.conda\envs\wp\python.exe"
$Root = $PSScriptRoot

# Conda keeps a bunch of its own shared DLLs (libffi, sqlite3, libbz2, ...)
# under Library\bin — normally put on PATH by `conda activate`, which we
# don't run here since we call python.exe by its full path. Without it,
# PyInstaller's dependency walker can't find e.g. ffi-8.dll (needed by
# _ctypes.pyd) and silently ships a build that crashes at startup instead.
$env:PATH = "C:\Users\Owner\.conda\envs\wp\Library\bin;$env:PATH"

$pyiArgs = @(
  "--name", "WA-Ventilation-Report",
  "--onefile",
  "--console",
  "--clean",
  "--distpath", "$Root\dist",
  "--workpath", "$Root\build",
  "--specpath", "$Root",
  "--add-data", "$Root\app.py;.",
  "--collect-all", "streamlit",
  "--collect-all", "wa_report",
  "--hidden-import", "pandas",
  "--hidden-import", "docx",
  "--hidden-import", "PIL",
  "--hidden-import", "dotenv",
  # Neither this app nor its deps actually use a GUI plotting backend —
  # excluding these avoids the matplotlib/tkinter runtime hook path
  # entirely (the one that crashed at startup importing ctypes above).
  "--exclude-module", "matplotlib",
  "--exclude-module", "tkinter",
  "$Root\run_app.py"
)

& $Python -m PyInstaller @pyiArgs
