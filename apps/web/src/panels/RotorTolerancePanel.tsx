import { useRef, useState } from 'react'
import { api } from '../services/api'
import type { DroneDesign } from '../types/api'

interface BoundedResult {
  status: string
  analytical_screen_passed: boolean
  actual_3d_interference_validated: boolean
  flightworthiness_established: boolean
  source_hard_bounds_independently_authenticated: boolean
  minimum_worst_case_projected_tip_clearance_m: number
  pairs: Array<{
    rotor_a: number
    rotor_b: number
    worst_case_lower_projected_tip_clearance_m: number
    guaranteed_declared_tip_gap_under_assumed_hard_bounds: boolean
  }>
}

/** M28.4 assumed hard uncertainty bounds are not independent as-built evidence. */
export function RotorTolerancePanel({ design }: { design: DroneDesign }) {
  const [diameters, setDiameters] = useState('')
  const [centers, setCenters] = useState('')
  const [errors, setErrors] = useState('')
  const [minimum, setMinimum] = useState('0.02')
  const [geometrySource, setGeometrySource] = useState('')
  const [boundSource, setBoundSource] = useState('')
  const [report, setReport] = useState<BoundedResult | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const key = useRef(0)
  const invalidate = () => {
    key.current++
    setReport(null)
    setError('')
    setBusy(false)
  }
  const parse = (csv: string, count: number, label: string, positive = false) => {
    const parts = csv.split(',').map(s => s.trim())
    if (parts.length !== count || parts.some(s => s === '')) {
      throw new Error(`Enter exactly ${count} ${label}, in rotor order`)
    }
    const numbers = parts.map(Number)
    if (numbers.some(n => !Number.isFinite(n) || n < 0 || (positive && n === 0))) {
      throw new Error(`${label} must be finite ${positive ? 'positive' : 'nonnegative'} metres`)
    }
    return numbers
  }
  const run = async () => {
    const call = ++key.current
    setError('')
    setReport(null)
    try {
      const count = design.rotors.length
      if (count < 2 || count > 32) throw new Error('Design must contain 2–32 rotors')
      if (!geometrySource.trim() || !boundSource.trim()) {
        throw new Error('Original installed-geometry source and deterministic hard-bound source required')
      }
      const d = parse(diameters, count, 'installed diameters', true)
      const c = parse(centers, count, 'Euclidean XY center hard bounds')
      const e = parse(errors, count, 'diameter hard bounds')
      if (!minimum.trim() || !Number.isFinite(Number(minimum)) || Number(minimum) < 0) {
        throw new Error('Minimum projected gap must be finite and nonnegative')
      }
      setBusy(true)
      const result = await api.post<BoundedResult>('/components/bounded-rotor-clearance', {
        design, installed_propeller_diameters_m: d,
        xy_center_position_hard_bounds_m: c, diameter_hard_bounds_m: e,
        geometry_source: geometrySource.trim(), hard_bound_source: boundSource.trim(),
        minimum_declared_tip_clearance_m: Number(minimum),
      })
      if (call === key.current) setReport(result)
    } catch (e) {
      if (call === key.current) setError((e as Error).message)
    } finally {
      if (call === key.current) setBusy(false)
    }
  }
  return <section aria-label="Rotor tolerance uncertainty screen" className="space-y-2 p-3">
    <h3 className="text-[11px] font-semibold uppercase tracking-wider text-cyan-500">Rotor geometry hard bounds</h3>
    <p className="text-[10px] text-amber-400">Deterministic XY projected clearance only. Bounds must be worst-case absolute errors, not statistical standard deviations. No physical assembly or flight validation.</p>
    <p className="text-xs">Current rotors: {design.rotors.length}</p>
    {([
      ['Installed rotor diameters (m)', diameters, setDiameters],
      ['Rotor center XY hard bounds (m)', centers, setCenters],
      ['Rotor diameter hard bounds (m)', errors, setErrors],
      ['Geometry provenance', geometrySource, setGeometrySource],
      ['Hard-bound provenance', boundSource, setBoundSource],
      ['Required minimum clearance (m)', minimum, setMinimum],
    ] as Array<[string, string, (s: string) => void]>).map(([label, value, setter]) => (
      <label className="block text-xs" key={label}>{label}
        <input aria-label={label} value={value} onChange={event => { invalidate(); setter(event.target.value) }}
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1" />
      </label>
    ))}
    <button type="button" disabled={busy} onClick={() => { void run() }}
      className="w-full rounded bg-cyan-800 px-2 py-2 text-xs text-white disabled:opacity-40">
      {busy ? 'Evaluating…' : 'Evaluate bounded rotor clearances'}
    </button>
    {error && <p role="alert" className="text-xs text-rose-400">{error}</p>}
    {report && <div className="space-y-1 text-xs">
      <p className="font-semibold text-amber-300">{report.status.replaceAll('_', ' ')}</p>
      <p>Conservative analytical screen: {report.analytical_screen_passed ? 'within assumed limits' : 'not established'}</p>
      <p>Worst projected clearance: {report.minimum_worst_case_projected_tip_clearance_m.toFixed(4)} m</p>
      <p>Independently authenticated geometry bounds: {report.source_hard_bounds_independently_authenticated ? 'yes' : 'no'}</p>
      <p>Actual 3D interference validated: {report.actual_3d_interference_validated ? 'yes' : 'no'}</p>
      <p>Flightworthiness: {report.flightworthiness_established ? 'yes' : 'no'}</p>
      {report.pairs.map(pair => <p key={`${pair.rotor_a}-${pair.rotor_b}`}>
        {pair.rotor_a + 1}/{pair.rotor_b + 1}: {pair.worst_case_lower_projected_tip_clearance_m.toFixed(4)} m
        {pair.guaranteed_declared_tip_gap_under_assumed_hard_bounds ? '' : ' — insufficient'}
      </p>)}
    </div>}
  </section>
}
