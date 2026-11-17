import { useRef, useState } from 'react'
import { api } from '../services/api'

interface AuditReport {
  datasets: Array<{
    dataset_id: string
    status: string
    rows: number
    quality: {
      sampling_interval_within_predeclared_bound: boolean
      max_gap_s: number
    }
    observations: {
      duration_s: number
      trapezoidal_reported_charge_ah: number | null
      trapezoidal_reported_energy_wh: number | null
    }
  }>
  partition: {
    status: string
    cross_partition_collisions: Array<{
      calibration_dataset_id: string
      holdout_dataset_id: string
      shared_identifiers: string[]
    }>
  }
  near_real_world_simulation_accuracy_established: boolean
}

export function TelemetryAuditPanel() {
  const [manifestText, setManifestText] = useState('')
  const [csvText, setCsvText] = useState('')
  const [report, setReport] = useState<AuditReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const latest = useRef(0)
  const invalidate = () => {
    latest.current += 1
    setReport(null)
    setError(null)
    setBusy(false)
  }
  const run = async () => {
    const version = ++latest.current
    setError(null)
    setReport(null)
    try {
      if (!manifestText.trim() || !csvText.trim()) {
        throw new Error('Provide the original CSV and its SHA-256-pinned manifest')
      }
      const manifest = JSON.parse(manifestText) as unknown
      if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest)) {
        throw new Error('Manifest must be a JSON object')
      }
      setBusy(true)
      const data = await api.post<AuditReport>('/components/telemetry-audit', {
        datasets: [{ manifest, csv_text: csvText }],
      })
      if (version === latest.current) setReport(data)
    } catch (e) {
      if (version === latest.current) setError((e as Error).message)
    } finally {
      if (version === latest.current) setBusy(false)
    }
  }

  return (
    <section aria-label="Independent telemetry ingestion audit" className="space-y-2 p-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
        Telemetry integrity and leakage audit
      </h3>
      <p className="text-[10px] text-amber-400">
        Strict timestamped battery I/V CSV ingestion, pinned SHA-256 and SI units.
        This read-only check cannot authenticate sensors or prove flight accuracy.
        Use the CLI for cross-flight calibration/holdout splits.
      </p>
      <label className="block text-xs">
        Immutable evidence manifest (JSON)
        <textarea aria-label="Telemetry manifest JSON" rows={5} value={manifestText}
          onChange={(e) => { invalidate(); setManifestText(e.target.value) }}
          placeholder="Paste a schema v1.0 manifest with raw_sha256, source IDs and roles"
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs" />
      </label>
      <label className="block text-xs">
        Original timestamped telemetry CSV
        <textarea aria-label="Original telemetry CSV" rows={5} value={csvText}
          onChange={(e) => { invalidate(); setCsvText(e.target.value) }}
          placeholder="t_s,terminal_voltage_v,current_a"
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs" />
      </label>
      <button type="button" onClick={() => void run()} disabled={busy}
        className="w-full rounded bg-cyan-800 px-2 py-2 text-xs text-white disabled:opacity-40">
        {busy ? 'Auditing…' : 'Audit telemetry without changing models'}
      </button>
      {error && <p role="alert" className="text-xs text-rose-400">{error}</p>}
      {report && (
        <div className="space-y-1 rounded border border-slate-700 p-2 text-xs">
          <p>Evidence split: {report.partition.status.replaceAll('_', ' ')}</p>
          {report.datasets.map((d) => (
            <div key={d.dataset_id}>
              <p className="font-semibold text-cyan-300">{d.dataset_id}: {d.status.replaceAll('_', ' ')}</p>
              <p>Rows: {d.rows}; duration: {d.observations.duration_s.toFixed(2)} s</p>
              <p>Maximum sample gap: {d.quality.max_gap_s.toFixed(3)} s</p>
              <p>Charge from reported current: {d.observations.trapezoidal_reported_charge_ah == null
                ? 'not supported' : d.observations.trapezoidal_reported_charge_ah.toFixed(5) + ' Ah'}</p>
              <p>Energy from reported V×I: {d.observations.trapezoidal_reported_energy_wh == null
                ? 'not supported' : d.observations.trapezoidal_reported_energy_wh.toFixed(5) + ' Wh'}</p>
            </div>
          ))}
          <p className="text-[10px] text-amber-400">
            Full aircraft physical validation: not established. Sensor calibration,
            independent hardware provenance and frozen predictive comparison remain required.
          </p>
        </div>
      )}
    </section>
  )
}
