# Cyclic Report — React + FastAPI web app

A parallel, browser-based front end for the cyclic ventilator timeline —
upload the device's CSV exports instead of generating a static `charts.html`
file. This is a **separate product**, not a replacement: the existing
Streamlit app (`app.py`) and static report generator
(`wa_report/cyclic_report/render_pages.py`) are untouched and keep working
exactly as before.

The backend does **no new CSV parsing** — it calls straight into the
existing `wa_report.cyclic_report` package (`build_payload`, the same
function the static report's embedded JSON comes from), so this app can't
drift from what the desktop tool already does with the same files.

## What's here (v1 — core timeline)

- Upload one or more Cyclic CSVs (required) and Log CSVs (optional).
- Interactive dual-lane timeline: Alarms / Modes / Events strips + one
  stacked chart per selected Y-axis variable, all on a shared, zoomable
  time axis (Plotly.js — native pan/zoom/rangeslider, no hand-rolled brush
  geometry to maintain).
- Alarms / Events / Mode-changes ledger below the chart — click a chip to
  zoom the chart to it, click ⓘ on an event/mode for its full detail popup
  (set values, the log row's own "Cyc." echo if it has one, and — new in
  this app, ported from the same idea in the static report — the nearest
  real cyclic trend sample when it doesn't).
- Patient preamble banner.

## Not in this v1 (by design, see `docs/` conversation history)

WhatsApp chat merge / photo bursts, the Patients roster page, Word (.docx)
report generation, and the static report's view Export/Import. These were
deliberately deferred to get a working core timeline first — see the repo's
session history for the scoping decision. Add them incrementally once the
core UX is validated.

## Running it

Two processes, both from the **repo root** (`whatapp summry/`):

```bash
# 1. Backend (FastAPI) — needs the same env as the rest of the repo (conda env "wp"),
#    plus: pip install -r webapp/backend/requirements.txt
uvicorn webapp.backend.app.main:app --reload --port 8000

# 2. Frontend (React + Vite), in a second terminal
cd webapp/frontend
npm install   # first time only
npm run dev
```

Then open the URL Vite prints (default `http://localhost:5173`). The Vite
dev server proxies `/api/*` to the backend on port 8000 (see
`webapp/frontend/vite.config.ts`) — no CORS setup needed in dev.

Both are also registered in `.claude/launch.json` as `cyclic-webapp-backend`
/ `cyclic-webapp-frontend` for Claude Code's browser-preview tooling.

## Layout

```
webapp/
  backend/
    app/main.py         FastAPI app: POST /api/report (upload), GET /api/config
    requirements.txt
  frontend/
    src/
      api.ts             fetch wrappers
      types.ts            TS mirror of the backend's JSON shapes
      lib/report.ts       Plotly figure builder, detail-modal data helpers
      lib/format.ts        date/time/duration formatting (UTC — see comment)
      components/         UploadScreen, ReportView, Ledger, DetailModal, …
```
