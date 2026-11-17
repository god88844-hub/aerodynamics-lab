import { useRef, useState } from 'react'
import { api } from '../services/api'

interface HoldoutRun {
  run_id: string
  sample_count: number
  robust_coverage_fraction: number
  worst_conservative_absolute_residual: number
  error_gate_passed: boolean
  interval_gate_passed: boolean
}
interface SourcePinnedReport {
  status: string
  source_bytes_integrity_verified_against_operator_supplied_digests: boolean
  source_identity_or_preregistration_externally_authenticated: boolean
  actual_independent_physical_validation_established: boolean
  decision_equivalent_to_physical_testing: boolean
  runs: HoldoutRun[]
  blockers: string[]
}

/** M27.3: read-only original-CSV comparison; source origins unauthenticated. */
export function SourcePinnedHoldoutPanel() {
  const [json, setJson] = useState('')
  const [result, setResult] = useState<SourcePinnedReport | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const version = useRef(0)

  const invalidate = () => {
    version.current += 1
    setResult(null)
    setError('')
    setBusy(false)
  }
  const audit = async () => {
    const mine = ++version.current
    setResult(null)
    setError('')
    try {
      if (!json.trim()) throw new Error('Paste original paired holdout files and frozen protocol metadata')
      const parsed: unknown = JSON.parse(json)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('Holdout audit input must be an object')
      }
      const body = parsed as Record<string, unknown>
      if (!Array.isArray(body.runs) || body.runs.length < 2 || !body.frozen_protocol_sha256) {
        throw new Error('Supply at least two holdout runs and the frozen protocol digest')
      }
      setBusy(true)
      const reply = await api.post<SourcePinnedReport>('/components/source-pinned-holdout-audit', body)
      if (mine === version.current) setResult(reply)
    } catch (e) {
      if (mine === version.current) setError((e as Error).message)
    } finally {
      if (mine === version.current) setBusy(false)
    }
  }
  return <section aria-label="Source-pinned prediction holdout evidence" className="space-y-2 p-3">
    <h3 className="text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
      Original-source holdout comparison
    </h3>
    <p className="text-[10px] text-amber-400">
      Compare exact original prediction and measured-value CSV bytes using claimed SHA-256 digests.
      Matching bytes and reported numerical agreement cannot prove physical origin, preregistration or aircraft safety.
    </p>
    <label className="block text-xs">Original holdout campaign JSON
      <textarea aria-label="Original source holdout JSON" rows={5} value={json}
        onChange={e => { invalidate(); setJson(e.target.value) }}
        placeholder='{"frozen_protocol_sha256":"...","runs":[{"observed_csv":"...","prediction_csv":"..."}]}'
        className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs" />
    </label>
    <button type="button" disabled={busy} onClick={() => { void audit() }}
      className="w-full rounded bg-cyan-800 px-2 py-2 text-xs text-white disabled:opacity-40">
      {busy ? 'Auditing…' : 'Audit original source holdouts'}
    </button>
    {error && <p role="alert" className="text-xs text-rose-400">{error}</p>}
    {result && <div className="space-y-1 text-xs">
      <p className="font-semibold text-amber-300">{result.status.replaceAll('_', ' ')}</p>
      <p>Original source hashes match supplied digests: {
        result.source_bytes_integrity_verified_against_operator_supplied_digests ? 'yes' : 'no'
      }</p>
      <p>Independent source and preregistration authentication: {
        result.source_identity_or_preregistration_externally_authenticated ? 'yes' : 'no'
      }</p>
      <p>Actual independent physical validation: {
        result.actual_independent_physical_validation_established ? 'yes' : 'no'
      }</p>
      <p>Physical-test decision equivalence: {
        result.decision_equivalent_to_physical_testing ? 'yes' : 'no'
      }</p>
      {result.runs.map(run => <details key={run.run_id}>
        <summary>{run.run_id} — {run.sample_count} samples</summary>
        <p>Robust coverage: {(100 * run.robust_coverage_fraction).toFixed(1)}%</p>
        <p>Worst hard-bound residual: {run.worst_conservative_absolute_residual.toPrecision(4)}</p>
        <p>Declared error and band gates: {run.error_gate_passed && run.interval_gate_passed ? 'met' : 'not met'}</p>
      </details>)}
      {result.blockers.map((blocker, i) => <p className="text-[10px] text-amber-400" key={i}>{blocker}</p>)}
    </div>}
  </section>
}
