import { useEffect, useRef, useState } from 'react'
import { api } from '../services/api'
import { parseDischargeReplayRows } from '../editor/dischargeReplayRows'
import type { DroneDesign } from '../types/api'

interface DischargeReport {
  verdict: string
  accounting: {
    duration_s: number
    charge_consumed_ah: number
    measured_energy_delivered_wh: number
    modeled_final_soc_pct: number
    maximum_c_rate: number
    within_predeclared_sampling_gap: boolean
  }
  prediction: {
    voltage_mae_v: number
    voltage_rmse_v: number
    voltage_max_abs_error_v: number
    voltage_tolerance_met: boolean
    measured_warning_crossing_s: number | null
    predicted_warning_crossing_s: number | null
    endpoint_time_error_pct: number | null
    endpoint_tolerance_met: boolean
  }
}

/** Read-only: measured I/V trace is never installed as a physics component. */
export function DischargeReplayPanel({ design }: { design: DroneDesign }) {
  const batteryId = design.powertrain?.battery_id ?? ''
  const [kind, setKind] = useState('')
  const [serial, setSerial] = useState('')
  const [run, setRun] = useState('')
  const [source, setSource] = useState('')
  const [initialSoc, setInitialSoc] = useState('100')
  const [voltageLimit, setVoltageLimit] = useState('')
  const [endpointLimit, setEndpointLimit] = useState('')
  const [sampleGap, setSampleGap] = useState('')
  const [unused, setUnused] = useState(false)
  const [matches, setMatches] = useState(false)
  const [csv, setCsv] = useState('')
  const [report, setReport] = useState<DischargeReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const version = useRef(0)

  const invalidate = () => {
    version.current += 1
    setReport(null)
    setError(null)
    setRunning(false)
  }
  useEffect(() => { invalidate() }, [batteryId])

  const evaluate = async () => {
    const current = ++version.current
    setError(null)
    setReport(null)
    try {
      if (!batteryId) throw new Error('Select a battery in the powertrain')
      if (kind !== 'synthetic_fixture' && kind !== 'physical_measurements') {
        throw new Error('Select physical or synthetic evidence type')
      }
      if (![serial, run, source].every((v) => v.trim())) {
        throw new Error('Enter battery ID, discharge run ID, and data source')
      }
      const check = (raw: string, name: string, lower: number, upper: number): number => {
        const value = Number(raw)
        if (!raw.trim() || !Number.isFinite(value) || value <= lower || value > upper) {
          throw new Error(name + ' must be >' + lower + ' and <=' + upper)
        }
        return value
      }
      const initial_soc_pct = check(initialSoc, 'Initial SOC', 0, 100)
      const predeclared_max_abs_voltage_error_v = check(voltageLimit, 'Voltage tolerance', 0, 100)
      const predeclared_max_endpoint_time_error_pct = check(endpointLimit, 'Endpoint tolerance', 0, 100)
      const predeclared_max_sample_gap_s = check(sampleGap, 'Maximum sampling gap', 0, 300)
      const samples = parseDischargeReplayRows(csv)
      setRunning(true)
      const data = await api.post<DischargeReport>('/components/discharge-replay', {
        battery_id: batteryId, dataset_kind: kind,
        battery_serial_or_id: serial.trim(), run_id: run.trim(),
        data_source: source.trim(),
        hardware_matches_reference_spec: matches,
        model_unused_for_calibration: unused,
        initial_soc_pct,
        predeclared_max_abs_voltage_error_v,
        predeclared_max_endpoint_time_error_pct,
        predeclared_max_sample_gap_s,
        samples,
      })
      if (version.current === current) setReport(data)
    } catch (e) {
      if (version.current === current) setError((e as Error).message)
    } finally {
      if (version.current === current) setRunning(false)
    }
  }

  return (
    <section aria-label="Battery discharge replay lab" className="space-y-2 p-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-cyan-500">
        Battery discharge replay lab
      </h3>
      <p className="text-[10px] text-slate-400">
        Compare the fixed pack model to an operator-provided current/voltage discharge
        trace. Calculate measured charge and energy without altering aircraft physics.
        A successful conditional replay is not an independently predicted mission.
      </p>
      <p className="text-xs text-cyan-300">Active pack: {batteryId || 'none selected'}</p>
      <label className="block text-xs">
        Evidence type
        <select aria-label="Discharge evidence type" value={kind}
          onChange={(e) => { invalidate(); setKind(e.target.value) }}
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1">
          <option value="">Select evidence type</option>
          <option value="physical_measurements">Operator-reported physical log</option>
          <option value="synthetic_fixture">Synthetic numerical verification only</option>
        </select>
      </label>
      {([
        ['Battery serial or ID', serial, setSerial],
        ['Discharge run ID', run, setRun],
        ['Discharge data source', source, setSource],
        ['Initial SOC percent', initialSoc, setInitialSoc],
        ['Predeclared maximum voltage error V', voltageLimit, setVoltageLimit],
        ['Predeclared maximum warning-time error percent', endpointLimit, setEndpointLimit],
        ['Predeclared maximum sample gap seconds', sampleGap, setSampleGap],
      ] as const).map(([label, value, setter]) => (
        <label key={label} className="block text-xs text-slate-300">
          {label}
          <input aria-label={label} value={value}
            onChange={(e) => { invalidate(); setter(e.target.value) }}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1" />
        </label>
      ))}
      <label className="flex gap-2 text-xs">
        <input type="checkbox" aria-label="Reference battery hardware matches"
          checked={matches} onChange={(e) => { invalidate(); setMatches(e.target.checked) }} />
        I declare this physical battery matches the reference (not verified)
      </label>
      <label className="flex gap-2 text-xs">
        <input type="checkbox" aria-label="Discharge log unused for calibration"
          checked={unused} onChange={(e) => { invalidate(); setUnused(e.target.checked) }} />
        I declare this log was unused for model calibration
      </label>
      <p className="text-[10px] text-slate-400">
        CSV columns: t_s,current_a,terminal_voltage_v,temperature_c.
        At least 6 measurements; blank temperature is unknown, not zero.
        Time starts at 0 s and must strictly increase.
      </p>
      <textarea aria-label="Discharge trace CSV" rows={6} value={csv}
        onChange={(e) => { invalidate(); setCsv(e.target.value) }}
        placeholder={'0,5,24,25\n60,5,23.8,25\n120,5,23.6,25\n180,5,23.4,25\n240,5,23.2,25\n300,5,23.0,25'}
        className="w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs" />
      <p className="text-[10px] text-amber-400">
        Placeholder values only, not physical measurements. Predeclare limits before scoring.
        Measured current is supplied as a known load, not predicted by the simulator.
      </p>
      <button type="button" disabled={running || !batteryId}
        onClick={() => { void evaluate() }}
        className="w-full rounded bg-cyan-800 px-2 py-2 text-xs text-white disabled:opacity-40">
        {running ? 'Replaying…' : 'Replay held-out battery discharge'}
      </button>
      {error && <p role="alert" className="text-xs text-rose-400">{error}</p>}
      {report && (
        <div className="space-y-1 rounded border border-slate-700 p-2 text-xs">
          <p className="font-semibold text-cyan-300">{report.verdict.replaceAll('_', ' ')}</p>
          <p>Recorded discharge time: {report.accounting.duration_s.toFixed(1)} s</p>
          <p>Measured delivered energy: {report.accounting.measured_energy_delivered_wh.toFixed(2)} Wh</p>
          <p>Measured charge: {report.accounting.charge_consumed_ah.toFixed(3)} Ah</p>
          <p>Modeled SOC after replay: {report.accounting.modeled_final_soc_pct.toFixed(2)}%</p>
          <p>Highest measured C rate: {report.accounting.maximum_c_rate.toFixed(2)}C</p>
          <p>Voltage MAE: {report.prediction.voltage_mae_v.toFixed(3)} V</p>
          <p>Maximum voltage error: {report.prediction.voltage_max_abs_error_v.toFixed(3)} V</p>
          <p>Warning time observed in both: {
            report.prediction.measured_warning_crossing_s != null &&
            report.prediction.predicted_warning_crossing_s != null ? 'yes' : 'no'
          }</p>
          <p>Warning time error: {report.prediction.endpoint_time_error_pct == null
            ? 'unavailable' : report.prediction.endpoint_time_error_pct.toFixed(2) + '%'}</p>
          <p className="text-[10px] text-amber-300">
            Reported evidence and equipment identity are not independently authenticated.
            Generic pack parameters, battery temperature and high-C capacity derating
            still need physical characterization.
          </p>
        </div>
      )}
    </section>
  )
}
