import { useEffect, useRef, useState } from 'react'
import { api } from '../services/api'
import type { DroneDesign } from '../types/api'
import { parseBatteryEvidenceRows } from '../editor/batteryEvidenceRows'
import { SectionTitle } from './fields'

interface FitMetrics {
  count: number
  mae_v: number
  rmse_v: number
  bias_v: number
  mape_pct: number
  max_abs_percentage_error_pct: number
}
interface HoldoutObservation {
  id: string
  soc_pct: number
  current_a: number
  c_rate: number
  temperature_c: number | null
  measured_voltage_v: number
  predicted_voltage_v: number
  absolute_percentage_error_pct: number
}
interface BatteryEvidenceReport {
  battery_id: string
  dataset_kind: string
  verdict: string
  simulation_battery_modified: boolean
  sources: { self_reported_not_authenticated: boolean }
  fit: {
    fitted_pack_resistance_ohm: number
    declared_pack_resistance_ohm: number | null
    calibration_metrics: FitMetrics
    calibration_current_range_a: number[]
    calibration_soc_range_pct: number[]
  }
  heldout: {
    metrics: FitMetrics
    rows: HoldoutObservation[]
    nominal_model_metrics: FitMetrics | null
    nominal_model_status: string
    within_calibration_envelope: boolean
    meets_predeclared_error_tolerance: boolean
    max_observed_c_rate: number
    above_declared_c_rate_limit: boolean | null
  }
  temperature: { recorded_count: number; missing_count: number; modeled: boolean }
  limitations: string[]
}

