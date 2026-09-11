import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Dev-only proxy so the frontend can call plain "/api/…" paths without
    // CORS — the FastAPI backend (see webapp/backend) is expected to be
    // running separately on port 8000 (`uvicorn webapp.backend.app.main:app
    // --reload --port 8000` from the repo root).
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
