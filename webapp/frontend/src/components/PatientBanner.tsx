export default function PatientBanner({ patient }: { patient: [string, string][] }) {
  if (!patient.length) return null
  const get = (label: string) => patient.find(([k]) => k === label)?.[1]
  const name = get('Patient Name')
  const id = get('Patient ID')
  return (
    <div className="patient-banner">
      <b>{name || 'Current patient'}</b>
      {id && <span className="muted"> · ID {id}</span>}
      <details className="patient-details">
        <summary>all fields</summary>
        <table className="dm-t">
          <tbody>
            {patient.map(([k, v]) => (
              <tr key={k}><td className="k">{k}</td><td className="v">{v}</td></tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}