/** No results are persisted or promoted to the active flight battery model. */
export function BatteryEvidencePanel({ design }: { design: DroneDesign }) {
  const batteryId = design.powertrain?.battery_id ?? ''
  const [datasetKind, setDatasetKind] = useState('')
  const [calibrationRun, setCalibrationRun] = useState('')
  const [heldoutRun, setHeldoutRun] = useState('')
  const [calibrationSource, setCalibrationSource] = useState('')
  const [heldoutSource, setHeldoutSource] = useState('')
  const [tolerance, setTolerance] = useState('')
  const [samplesText, setSamplesText] = useState('')
  const [report, setReport] = useState<BatteryEvidenceReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const version = useRef(0)

  const invalidate = () => {
    version.current += 1
    setReport(null)
    setError(null)
    setRunning(false)
  }
  useEffect(() => {
    version.current += 1
    setReport(null)
    setError(null)
    setRunning(false)
  }, [design])

  const evaluate = async () => {
    const currentVersion = ++version.current
    setError(null)
    setReport(null)
    try {
      if (!batteryId) throw new Error('Select a battery powertrain component first')
      if (datasetKind !== 'physical_measurements' && datasetKind !== 'synthetic_fixture') {
        throw new Error('Declare whether inputs are measurements or synthetic fixtures')
      }
      const threshold = Number(tolerance)
      if (!tolerance.trim() || !Number.isFinite(threshold) || threshold <= 0 ||
          threshold > 100) throw new Error('Predeclare an error tolerance between 0 and 100%')
      if (![calibrationRun, heldoutRun, calibrationSource, heldoutSource]
        .every((v) => v.trim())) throw new Error('Enter distinct run IDs and both evidence sources')
      if (calibrationRun.trim() === heldoutRun.trim()) {
        throw new Error('Calibration and held-out runs must be different')
      }
      const samples = parseBatteryEvidenceRows(samplesText)
      setRunning(true)
      const data = await api.post<BatteryEvidenceReport>('/components/battery-evidence', {
        battery_id: batteryId,
        dataset_kind: datasetKind,
        calibration_run_id: calibrationRun.trim(),
        heldout_run_id: heldoutRun.trim(),
        calibration_source: calibrationSource.trim(),
        heldout_source: heldoutSource.trim(),
        predeclared_max_abs_percentage_error_pct: threshold,
        samples,
      })
      if (version.current === currentVersion) setReport(data)
    } catch (e) {
      if (version.current === currentVersion) setError((e as Error).message)
    } finally {
      if (version.current === currentVersion) setRunning(false)
    }
  }
  return (
    <section className="space-y-2 p-3" aria-label="Battery evidence lab">
      <SectionTitle>Battery evidence lab</SectionTitle>
      <p className="text-[10px] text-slate-400">
        Fit one pack-resistance estimate to a declared calibration discharge
        run, and score a separate held-out run. Actual pack measurements are
        required for empirical evidence. This never changes flight predictions.
      </p>
      <p className="text-xs text-cyan-300">
        Active pack: {batteryId || 'none selected'}
      </p>
      <label className="block text-xs text-slate-300">
        Evidence type
        <select aria-label="Battery evidence type" value={datasetKind}
          onChange={(e) => { invalidate(); setDatasetKind(e.target.value) }}
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1">
          <option value="">Choose evidence type</option>
          <option value="physical_measurements">Reported physical measurements</option>
          <option value="synthetic_fixture">Synthetic (code verification only)</option>
        </select>
      </label>
      {([
        ['Calibration run ID', calibrationRun, setCalibrationRun],
        ['Held-out run ID', heldoutRun, setHeldoutRun],
        ['Calibration data source', calibrationSource, setCalibrationSource],
        ['Held-out data source', heldoutSource, setHeldoutSource],
      ] as const).map(([name, value, update]) => (
        <label key={name} className="block text-xs text-slate-300">
          {name}
          <input aria-label={name} type="text" value={value} maxLength={500}
            onChange={(e) => { invalidate(); update(e.target.value) }}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1" />
        </label>
      ))}
      <label className="block text-xs text-slate-300">
        Predeclared maximum voltage prediction error (%)
        <input aria-label="Predeclared maximum voltage error percent" type="number"
          min="0.01" max="100" step=".1" value={tolerance}
          onChange={(e) => { invalidate(); setTolerance(e.target.value) }}
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1" />
      </label>
      <p className="text-[10px] text-slate-400">
        CSV columns: id, split (calibration/held_out), SOC %, pack current A,
        measured loaded pack voltage V, temperature °C (blank if unknown).
        Use at least three calibration points and two from a different run.
      </p>
      <textarea aria-label="Battery discharge CSV rows"
        rows={6} value={samplesText}
        onChange={(e) => { invalidate(); setSamplesText(e.target.value) }}
        placeholder={'c1,calibration,40,10,23.2,25\nc2,calibration,50,20,22.9,25\nc3,calibration,60,30,22.5,25\nh1,held_out,45,15,23.0,25\nh2,held_out,55,25,22.7,25'}
        className="w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs" />
      <p className="text-[10px] text-amber-400">
        Placeholder numbers illustrate the CSV format only. Do not treat
        them as tested pack values or independent validation evidence.
      </p>
      <button type="button" disabled={running || !batteryId}
        onClick={() => void evaluate()}
        className="w-full rounded bg-cyan-800 px-2 py-2 text-xs text-white disabled:opacity-40">
        {running ? 'Evaluating…' : 'Evaluate held-out battery evidence'}
      </button>
      {error && <p role="alert" className="text-xs text-rose-400">{error}</p>}
      {report && (
        <div className="space-y-2 rounded border border-slate-700 p-2 text-xs">
          <p className="font-semibold text-cyan-300">
            {report.verdict.replaceAll('_', ' ')}
          </p>
          <p className="text-slate-400">
            Battery resistance (fit): {(report.fit.fitted_pack_resistance_ohm * 1000).toFixed(2)} mΩ
          </p>
          <p className="text-slate-400">
            Current pack model: {report.fit.declared_pack_resistance_ohm == null
              ? 'unknown resistance'
              : `${(report.fit.declared_pack_resistance_ohm * 1000).toFixed(2)} mΩ`}
          </p>
          <p>Held-out MAPE: {report.heldout.metrics.mape_pct.toFixed(2)}%</p>
          <p>Held-out RMSE: {report.heldout.metrics.rmse_v.toFixed(3)} V</p>
          <p>Worst held-out error: {report.heldout.metrics.max_abs_percentage_error_pct.toFixed(2)}%</p>
          <p>Within measured calibration envelope: {report.heldout.within_calibration_envelope ? 'yes' : 'no'}</p>
          <p>Predeclared voltage-error tolerance met: {report.heldout.meets_predeclared_error_tolerance ? 'yes' : 'no'}</p>
          <p>Highest held-out load: {report.heldout.max_observed_c_rate.toFixed(2)}C</p>
          <p>Above declared C-rating: {report.heldout.above_declared_c_rate_limit == null
            ? 'unknown (no rating supplied)' : report.heldout.above_declared_c_rate_limit ? 'yes' : 'no'}</p>
          <p>Temperature correction modeled: no</p>
          <p>Original model comparison: {report.heldout.nominal_model_status.replaceAll('_', ' ')}</p>
          {report.heldout.nominal_model_metrics &&
            <p>Original model held-out MAPE: {report.heldout.nominal_model_metrics.mape_pct.toFixed(2)}%</p>}
          <details>
            <summary className="cursor-pointer">Measured vs predicted held-out rows</summary>
            {report.heldout.rows.map((row) => (
              <p key={row.id} className="mt-1 font-mono text-[10px]">
                {row.id}: {row.current_a.toFixed(1)} A · measured {row.measured_voltage_v.toFixed(3)} V ·
                predicted {row.predicted_voltage_v.toFixed(3)} V ·
                error {row.absolute_percentage_error_pct.toFixed(2)}%
              </p>
            ))}
          </details>
          <p className="text-[10px] text-amber-300">
            Provenance and run independence are user-declared, not authenticated.
            No battery model or existing flight simulation was modified.
            Numerical fit is not a probability of real-world flight success.
          </p>
        </div>
      )}
    </section>
  )
}
