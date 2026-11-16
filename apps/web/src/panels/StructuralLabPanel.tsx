import { useEffect, useState } from 'react'
import type { DroneDesign } from '../types/api'
import { api } from '../services/api'
import { parseStructuralCases } from '../editor/structuralCases'
import { SectionTitle } from './fields'

interface RotorResult {
  rotor_index: number
  thrust_n: number
  span_m: number
  root_bending_moment_n_m: number
  bending_stress_pa: number
  margin: number | null
}
interface StructuralEnvelopeResult {
  verdict: string
  material_id: string
  material_source: string
  material_uncertainty_pct: number
  governing: (RotorResult & { case: string }) | null
  cases: { name: string; rotors: RotorResult[]; minimum_nonzero_margin: number | null }[]
  limitations: string[]
}

/** Case loads are always explicitly entered by the operator, in newtons. */
export function StructuralLabPanel({ design }: { design: DroneDesign }) {
  const [input, setInput] = useState('')
  const [report, setReport] = useState<StructuralEnvelopeResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  useEffect(() => {
    setReport(null)
    setError(null)
  }, [design])
  const evaluate = async () => {
    setError(null)
    setReport(null)
    try {
      const cases = parseStructuralCases(input, design.rotors.length)
      setRunning(true)
      const response = await api.post<StructuralEnvelopeResult>(
        '/designs/structural-envelope', { snapshot: design, cases },
      )
      setReport(response)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setRunning(false)
    }
  }
  return (
    <section className="space-y-2 p-3" aria-label="Structural load-case lab">
      <SectionTitle>Structural load-case lab</SectionTitle>
      <p className="text-[10px] text-slate-400">
        Enter named cases; each line lists {design.rotors.length} rotor thrusts
        in newtons, in design rotor order. No loads are guessed.
      </p>
      <textarea rows={3} value={input} onChange={(e) => setInput(e.target.value)}
        aria-label="Named structural load cases"
        placeholder={`hover: ${design.rotors.map(() => '?').join(', ')}`}
        className="w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs"
      />
      <button type="button" onClick={() => void evaluate()}
        disabled={running || !design.frame || design.rotors.length === 0}
        className="w-full rounded bg-cyan-800 px-2 py-2 text-xs text-white disabled:opacity-40">
        {running ? 'Evaluating…' : 'Evaluate static load cases'}
      </button>
      {!design.frame && <p className="text-xs text-amber-400">
        Frame geometry required; no structural result will be invented.
      </p>}
      {error && <p className="text-xs text-rose-400" role="alert">{error}</p>}
      {report && (
        <div className="space-y-2 rounded border border-slate-700 p-2 text-xs">
          <p className="font-semibold text-cyan-300">{report.verdict.replaceAll('_', ' ')}</p>
          <p className="text-slate-400">
            {report.material_id} · declared uncertainty {report.material_uncertainty_pct}%
          </p>
          {report.governing ? (
            <div className="space-y-1 font-mono">
              <p>Governing: {report.governing.case}, rotor {report.governing.rotor_index + 1}</p>
              <p>Force: {report.governing.thrust_n.toFixed(2)} N</p>
              <p>Lever: {report.governing.span_m.toFixed(3)} m</p>
              <p>Moment: {report.governing.root_bending_moment_n_m.toFixed(3)} N·m</p>
              <p>Stress: {(report.governing.bending_stress_pa / 1e6).toFixed(2)} MPa</p>
              <p>Margin: {report.governing.margin?.toFixed(2) ?? 'undefined'}</p>
            </div>
          ) : <p className="text-amber-300">No nonzero loads: structural strength not assessed.</p>}
          <details>
            <summary className="cursor-pointer text-slate-300">All cases and rotor margins</summary>
            {report.cases.map((item) => (
              <div key={item.name} className="mt-2 space-y-1">
                <p className="font-semibold">{item.name}</p>
                {item.rotors.map((arm) => (
                  <p key={arm.rotor_index} className="font-mono text-[10px] text-slate-400">
                    R{arm.rotor_index + 1}: {arm.thrust_n.toFixed(2)} N ·
                    {(arm.bending_stress_pa / 1e6).toFixed(2)} MPa ·
                    margin {arm.margin?.toFixed(2) ?? 'n/a'}
                  </p>
                ))}
              </div>
            ))}
          </details>
          <p className="text-[10px] text-amber-400">
            Analytical static screen only. Not a physical validation, certification,
            fatigue check, structural joint simulation or real-world success probability.
          </p>
        </div>
      )}
    </section>
  )
}
