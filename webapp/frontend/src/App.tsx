import { useEffect, useState } from 'react'
import './App.css'
import UploadScreen from './components/UploadScreen'
import ReportView from './components/ReportView'
import { ApiError, fetchConfig, uploadReport } from './api'
import type { ConfigResponse, Meta, Payload } from './types'

export default function App() {
  const [config, setConfig] = useState<ConfigResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [report, setReport] = useState<{ payload: Payload; meta: Meta } | null>(null)

  useEffect(() => {
    fetchConfig().then(setConfig).catch(() => setConfig(null))
  }, [])

  const handleSubmit = async (cyclicFiles: File[], logFiles: File[]) => {
    setBusy(true)
    setError(null)
    try {
      const res = await uploadReport(cyclicFiles, logFiles, [])
      setReport(res)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong building the report.')
    } finally {
      setBusy(false)
    }
  }

  if (report) {
    return <ReportView payload={report.payload} meta={report.meta} onReset={() => setReport(null)} />
  }
  return <UploadScreen config={config} busy={busy} error={error} onSubmit={handleSubmit} />
}
