import { useRef, useState } from 'react'
import type { ConfigResponse } from '../types'

interface Props {
  config: ConfigResponse | null
  busy: boolean
  error: string | null
  onSubmit: (cyclicFiles: File[], logFiles: File[]) => void
}

function FileDrop({
  label, hint, files, onChange, multiple = true,
}: {
  label: string
  hint: string
  files: File[]
  onChange: (files: File[]) => void
  multiple?: boolean
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  const addFiles = (list: FileList | null) => {
    if (!list) return
    onChange(multiple ? [...files, ...Array.from(list)] : [list[0]])
  }

  return (
    <div className="filedrop-wrap">
      <label className="lbl">{label}</label>
      <div
        className={`filedrop${dragOver ? ' over' : ''}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); addFiles(e.dataTransfer.files) }}
      >
        <input
          ref={inputRef} type="file" accept=".csv" multiple={multiple} hidden
          onChange={(e) => { addFiles(e.target.files); e.target.value = '' }}
        />
        {files.length === 0 ? (
          <span className="filedrop-hint">Drop CSV file{multiple ? 's' : ''} here, or click to browse — {hint}</span>
        ) : (
          <ul className="filedrop-list">
            {files.map((f, i) => (
              <li key={`${f.name}-${i}`}>
                {f.name} <span className="muted">({(f.size / 1024).toFixed(0)} KB)</span>
                <button
                  type="button" className="chip-x"
                  onClick={(e) => { e.stopPropagation(); onChange(files.filter((_, j) => j !== i)) }}
                >✕</button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export default function UploadScreen({ busy, error, onSubmit }: Props) {
  const [cyclicFiles, setCyclicFiles] = useState<File[]>([])
  const [logFiles, setLogFiles] = useState<File[]>([])

  const canSubmit = cyclicFiles.length > 0 && !busy

  return (
    <div className="upload-screen">
      <div className="upload-card">
        <h1>Cyclic Ventilator Report</h1>
        <p className="sub">
          Upload the device's exported CSV files to build an interactive timeline —
          the same data the desktop report uses, reused as-is (nothing re-parsed
          differently here).
        </p>

        <FileDrop
          label="Cyclic data CSV(s) — required"
          hint="the breath-by-breath trend export (PIP, VTi, VTe, …)"
          files={cyclicFiles}
          onChange={setCyclicFiles}
        />
        <FileDrop
          label="Log data CSV(s) — optional"
          hint="alarms, mode changes, and settings events"
          files={logFiles}
          onChange={setLogFiles}
        />

        {error && <div className="upload-error">{error}</div>}

        <button
          type="button" className="primary big"
          disabled={!canSubmit}
          onClick={() => onSubmit(cyclicFiles, logFiles)}
        >
          {busy ? 'Building report…' : 'Build report'}
        </button>
        {!cyclicFiles.length && <p className="hint">At least one Cyclic CSV is required. Log CSV is optional but enables alarms/events/mode changes.</p>}
      </div>
    </div>
  )
}
