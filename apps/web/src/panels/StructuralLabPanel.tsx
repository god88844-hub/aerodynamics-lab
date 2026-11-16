import { useEffect, useRef, useState } from 'react'
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
  arm_axial_torque_n_m: number | null
  tube_peak_shear_stress_pa: number | null
  tube_shear_margin: number | null
  joint_bending_margin: number | null
  joint_axial_torque_margin: number | null
}
interface StructuralEnvelopeResult {
  verdict: string
  material_id: string
  material_source: string
  material_uncertainty_pct: number
  governing: (RotorResult & { case: string }) | null
  cases: { name: string; rotors: RotorResult[]; minimum_nonzero_margin: number | null }[]
  limitations: string[]
  advanced_loads: {
    screening_verdict: string
    axial_torque_cases_with_data: number
    axial_torque_cases_total: number
    tube_torsion_screen: boolean | null
    joint_bending_screen: boolean | null
    joint_axial_torque_screen: boolean | null
    combined_interaction: string
    limitations: string[]
  }
}

/** Case loads are always explicitly entered by the operator, in newtons. */
export function StructuralLabPanel({ design }: { design: DroneDesign }) {
  const [input, setInput] = useState('')
  const [shearMpa, setShearMpa] = useState('')
  const [shearSource, setShearSource] = useState('')
  const [jointMoment, setJointMoment] = useState('')
  const [jointTorque, setJointTorque] = useState('')
  const [jointSource, setJointSource] = useState('')
  const [report, setReport] = useState<StructuralEnvelopeResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const requestVersion = useRef(0)
  useEffect(() => {
    // Discard pending responses if the design is edited before they arrive.
    requestVersion.current += 1
    setRunning(false)
    setReport(null)
    setError(null)
  }, [design])
  const evaluate = async () => {
    const version = ++requestVersion.current
    setError(null)
    setReport(null)
    try {
      const cases = parseStructuralCases(input, design.rotors.length)
      const optional: Record<string, unknown> = {}
      if (shearMpa.trim() || shearSource.trim()) {
        const value = Number(shearMpa)
        if (!shearMpa.trim() || !Number.isFinite(value) || value <= 0 ||
            !shearSource.trim()) {
          throw new Error('Shear allowable requires positive MPa and a source')
        }
        optional.shear_allowable_pa = value * 1e6
        optional.shear_allowable_source = shearSource.trim()
      }
      if (jointMoment.trim() || jointTorque.trim() || jointSource.trim()) {
        const moment = Number(jointMoment)
        const torque = Number(jointTorque)
        if (!jointMoment.trim() || !jointTorque.trim() ||
            !Number.isFinite(moment) || moment <= 0 ||
            !Number.isFinite(torque) || torque <= 0 || !jointSource.trim()) {
          throw new Error('Joint capacities require positive bending and axial torque limits plus a source')
        }
        optional.joint_allowables = {
          bending_moment_n_m: moment, axial_torque_n_m: torque,
          evidence_source: jointSource.trim(),
        }
      }
      setRunning(true)
      const response = await api.post<StructuralEnvelopeResult>(
        '/designs/structural-envelope', { snapshot: design, cases, ...optional },
      )
      if (requestVersion.current === version) setReport(response)
    } catch (e) {
      if (requestVersion.current === version) setError((e as Error).message)
    } finally {
      if (requestVersion.current === version) setRunning(false)
    }
  }
  return (
    <section className="space-y-2 p-3" aria-label="Structural load-case lab">
      <SectionTitle>Structural load-case lab</SectionTitle>
      <p className="text-[10px] text-slate-400">
        Enter named cases; each line lists {design.rotors.length} rotor thrusts
        in newtons, in design rotor order. After | you may enter explicit
        signed arm-axis torques in N·m. No loads are guessed.
      </p>
      <textarea rows={3} value={input} onChange={(e) => setInput(e.target.value)}
        aria-label="Named structural load cases"
        placeholder={`hover: ${design.rotors.map(() => '?').join(', ')}`}
        className="w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs"
      />
      <details className="rounded border border-slate-800 p-2 text-xs">
        <summary className="cursor-pointer text-cyan-300">Optional torsion and joint inputs</summary>
        <p className="mt-2 text-[10px] text-slate-400">
          Provide separately verified strength limits with their sources.
          Motor reaction yaw torque is NOT the arm-axis torque.
          Blank values mean unassessed, not zero.
        </p>
        <div className="mt-2 space-y-2">
          <label className="block text-slate-300">
            Tube shear allowable (MPa)
            <input type="number" min="0" step="1" value={shearMpa}
              aria-label="Tube shear allowable MPa"
              onChange={(e) => setShearMpa(e.target.value)}
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1" />
          </label>
          <label className="block text-slate-300">
            Shear allowable evidence source
            <input type="text" value={shearSource} maxLength={240}
              aria-label="Shear evidence source"
              onChange={(e) => setShearSource(e.target.value)}
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1" />
          </label>
          <label className="block text-slate-300">
            Joint bending capacity (N·m)
            <input type="number" min="0" step=".1" value={jointMoment}
              aria-label="Joint bending capacity"
              onChange={(e) => setJointMoment(e.target.value)}
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1" />
          </label>
          <label className="block text-slate-300">
            Joint arm-axis torque capacity (N·m)
            <input type="number" min="0" step=".1" value={jointTorque}
              aria-label="Joint arm-axis torque capacity"
              onChange={(e) => setJointTorque(e.target.value)}
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1" />
          </label>
          <label className="block text-slate-300">
            Joint capacity evidence source
            <input type="text" value={jointSource} maxLength={240}
              aria-label="Joint evidence source"
              onChange={(e) => setJointSource(e.target.value)}
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1" />
          </label>
        </div>
      </details>
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
          <div className="space-y-1 rounded border border-slate-800 p-2">
            <p className="font-semibold text-amber-300">
              Advanced: {report.advanced_loads.screening_verdict.replaceAll('_', ' ')}
            </p>
            <p>Arm-axis torque inputs: {report.advanced_loads.axial_torque_cases_with_data}
              / {report.advanced_loads.axial_torque_cases_total} cases</p>
            <p>Tube shear screen: {String(report.advanced_loads.tube_torsion_screen ?? 'unassessed')}</p>
            <p>Joint bending: {String(report.advanced_loads.joint_bending_screen ?? 'unassessed')}</p>
            <p>Joint torsion: {String(report.advanced_loads.joint_axial_torque_screen ?? 'unassessed')}</p>
            <p className="font-semibold text-amber-300">
              Combined bending–torsion/joint interaction: NOT MODELED
            </p>
          </div>
          <details>
            <summary className="cursor-pointer text-slate-300">All cases and rotor margins</summary>
            {report.cases.map((item) => (
              <div key={item.name} className="mt-2 space-y-1">
                <p className="font-semibold">{item.name}</p>
                {item.rotors.map((arm) => (
                  <p key={arm.rotor_index} className="font-mono text-[10px] text-slate-400">
                    R{arm.rotor_index + 1}: {arm.thrust_n.toFixed(2)} N ·
                    {(arm.bending_stress_pa / 1e6).toFixed(2)} MPa ·
                    bend margin {arm.margin?.toFixed(2) ?? 'n/a'} ·
                    axial torque {arm.arm_axial_torque_n_m?.toFixed(3) ?? 'unknown'} N·m ·
                    shear {arm.tube_peak_shear_stress_pa != null
                      ? (arm.tube_peak_shear_stress_pa / 1e6).toFixed(3)
                      : 'unknown'} MPa · shear margin {arm.tube_shear_margin?.toFixed(2) ?? 'unassessed'} ·
                    joint bend margin {arm.joint_bending_margin?.toFixed(2) ?? 'unassessed'} ·
                    joint torque margin {arm.joint_axial_torque_margin?.toFixed(2) ?? 'unassessed'}
                  </p>
                ))}
              </div>
            ))}
          </details>
          <p className="text-[10px] text-amber-400">
            Analytical static screen only. Not a physical validation, certification,
            fatigue check, structural joint simulation or real-world success probability.
            Passing separate screens does NOT establish combined structural safety.
          </p>
        </div>
      )}
    </section>
  )
}
