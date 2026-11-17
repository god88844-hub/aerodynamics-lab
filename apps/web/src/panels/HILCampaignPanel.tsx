import { useRef, useState } from 'react'
import { api } from '../services/api'

interface ControllerEvidence {
  status: string
  matches_supplied_frozen_digest: boolean
  run_count: number
  holdout_count: number
  reported_samplewise_tracking_compatible_only: boolean
  simulation_prediction_error_measured: boolean
  independent_controller_hardware_validation: boolean
  aircraft_flight_readiness: boolean
  blockers: string[]
  runs: Array<{
    dataset_id: string
    partition_role: string
    count: number
    maximum_gap_s: number
    max_roll_or_pitch_tracking_error_deg: number
    tracking_rmse_deg: number
    saturation_count: number
    samplewise_tracking_upper_bound_deg: number | null
    blockers: string[]
  }>
}

/** Source-integrity and tracking audit, never a HIL simulator validation verdict. */
export function HILCampaignPanel() {
  const [raw, setRaw] = useState('')
  const [report, setReport] = useState<ControllerEvidence | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const version = useRef(0)
  const invalidate = () => {
    version.current += 1
    setReport(null)
    setError(null)
    setRunning(false)
  }
  const run = async () => {
    const key = ++version.current
    setReport(null)
    setError(null)
    try {
      if (!raw.trim()) throw new Error('Paste a frozen controller protocol and original telemetry')
      const parsed = JSON.parse(raw) as unknown
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('Controller campaign must be an object')
      }
      const data = parsed as Record<string, unknown>
      if (!data.frozen_protocol || !Array.isArray(data.recordings)) {
        throw new Error('Campaign needs frozen_protocol and recordings')
      }
      setRunning(true)
      const result = await api.post<ControllerEvidence>('/components/hil-campaign-audit', data)
      if (key === version.current) setReport(result)
    } catch (e) {
      if (key === version.current) setError((e as Error).message)
    } finally {
      if (key === version.current) setRunning(false)
    }
  }
  return (
    <section aria-label="Controller-in-the-loop evidence audit" className="space-y-2 p-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
        Controller / sensor hardware-loop evidence
      </h3>
      <p className="text-[10px] text-amber-400">
        Audit frozen firmware and parameter hashes, source-pinned controller
        measurements, timestamp and saturation quality, and tracking residuals.
        Command tracking is not AeroForge flight-model prediction accuracy.
      </p>
      <label className="block text-xs">
        Original HIL campaign and protocol JSON
        <textarea aria-label="HIL controller campaign JSON" rows={6} value={raw}
          onChange={e => { invalidate(); setRaw(e.target.value) }}
          placeholder='{"frozen_protocol":{...},"recordings":[...]}'
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs" />
      </label>
      <button type="button" onClick={() => { void run() }} disabled={running}
        className="w-full rounded bg-cyan-800 px-2 py-2 text-xs text-white disabled:opacity-40">
        {running ? 'Auditing…' : 'Audit controller test evidence'}
      </button>
      {error && <p role="alert" className="text-xs text-rose-400">{error}</p>}
      {report && <div className="space-y-2 rounded border border-slate-700 p-2 text-xs">
        <p className="font-semibold text-amber-300">{report.status.replaceAll('_', ' ')}</p>
        <p>Flight-model prediction error measured: {report.simulation_prediction_error_measured ? 'yes' : 'no'}</p>
        <p>Independently validated controller hardware: {
          report.independent_controller_hardware_validation ? 'yes' : 'no'
        }</p>
        <p>Flight readiness established: {report.aircraft_flight_readiness ? 'yes' : 'no'}</p>
        <p>Declared roll/pitch samplewise tracking compatible: {
          report.reported_samplewise_tracking_compatible_only ? 'reported' : 'not demonstrated'
        }</p>
        <p>Records: {report.run_count}; declared holdouts: {report.holdout_count}</p>
        {report.runs.map(r => <div key={r.dataset_id} className="border-t border-slate-800 pt-2">
          <p className="font-semibold">{r.dataset_id} ({r.partition_role})</p>
          <p>Samples: {r.count}; maximum gap {r.maximum_gap_s.toFixed(4)} s</p>
          <p>Worst reported roll/pitch tracking error: {
            r.max_roll_or_pitch_tracking_error_deg.toFixed(3)
          }°</p>
          <p>RMS tracking error: {r.tracking_rmse_deg.toFixed(3)}°</p>
          <p>Saturation flags: {r.saturation_count}</p>
          <p>Conservative declared bound: {
            r.samplewise_tracking_upper_bound_deg === null
              ? 'unavailable' : r.samplewise_tracking_upper_bound_deg.toFixed(3) + '°'
          }</p>
          {r.blockers.map((b, i) => <p key={i} className="text-[10px] text-amber-400">{b}</p>)}
        </div>)}
        <p className="text-[10px] text-amber-400">
          Nonphysical or unauthenticated data do not qualify an aircraft.
          Real hardware-in-the-loop testing and independently timed simulator
          predictions are still needed.
        </p>
      </div>}
    </section>
  )
}
