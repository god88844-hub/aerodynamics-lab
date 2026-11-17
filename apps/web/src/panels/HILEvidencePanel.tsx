import { useRef, useState } from 'react'
import { api } from '../services/api'

interface HILReport {
  status: string
  matches_supplied_preregistration_digest: boolean
  all_reported_holdouts_compatible_declared_samplewise_bounds: boolean
  blockers: string[]
  independent_physical_flight_validation_established: boolean
  flight_safety_certified: boolean
  runs: Array<{
    dataset_id: string
    role: string
    rows: number
    channel_errors: Record<string, {
      unit: string
      mae: number
      max_absolute_residual: number
      declared_samplewise_upper_bound: number | null
      within_declared_samplewise_tolerance: boolean
    }>
    blockers: string[]
  }>
}

export function HILEvidencePanel() {
  const [request, setRequest] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [report, setReport] = useState<HILReport | null>(null)
  const [busy, setBusy] = useState(false)
  const version = useRef(0)
  const invalidate = () => {
    version.current += 1
    setError(null)
    setReport(null)
    setBusy(false)
  }
  const submit = async () => {
    const mine = ++version.current
    setError(null)
    setReport(null)
    try {
      if (!request.trim()) throw new Error('Paste a frozen HIL evidence request')
      const payload: unknown = JSON.parse(request)
      if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
        throw new Error('Evidence request must be an object')
      }
      setBusy(true)
      const result = await api.post<HILReport>('/components/hil-evidence', payload)
      if (version.current === mine) setReport(result)
    } catch (e) {
      if (version.current === mine) setError((e as Error).message)
    } finally {
      if (version.current === mine) setBusy(false)
    }
  }

  return (
    <section aria-label="Controller HIL evidence comparison" className="space-y-2 p-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
        Controller / HIL evidence
      </h3>
      <p className="text-[10px] text-amber-400">
        Read-only comparison of independent reported trajectories and frozen
        predictions. Sources, clock sync, firmware and instrument calibration
        are not independently authenticated. No commands are sent to hardware.
      </p>
      <label className="block text-xs">
        HIL campaign JSON
        <textarea aria-label="Controller HIL campaign JSON" rows={5} value={request}
          onChange={e => { invalidate(); setRequest(e.target.value) }}
          placeholder="Frozen protocol and original SHA-256-pinned observed/predicted CSV recordings"
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs" />
      </label>
      <button type="button" disabled={busy} onClick={() => { void submit() }}
        className="w-full rounded bg-cyan-800 px-2 py-2 text-xs text-white disabled:opacity-40">
        {busy ? 'Auditing…' : 'Audit controller HIL evidence'}
      </button>
      {error && <p role="alert" className="text-xs text-rose-400">{error}</p>}
      {report && (
        <div className="space-y-1 text-xs">
          <p className="font-semibold text-amber-300">{report.status.replaceAll('_', ' ')}</p>
          <p>Reported samplewise compatibility: {
            report.all_reported_holdouts_compatible_declared_samplewise_bounds ? 'yes' : 'no'
          }</p>
          <p>Independent physical flight validation: {
            report.independent_physical_flight_validation_established ? 'yes' : 'no'
          }</p>
          <p>Flight safety certification: {report.flight_safety_certified ? 'yes' : 'no'}</p>
          <p>Blocking gaps: {report.blockers.length}</p>
          {report.runs.map(run => (
            <details key={run.dataset_id}>
              <summary className="cursor-pointer">{run.dataset_id} — {run.role} ({run.rows} points)</summary>
              <div className="space-y-1 py-1 text-[10px]">
                {Object.entries(run.channel_errors).map(([ch, metric]) =>
                  <p key={ch}>{ch}: MAE {metric.mae.toFixed(4)} {metric.unit},
                    max {metric.max_absolute_residual.toFixed(4)} {metric.unit},
                    sampled screen {metric.within_declared_samplewise_tolerance ? 'within' : 'not demonstrated'}</p>
                )}
                {run.blockers.map((b, i) => <p key={i} className="text-amber-300">{b}</p>)}
              </div>
            </details>
          ))}
          <p className="text-[10px] text-amber-400">
            These scores cannot certify actual controller hardware,
            actuator thermal behavior, or airworthiness.
          </p>
        </div>
      )}
    </section>
  )
}
