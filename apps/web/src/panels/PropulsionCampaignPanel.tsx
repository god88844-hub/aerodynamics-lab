import { useRef, useState } from 'react'
import { api } from '../services/api'

interface MotorCampaignResult {
  status: string
  motor_id: string
  propeller_id: string
  run_count: number
  holdout_count: number
  matches_supplied_frozen_protocol_digest: boolean
  manufacturer_reference_is_calibration_not_validation: boolean
  all_holdout_samples_compatible_declared_bounds_only: boolean
  independent_static_propulsion_validation_established: boolean
  flight_readiness_established: boolean
  blockers: string[]
  runs: Array<{
    dataset_id: string
    role: string
    original_point_count: number
    scored_count: number
    samplewise_compatible: boolean
    blockers: string[]
    unsupported: Array<{ index: number; reason: string }>
  }>
}

/** Preview static data consistency; never an independent physical qualification. */
export function PropulsionCampaignPanel() {
  const [input, setInput] = useState('')
  const [result, setResult] = useState<MotorCampaignResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const version = useRef(0)
  const invalidate = () => {
    version.current += 1
    setResult(null)
    setError(null)
    setRunning(false)
  }
  const submit = async () => {
    const id = ++version.current
    setResult(null)
    setError(null)
    try {
      if (!input.trim()) throw new Error('Provide a complete frozen static-bench campaign JSON')
      const parsed = JSON.parse(input) as unknown
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('Static propulsion campaign must be a JSON object')
      }
      const request = parsed as Record<string, unknown>
      if (!request.motor_id || !request.propeller_id ||
          !request.frozen_protocol || !Array.isArray(request.runs)) {
        throw new Error('Motor ID, propeller ID, frozen protocol and source runs are required')
      }
      setRunning(true)
      const answer = await api.post<MotorCampaignResult>(
        '/components/propulsion-campaign-audit', request,
      )
      if (id === version.current) setResult(answer)
    } catch (err) {
      if (id === version.current) setError((err as Error).message)
    } finally {
      if (id === version.current) setRunning(false)
    }
  }
  return (
    <section aria-label="Static propulsion validation evidence audit" className="space-y-2 p-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
        Motor and propeller bench campaign
      </h3>
      <p className="text-[10px] text-slate-400">
        Audit SHA-256-pinned static RPM, voltage, thrust and current measurements,
        registered test rigs and frozen holdout limits. Manufacturer calibration
        points and a different motor are not independent validation.
      </p>
      <label className="block text-xs">
        Campaign JSON
        <textarea aria-label="Static propulsion campaign JSON" rows={6} value={input}
          onChange={e => { invalidate(); setInput(e.target.value) }}
          placeholder='{"motor_id":"...", "propeller_id":"...", "frozen_protocol":{...}, "runs":[...]}'
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs" />
      </label>
      <button type="button" onClick={() => { void submit() }} disabled={running}
        className="w-full rounded bg-cyan-800 px-2 py-2 text-xs text-white disabled:opacity-40">
        {running ? 'Auditing…' : 'Audit static propulsion campaign'}
      </button>
      {error && <p role="alert" className="text-xs text-rose-400">{error}</p>}
      {result && <div className="space-y-1 rounded border border-slate-700 p-2 text-xs">
        <p className="font-semibold text-amber-300">{result.status.replaceAll('_', ' ')}</p>
        <p>Motor / propeller: {result.motor_id} / {result.propeller_id}</p>
        <p>Registered source runs: {result.run_count}; holdouts: {result.holdout_count}</p>
        <p>Static physical validation independently established: {
          result.independent_static_propulsion_validation_established ? 'yes' : 'no'
        }</p>
        <p>Aircraft flight readiness: {result.flight_readiness_established ? 'yes' : 'no'}</p>
        <p>Original manufacturer data are calibration: {
          result.manufacturer_reference_is_calibration_not_validation ? 'yes' : 'no'
        }</p>
        <p>Pre-registered digest matches declaration: {
          result.matches_supplied_frozen_protocol_digest ? 'yes' : 'no'
        }</p>
        <p>Samplewise thrust/current agreement under reported bounds: {
          result.all_holdout_samples_compatible_declared_bounds_only ? 'reported' : 'not established'
        }</p>
        {result.runs.map(r => <div key={r.dataset_id}
          className="space-y-1 border-t border-slate-800 pt-2">
          <p>{r.dataset_id} ({r.role}): {r.scored_count}/{r.original_point_count} points scored</p>
          {r.blockers.map((reason,i) =>
            <p key={i} className="text-[10px] text-amber-400">{reason}</p>)}
          {r.unsupported.map(x =>
            <p key={x.index} className="text-[10px] text-rose-400">Unsupported {x.index}: {x.reason}</p>)}
        </div>)}
        <p className="text-[10px] font-medium text-amber-400">Independent evidence gaps: {result.blockers.length}</p>
        {result.blockers.map((b,i) =>
          <p key={i} className="text-[10px] text-slate-400">{b}</p>)}
        <p className="text-[10px] text-amber-400">
          No physical certification, aircraft safety release, or dynamic motor/ESC
          thermal prediction is supported by this comparison.
        </p>
      </div>}
    </section>
  )
}
