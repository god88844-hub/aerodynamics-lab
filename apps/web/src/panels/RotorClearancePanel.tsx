import { useEffect, useRef, useState } from 'react'
import { api } from '../services/api'
import type { DroneDesign } from '../types/api'

interface Pair {
  rotor_a: number
  rotor_b: number
  projected_tip_clearance_m: number
  projected_disk_touch_or_overlap: boolean
  below_declared_tip_clearance: boolean
  center_vertical_separation_m: number
}
interface ClearanceResult {
  status: string
  screen_passed: boolean
  minimum_observed_projected_tip_clearance_m: number
  independently_measured_geometry_validated: boolean
  physical_interference_or_flightworthiness_established: boolean
  pairs: Pair[]
  limitations: string[]
}

/** M28.2: read-only projected prop sweep check, not as-built collision proof. */
export function RotorClearancePanel({ design }: { design: DroneDesign }) {
  const [diameters, setDiameters] = useState('')
  const [minimum, setMinimum] = useState('0')
  const [source, setSource] = useState('')
  const [result, setResult] = useState<ClearanceResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const version = useRef(0)

  const invalidate = () => {
    version.current += 1
    setResult(null)
    setError(null)
    setBusy(false)
  }
  useEffect(() => { invalidate() }, [design])

  const evaluate = async () => {
    const mine = ++version.current
    setResult(null)
    setError(null)
    try {
      const n = design.rotors.length
      if (n < 2 || n > 32) throw new Error('Select a design with 2–32 rotors')
      if (!source.trim()) throw new Error('State the original geometry and installed diameter source')
      const texts = diameters.split(',').map(v => v.trim())
      if (texts.length !== n || texts.some(v => !v)) {
        throw new Error('Enter exactly one installed propeller diameter (m) per rotor')
      }
      const values = texts.map(Number)
      if (values.some(v => !Number.isFinite(v) || v <= 0)) {
        throw new Error('Installed diameters must be positive finite numbers')
      }
      if (!minimum.trim() || !Number.isFinite(Number(minimum)) || Number(minimum) < 0) {
        throw new Error('Minimum declared tip clearance must be a nonnegative finite number')
      }
      setBusy(true)
      const report = await api.post<ClearanceResult>('/components/rotor-clearance-screen', {
        design,
        installed_propeller_diameters_m: values,
        minimum_declared_tip_clearance_m: Number(minimum),
        geometry_and_diameter_source: source.trim(),
      })
      if (mine === version.current) setResult(report)
    } catch (e) {
      if (mine === version.current) setError((e as Error).message)
    } finally {
      if (mine === version.current) setBusy(false)
    }
  }

  return (
    <section aria-label="Rotor sweep clearance analysis" className="space-y-2 p-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
        Rotor sweep / tip clearance
      </h3>
      <p className="text-[10px] text-amber-400">
        Projected XY disks only. No frame or blade 3D collision check, flexible
        blade clearance, physically measured assembly or flight safety approval.
      </p>
      <p className="text-xs text-slate-400">Current design: {design.rotors.length} rotors</p>
      <label className="block text-xs">
        Installed propeller diameters (m), comma-separated, rotor order
        <textarea aria-label="Installed rotor diameters" rows={2} value={diameters}
          onChange={e => { invalidate(); setDiameters(e.target.value) }}
          placeholder="0.381,0.381,0.381,0.381"
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs" />
      </label>
      <label className="block text-xs">
        Source of installed geometry and actual diameters
        <input aria-label="Rotor geometry source" value={source}
          onChange={e => { invalidate(); setSource(e.target.value) }}
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1" />
      </label>
      <label className="block text-xs">
        Minimum declared projected tip clearance (m)
        <input aria-label="Minimum rotor tip clearance" value={minimum}
          onChange={e => { invalidate(); setMinimum(e.target.value) }}
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1" />
      </label>
      <button type="button" onClick={() => { void evaluate() }} disabled={busy}
        className="w-full rounded bg-cyan-800 px-2 py-2 text-xs text-white disabled:opacity-40">
        {busy ? 'Checking…' : 'Screen rotor tip clearances'}
      </button>
      {error && <p role="alert" className="text-xs text-rose-400">{error}</p>}
      {result && (
        <div className="space-y-1 text-xs">
          <p className="font-semibold text-amber-300">{result.status.replaceAll('_', ' ')}</p>
          <p>Projected screen: {result.screen_passed ? 'within declared gap' : 'conflict or insufficient gap'}</p>
          <p>Minimum projected gap: {result.minimum_observed_projected_tip_clearance_m.toFixed(4)} m</p>
          <p>Physical interference validated: {result.physical_interference_or_flightworthiness_established ? 'yes' : 'no'}</p>
          <p>Geometry independently measured: {result.independently_measured_geometry_validated ? 'yes' : 'no'}</p>
          {result.pairs.map(p => (
            <p key={`${p.rotor_a}-${p.rotor_b}`} className={p.below_declared_tip_clearance ? 'text-rose-400' : 'text-slate-400'}>
              Rotors {p.rotor_a + 1}/{p.rotor_b + 1}: {p.projected_tip_clearance_m.toFixed(4)} m
              {p.projected_disk_touch_or_overlap ? ' (projected overlap)' : ''}
            </p>
          ))}
          <p className="text-[10px] text-amber-400">
            Positive projected gaps are only an analytic screen, never independent real-world validation.
          </p>
        </div>
      )}
    </section>
  )
}
