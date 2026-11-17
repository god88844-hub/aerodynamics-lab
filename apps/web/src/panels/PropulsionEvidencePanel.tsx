/** M14: compare measured static motor/prop observations against the frozen bench model. */
import { useEffect, useRef, useState } from 'react'
import { api } from '../services/api'
import type { DroneDesign } from '../types/api'
import { parsePropulsionEvidenceRows } from '../editor/propulsionEvidenceRows'
import { SectionTitle } from './fields'

interface Metrics {
  n: number
  mape_pct: number
  rmse_pct: number
  max_abs_error_pct: number
  threshold_met: boolean
}
interface EvidenceResult {
  verdict: string
  simulation_modified: boolean
  evidence: {
    observation_count: number
    scored_count: number
    unsupported_count: number
    unsupported_samples: { id: string; reason: string }[]
    thrust_metrics: Metrics | null
    current_metrics: Metrics | null
    current_voltage_extrapolated: boolean
    calibration_knot_operating_point_overlap_count: number
  }
}

export function PropulsionEvidencePanel({ design }: { design: DroneDesign }) {
  const motorId = design.powertrain?.motor_id ?? ''
  const propId = design.powertrain?.propeller_id ?? ''
  const [kind, setKind] = useState('')
  const [runId, setRunId] = useState('')
  const [source, setSource] = useState('')
  const [fixture, setFixture] = useState('')
  const [hardwareMatch, setHardwareMatch] = useState(false)
  const [independent, setIndependent] = useState(false)
  const [thrustTol, setThrustTol] = useState('')
  const [currentTol, setCurrentTol] = useState('')
  const [csv, setCsv] = useState('')
  const [report, setReport] = useState<EvidenceResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const version = useRef(0)
  const invalidate = () => { version.current++; setReport(null); setError(null); setRunning(false) }
  useEffect(() => { version.current++; setReport(null); setError(null); setRunning(false) }, [design])

  async function run() {
    const currentVersion = ++version.current
    setReport(null); setError(null)
    try {
      if (!motorId || !propId) throw new Error('Select matching motor and propeller components')
      if (kind !== 'physical_measurements' && kind !== 'synthetic_fixture') {
        throw new Error('Choose measured data or synthetic code-verification fixtures')
      }
      if (!runId.trim() || !source.trim()) throw new Error('Specify independent run ID and data source')
      if (kind === 'physical_measurements' && !fixture.trim()) {
        throw new Error('Describe the test fixture and measurement instruments')
      }
      const t = Number(thrustTol), c = Number(currentTol)
      if (![t, c].every((value) => Number.isFinite(value) && value > 0 && value <= 100) ||
          !thrustTol.trim() || !currentTol.trim()) throw new Error('Predeclare two tolerances between 0 and 100%')
      const observations = parsePropulsionEvidenceRows(csv)
      setRunning(true)
      const result = await api.post<EvidenceResult>('/components/propulsion-evidence', {
        motor_id: motorId, propeller_id: propId, dataset_kind: kind,
        independent_run_id: runId.trim(), evidence_source: source.trim(),
        hardware_matches_selected_components: hardwareMatch,
        unused_for_model_calibration: independent,
        predeclared_max_thrust_error_pct: t, predeclared_max_current_error_pct: c,
        test_fixture_description: fixture.trim() || null,
        observations,
      })
      if (version.current === currentVersion) setReport(result)
    } catch (e) {
      if (version.current === currentVersion) setError((e as Error).message)
    } finally {
      if (version.current === currentVersion) setRunning(false)
    }
  }

  return (
    <section className="space-y-2 p-3" aria-label="Propulsion evidence lab">
      <SectionTitle>Static propulsion evidence lab</SectionTitle>
      <p className="text-[10px] text-amber-400">
        Independent static thrust-bench measurements required for empirical evidence.
        Same calibration table is never independent validation; data provenance is operator-declared.
      </p>
      <p className="text-xs text-cyan-300">Motor: {motorId || 'none'} · Prop: {propId || 'none'}</p>
      <label className="block text-xs">Dataset type
        <select aria-label="Propulsion evidence dataset type" value={kind}
          onChange={(e) => { invalidate(); setKind(e.target.value) }}
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1">
          <option value="">Select evidence type</option>
          <option value="physical_measurements">User-reported physical measurements</option>
          <option value="synthetic_fixture">Synthetic mathematical verification</option>
        </select>
      </label>
      {([
        ['Independent test run ID', runId, setRunId],
        ['Evidence source / raw data reference', source, setSource],
        ['Fixture / instrument description', fixture, setFixture],
        ['Predeclared maximum thrust error (%)', thrustTol, setThrustTol],
        ['Predeclared maximum current error (%)', currentTol, setCurrentTol],
      ] as const).map(([name, value, update]) => (
        <label key={name} className="block text-xs">{name}
          <input type="text" aria-label={name} value={value} maxLength={500}
            onChange={(e) => { invalidate(); update(e.target.value) }}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1" />
        </label>
      ))}
      <label className="flex items-center gap-2 text-xs">
        <input type="checkbox" aria-label="Matching motor prop hardware" checked={hardwareMatch}
          onChange={(e) => { invalidate(); setHardwareMatch(e.target.checked) }} />
        Identical motor / propeller hardware (user declared)
      </label>
      <label className="flex items-center gap-2 text-xs">
        <input type="checkbox" aria-label="Unused for calibration" checked={independent}
          onChange={(e) => { invalidate(); setIndependent(e.target.checked) }} />
        These observations were not used for model calibration (user declared)
      </label>
      <p className="text-[10px] text-slate-400">CSV: id,rpm,voltage_v,thrust_gf,current_a.
        At least five distinct RPM points; no automatically generated evidence.</p>
      <textarea aria-label="Propulsion bench CSV rows" rows={6} value={csv}
        onChange={(e) => { invalidate(); setCsv(e.target.value) }}
        placeholder="id,rpm,voltage_v,thrust_gf,current_a"
        className="w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs" />
      <button type="button" disabled={running || !motorId || !propId}
        onClick={() => void run()}
        className="w-full rounded bg-cyan-800 px-2 py-2 text-xs text-white disabled:opacity-40">
        {running ? 'Evaluating…' : 'Compare independent static bench data'}
      </button>
      {error && <p role="alert" className="text-xs text-rose-400">{error}</p>}
      {report && (
        <div className="space-y-1 rounded border border-slate-700 p-2 text-xs">
          <p className="font-semibold text-amber-300">{report.verdict.replaceAll('_', ' ')}</p>
          <p>Scored: {report.evidence.scored_count}/{report.evidence.observation_count}</p>
          <p>Unsupported: {report.evidence.unsupported_count}</p>
          <p>Thrust MAPE: {report.evidence.thrust_metrics?.mape_pct.toFixed(2) ?? 'not computable'}%</p>
          <p>Current MAPE: {report.evidence.current_metrics?.mape_pct.toFixed(2) ?? 'not computable'}%</p>
          <p>Worst thrust error: {report.evidence.thrust_metrics?.max_abs_error_pct.toFixed(2) ?? 'unknown'}%</p>
          <p>Worst current error: {report.evidence.current_metrics?.max_abs_error_pct.toFixed(2) ?? 'unknown'}%</p>
          <p>Calibration knot overlaps: {report.evidence.calibration_knot_operating_point_overlap_count}</p>
          <p>Extrapolated voltage: {report.evidence.current_voltage_extrapolated ? 'yes' : 'no'}</p>
          {report.evidence.unsupported_samples.map((row) => (
            <p key={row.id} className="text-rose-400">{row.id}: {row.reason}</p>
          ))}
          <p className="text-[10px] text-amber-400">No simulation is changed. Matching error
            tolerances cannot establish measurement traceability or certify a flight vehicle.</p>
        </div>
      )}
    </section>
  )
}
