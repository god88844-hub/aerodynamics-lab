import { useRef, useState } from 'react'
import { api } from '../services/api'
import type { DroneDesign } from '../types/api'

interface CombinedReport {
  status: string
  material_id: string
  screen_passed: boolean
  independent_structural_validation_established: boolean
  flightworthiness_established: boolean
  cases: Array<{ name: string, rotors: Array<{
    rotor_index: number
    von_mises_pa: number
    static_margin_over_required_allowable: number | null
  }> }>
  blockers?: string[]
}

export function CombinedMetalPanel({ design }: { design: DroneDesign }) {
  const [cases, setCases] = useState('')
  const [factor, setFactor] = useState('1.5')
  const [source, setSource] = useState('')
  const [report, setReport] = useState<CombinedReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const version = useRef(0)

  const invalidate = () => {
    version.current += 1
    setReport(null)
    setError(null)
    setBusy(false)
  }
  const analyze = async () => {
    const mine = ++version.current
    setError(null)
    setReport(null)
    try {
      if (!cases.trim() || !source.trim()) {
        throw new Error('Provide explicit load cases and their provenance')
      }
      const factorValue = Number(factor)
      if (!Number.isFinite(factorValue) || factorValue < 1 || factorValue > 10) {
        throw new Error('Safety factor must be between 1 and 10')
      }
      const parsed = JSON.parse(cases) as unknown
      if (!Array.isArray(parsed) || parsed.length === 0) {
        throw new Error('Load cases must be a nonempty JSON array')
      }
      setBusy(true)
      const data = await api.post<CombinedReport>('/components/combined-metal-screen', {
        design, cases: parsed, safety_factor: factorValue,
        load_case_source: source.trim(),
      })
      if (version.current === mine) setReport(data)
    } catch (e) {
      if (version.current === mine) setError((e as Error).message)
    } finally {
      if (version.current === mine) setBusy(false)
    }
  }

  return (
    <section aria-label="Combined metal stress screening" className="space-y-2 p-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
        Metal bending + torsion screen
      </h3>
      <p className="text-[10px] text-amber-400">
        First-order von Mises check applies only to isotropic Aluminum 6061-T6 tubes.
        CFRP, printed polymers, joints, fatigue and real flight strength are NOT validated.
      </p>
      <label className="block text-xs">
        Explicit load case list JSON
        <textarea aria-label="Combined stress load cases" rows={5} value={cases}
          onChange={e => { invalidate(); setCases(e.target.value) }}
          placeholder={'[{"name":"bench","thrusts_n":[5,5,5,5],"axial_torques_n_m":[0.1,0.1,0.1,0.1]}]'}
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs" />
      </label>
      <label className="block text-xs">
        Load source
        <input aria-label="Combined stress load provenance" value={source}
          onChange={e => { invalidate(); setSource(e.target.value) }}
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1" />
      </label>
      <label className="block text-xs">
        Required safety factor
        <input aria-label="Combined stress safety factor" value={factor}
          onChange={e => { invalidate(); setFactor(e.target.value) }}
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1" />
      </label>
      <button type="button" disabled={busy} onClick={() => { void analyze() }}
        className="w-full rounded bg-cyan-800 px-2 py-2 text-xs text-white disabled:opacity-40">
        {busy ? 'Evaluating…' : 'Screen metal arm combined stresses'}
      </button>
      {error && <p role="alert" className="text-xs text-rose-400">{error}</p>}
      {report && (
        <div className="space-y-1 text-xs">
          <p className="font-semibold text-amber-300">{report.status.replaceAll('_', ' ')}</p>
          <p>Material: {report.material_id}</p>
          <p>Analytical static screen: {report.screen_passed ? 'within declared limit' : 'not demonstrated'}</p>
          <p>Independent structural validation: {
            report.independent_structural_validation_established ? 'yes' : 'no'
          }</p>
          <p>Flightworthiness: {report.flightworthiness_established ? 'yes' : 'no'}</p>
          {report.cases.map(entry => (
            <details key={entry.name}>
              <summary>{entry.name} — {entry.rotors.length} arms</summary>
              {entry.rotors.map(arm => (
                <p key={arm.rotor_index} className="text-[10px]">
                  Rotor {arm.rotor_index}: { (arm.von_mises_pa / 1e6).toFixed(2) } MPa,
                  required allowable margin {arm.static_margin_over_required_allowable?.toFixed(2) ?? 'unknown'}
                </p>
              ))}
            </details>
          ))}
          {report.blockers?.map((warning, i) => (
            <p key={i} className="text-[10px] text-amber-400">{warning}</p>
          ))}
        </div>
      )}
    </section>
  )
}
